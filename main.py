"""
厚労省 一次情報収集ボット — エントリーポイント

使い方:
  cd primary-info-bot
  pip install -r requirements.txt
  python main.py              … 通常実行（新着だけ通知）
  python main.py --test       … Discordテスト通知1件
  python main.py --demo       … 最新記事1件を試し送り（既読は変えない）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fetch.rss_fetcher import fetch_rss
from notify.discord import get_webhook_url, print_notifications, send_discord, send_raw_message
from process.classify import classify_article
from process.dedupe import cleanup_seen_ids, filter_new_articles
from process.normalize import normalize_article
from process.score import score_article

CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
MAX_NOTIFY_PER_RUN = 10


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_log(log: list[dict[str, Any]], entry: dict[str, Any], max_len: int = 50) -> list[dict[str, Any]]:
    log.append(entry)
    return log[-max_len:]


def fetch_source(source: dict[str, Any]) -> list[dict[str, Any]]:
    source_type = source.get("type", "rss")
    if source_type == "rss":
        return fetch_rss(source)
    raise ValueError(f"未対応の type: {source_type} ({source.get('id')})")


def load_dotenv(path: Path) -> None:
    """pip不要の簡易 .env 読み込み"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def run_test_notify() -> int:
    """Discord接続テスト"""
    print("Discord テスト通知を送ります…")
    if not get_webhook_url():
        print("\n❌ Webhook URL が未設定です。")
        print("  primary-info-bot フォルダに .env を作って、次の1行を書いてください：")
        print('  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxx/xxxx')
        return 1

    try:
        send_raw_message("✅ 厚労省ボットのテスト通知です。Discord連携OK！")
        print("✅ Discord に送信しました。チャンネルを確認してください。")
        return 0
    except Exception as exc:
        print(f"\n❌ 送信失敗: {exc}")
        print("  Webhook URL が正しいか、Discord側でWebhookが削除されてないか確認してください。")
        return 1


def run_demo_notify() -> int:
    """最新記事1件を試し送り（seen_ids は更新しない）"""
    sources_cfg = load_yaml(CONFIG_DIR / "sources.yaml")
    keywords = load_yaml(CONFIG_DIR / "keywords.yaml")

    source = next((s for s in sources_cfg.get("sources", []) if s.get("enabled", True)), None)
    if not source:
        print("❌ 有効な情報源がありません。")
        return 1

    raw = fetch_source(source)
    if not raw:
        print("❌ 記事を取得できませんでした。")
        return 1

    article = normalize_article(raw[0])
    classify_article(article, keywords)
    score_article(article, keywords)

    print("最新記事1件のデモ通知：")
    print_notifications([article])

    if not get_webhook_url():
        print("（Webhook未設定のためターミナル表示のみ。Discordに送るには .env を設定）")
        return 1

    try:
        send_discord([article])
        print("✅ Discord にデモ通知を送信しました。")
        return 0
    except Exception as exc:
        print(f"❌ 送信失敗: {exc}")
        return 1


def main() -> int:
    load_dotenv(ROOT / ".env")
    sources_cfg = load_yaml(CONFIG_DIR / "sources.yaml")
    keywords = load_yaml(CONFIG_DIR / "keywords.yaml")
    seen_ids = load_json(DATA_DIR / "seen_ids.json", {})
    run_log = load_json(DATA_DIR / "run_log.json", [])

    is_first_run = len(seen_ids) == 0
    all_new: list[dict[str, Any]] = []
    error_count = 0

    for source in sources_cfg.get("sources", []):
        if not source.get("enabled", True):
            continue

        source_id = source.get("id", "unknown")
        try:
            raw_articles = fetch_source(source)
            normalized = [normalize_article(a) for a in raw_articles if a.get("url")]

            if is_first_run:
                for article in normalized:
                    seen_ids[article["id"]] = {
                        "url": article["url"],
                        "title": article["title"],
                        "first_seen": datetime.now(timezone.utc).isoformat(),
                    }
                print(f"[初回] {source_id}: {len(normalized)} 件を既読登録（通知なし）")
                run_log = append_log(
                    run_log,
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_id": source_id,
                        "status": "bootstrap",
                        "count": len(normalized),
                    },
                )
                continue

            new_articles, seen_ids = filter_new_articles(normalized, seen_ids)
            for article in new_articles:
                classify_article(article, keywords)
                score_article(article, keywords)
            all_new.extend(new_articles)

            run_log = append_log(
                run_log,
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_id": source_id,
                    "status": "ok",
                    "fetched": len(normalized),
                    "new": len(new_articles),
                },
            )
            print(f"[OK] {source_id}: 取得 {len(normalized)} / 新着 {len(new_articles)}")

        except Exception as exc:
            error_count += 1
            run_log = append_log(
                run_log,
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_id": source_id,
                    "status": "error",
                    "message": str(exc),
                },
            )
            print(f"[ERROR] {source_id}: {exc}", file=sys.stderr)

    seen_ids = cleanup_seen_ids(seen_ids)
    save_json(DATA_DIR / "seen_ids.json", seen_ids)
    save_json(DATA_DIR / "run_log.json", run_log)

    if is_first_run:
        print("\n初回実行完了。次回から新着だけ通知されます。")
        return 0

    if not all_new:
        print("\n新着なし。")
        return 0

    # 重要度が高い順、同率なら新しい順（sort は安定なので2回）
    all_new.sort(key=lambda a: a.get("published", ""), reverse=True)
    all_new.sort(key=lambda a: a.get("score", 0), reverse=True)
    to_notify = all_new[:MAX_NOTIFY_PER_RUN]

    if len(all_new) > MAX_NOTIFY_PER_RUN:
        print(f"\n新着 {len(all_new)} 件（通知は最大 {MAX_NOTIFY_PER_RUN} 件）")

    sent = send_discord(to_notify)
    if sent:
        print(f"\nDiscord に {len(to_notify)} 件送信しました。")
    else:
        print("\nDISCORD_WEBHOOK_URL 未設定 → ターミナルに表示します。")
        print_notifications(to_notify)

    return 1 if error_count else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="厚労省 一次情報収集ボット")
    parser.add_argument("--test", action="store_true", help="Discordテスト通知を1件送る")
    parser.add_argument("--demo", action="store_true", help="最新記事1件を試し送り（既読は変えない）")
    args = parser.parse_args()

    if args.test:
        load_dotenv(ROOT / ".env")
        raise SystemExit(run_test_notify())
    if args.demo:
        load_dotenv(ROOT / ".env")
        raise SystemExit(run_demo_notify())

    raise SystemExit(main())
