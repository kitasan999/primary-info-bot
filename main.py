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
import time
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
from process.decision_status import classify_decision_status, should_notify_by_status
from process.quality_gate import apply_quality_gate
from process.relevance import assess_relevance, is_obvious_discussing_title, priority_score, quick_title_score
from process.topic_dedupe import merge_same_topic
from process.score import score_article
from process.summarize import enrich_article

CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
MAX_NOTIFY_PER_RUN = 10
MONEY_SOURCE_IDS = {"fsa_news", "boj_news", "mof_news"}


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


def filter_relevant_articles(
    articles: list[dict[str, Any]],
    profile: dict[str, Any],
    max_count: int = MAX_NOTIFY_PER_RUN,
    *,
    demo: bool = False,
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]], int]:
    """介護職向けに関係ありそうな記事だけ残す（要約は統合後だけ）"""
    candidates: list[dict[str, Any]] = []
    skipped: list[tuple[dict[str, Any], str]] = []
    min_score = profile.get("min_score_to_notify", 3)

    for article in articles:
        title = article.get("title", "")
        source_id = article.get("source_id", "")
        pre_score = quick_title_score(title, profile)

        if source_id != "mhlw_kinkyu" and is_obvious_discussing_title(title):
            skipped.append((article, "協議中・検討会（まだ決まってない）"))
            continue

        if source_id != "mhlw_kinkyu" and pre_score < 1:
            skipped.append((article, "タイトルから関係薄いと判断"))
            continue

        article["decision_status"] = classify_decision_status(article)
        score = max(pre_score, 5) if source_id == "mhlw_kinkyu" else pre_score
        topic_ok = score >= min_score
        status_ok = should_notify_by_status(article["decision_status"], profile, score, title=title)
        if not (topic_ok and status_ok):
            dec = article["decision_status"]
            if dec.get("type") == "discussing" and score >= min_score:
                skipped.append((article, "協議中・検討会（まだ決まってない）"))
            elif dec.get("type") == "info":
                skipped.append((article, "更新情報（通知設定オフ）"))
            else:
                skipped.append((article, "タイトルから関係薄いと判断"))
            continue

        article["_pre_score"] = score
        candidates.append(article)

    candidates.sort(
        key=lambda a: (
            priority_score(a.get("title", ""), profile),
            a.get("_pre_score", 0),
            a.get("decision_status", {}).get("type") == "decided",
        ),
        reverse=True,
    )

    merged, merged_n = merge_same_topic(candidates)
    if merged_n > 0:
        print(f"  同トピック統合: {len(candidates)}件 → {len(merged)}件（{merged_n}件を統合）")

    relevant: list[dict[str, Any]] = []
    for idx, article in enumerate(merged[:max_count]):
        if idx > 0:
            time.sleep(2)
        title = article.get("title", "")
        source_id = article.get("source_id", "")
        print(f"  要約中: {title[:36]}…")
        try:
            enrich_article(article, profile=profile)
            rel = assess_relevance(article, profile)
            if source_id == "mhlw_kinkyu":
                rel["relevance_score"] = max(rel["relevance_score"], 5)
                rel["relevance_label"] = "🟢 関係大"
                rel["relevance_reason"] = "厚労省の緊急情報（優先確認）"
                rel["notify"] = True
                article["relevance"] = rel
        except Exception as exc:
            skipped.append((article, f"読み取り失敗: {exc}"))
            continue

        if article.get("relevance", {}).get("notify"):
            keep, why = apply_quality_gate(article, profile, demo=demo)
            if not keep:
                skipped.append((article, why))
                continue
            relevant.append(article)
        else:
            reason = article.get("relevance", {}).get("relevance_reason", "関係薄い")
            skipped.append((article, reason))

    return relevant, skipped, merged_n


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


def run_preview(digest_mode: bool = False, money_mode: bool = False) -> int:
    """通知内容をターミナルにプレビュー（Discord送信なし）"""
    import json as json_mod

    sources_cfg = load_yaml(CONFIG_DIR / "sources.yaml")
    keywords = load_yaml(CONFIG_DIR / "keywords.yaml")
    profile = load_yaml(CONFIG_DIR / "profile.yaml")

    source = next((s for s in sources_cfg.get("sources", []) if s.get("enabled", True)), None)
    if money_mode:
        print("お金系プレビュー生成中…")
        candidates = _build_candidates(sources_cfg.get("sources", []), keywords, source_ids=MONEY_SOURCE_IDS)
        if not candidates:
            print("❌ お金系ソースから記事を取得できませんでした。")
            return 1
        max_count = 1
    else:
        if not source:
            print("❌ 有効な情報源がありません。")
            return 1
        print("プレビュー生成中…")
        raw = fetch_source(source)
        candidates = []
        for item in raw[:40]:
            article = normalize_article(item)
            classify_article(article, keywords)
            score_article(article, keywords)
            candidates.append(article)
        max_count = 5 if digest_mode else 1

    relevant, skipped, merged_n = filter_relevant_articles(
        candidates, profile, max_count=max_count, demo=money_mode
    )

    from notify.base import format_discord_embed
    from notify.digest import format_digest_embed

    if not relevant:
        print("関係ありそうな記事なし")
        return 0

    demo_profile = dict(profile)
    if digest_mode:
        demo_profile["digest_threshold"] = 1

    threshold = demo_profile.get("digest_threshold", 3)
    from process.category import sort_by_category

    relevant = sort_by_category(relevant)

    if len(relevant) > threshold:
        embed = format_digest_embed(relevant, merged_n)
        print(json_mod.dumps(embed, ensure_ascii=False, indent=2))
    else:
        for art in relevant:
            embed = format_discord_embed(art)
            print(json_mod.dumps(embed, ensure_ascii=False, indent=2))
            print("---")
    return 0


def _build_candidates(
    sources: list[dict[str, Any]],
    keywords: dict[str, Any],
    *,
    source_ids: set[str] | None = None,
    per_source: int = 40,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source in sources:
        if not source.get("enabled", True):
            continue
        sid = source.get("id", "")
        if source_ids and sid not in source_ids:
            continue
        try:
            raw = fetch_source(source)
        except Exception as exc:
            print(f"  取得失敗 {sid}: {exc}")
            continue
        for item in raw[:per_source]:
            article = normalize_article(item)
            classify_article(article, keywords)
            score_article(article, keywords)
            candidates.append(article)
    return candidates


def run_demo_money() -> int:
    """金融庁・日銀・財務省からお金系デモ通知を1件送る"""
    sources_cfg = load_yaml(CONFIG_DIR / "sources.yaml")
    keywords = load_yaml(CONFIG_DIR / "keywords.yaml")
    profile = load_yaml(CONFIG_DIR / "profile.yaml")

    sources = sources_cfg.get("sources", [])
    print("お金・NISA・税制系の記事を探しています…")
    candidates = _build_candidates(sources, keywords, source_ids=MONEY_SOURCE_IDS)
    if not candidates:
        print("❌ お金系ソースから記事を取得できませんでした。")
        return 1

    candidates.sort(
        key=lambda a: (priority_score(a.get("title", ""), profile), quick_title_score(a.get("title", ""), profile)),
        reverse=True,
    )
    relevant, skipped, merged_n = filter_relevant_articles(candidates, profile, max_count=1, demo=True)

    if not relevant:
        print("\n⚪ 今の新着の中に、お金系っぽい記事がありませんでした。")
        print("スキップした例：")
        for art, reason in skipped[:5]:
            print(f"  × [{art.get('source_name', '')}] {art.get('title', '')[:36]}…")
            print(f"    → {reason}")
        return 0

    article = relevant[0]
    print("\nお金系デモ通知（1件）：")
    print_notifications([article], profile)

    if not get_webhook_url():
        print("（Webhook未設定のためターミナル表示のみ）")
        return 1

    try:
        send_discord([article], profile, merged_n)
        print("✅ Discord にお金系デモ通知を送信しました。")
        return 0
    except Exception as exc:
        print(f"❌ 送信失敗: {exc}")
        return 1


def run_demo_notify(digest_mode: bool = False) -> int:
    """関係ありそうな記事を試し送り（digest_mode=True なら複数件まとめ）"""
    sources_cfg = load_yaml(CONFIG_DIR / "sources.yaml")
    keywords = load_yaml(CONFIG_DIR / "keywords.yaml")
    profile = load_yaml(CONFIG_DIR / "profile.yaml")

    source = next((s for s in sources_cfg.get("sources", []) if s.get("enabled", True)), None)
    if not source:
        print("❌ 有効な情報源がありません。")
        return 1

    raw = fetch_source(source)
    if not raw:
        print("❌ 記事を取得できませんでした。")
        return 1

    candidates = []
    for item in raw[:40]:
        article = normalize_article(item)
        classify_article(article, keywords)
        score_article(article, keywords)
        candidates.append(article)

    max_count = 5 if digest_mode else 1
    print("介護職向けに関係ありそうな記事を探しています…")
    relevant, skipped, merged_n = filter_relevant_articles(candidates, profile, max_count=max_count)

    if not relevant:
        print("\n⚪ 今の新着の中に、介護現場向けっぽい記事がありませんでした。")
        print("（だから通知が来へんのは正常やで）\n")
        print("スキップした例：")
        for art, reason in skipped[:5]:
            print(f"  × {art.get('title', '')[:42]}…")
            print(f"    → {reason}")
        return 0

    if digest_mode:
        profile = dict(profile)
        profile["digest_threshold"] = 1
        print(f"\nまとめ通知デモ（{len(relevant)}件）：")
        print_notifications(relevant, profile)
    else:
        article = relevant[0]
        print("\n関係ありそうな記事1件のデモ通知：")
        print_notifications([article], profile)

    if not get_webhook_url():
        print("（Webhook未設定のためターミナル表示のみ）")
        return 1

    try:
        demo_profile = dict(profile)
        if digest_mode:
            demo_profile["digest_threshold"] = 1
        send_discord(relevant if digest_mode else [relevant[0]], demo_profile, merged_n)
        print("✅ Discord にデモ通知を送信しました。")
        return 0
    except Exception as exc:
        print(f"❌ 送信失敗: {exc}")
        return 1


def main() -> int:
    load_dotenv(ROOT / ".env")
    sources_cfg = load_yaml(CONFIG_DIR / "sources.yaml")
    keywords = load_yaml(CONFIG_DIR / "keywords.yaml")
    profile = load_yaml(CONFIG_DIR / "profile.yaml")
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

    print(f"\n新着 {len(all_new)} 件 → 介護職向けにフィルタします…")
    to_notify, skipped, merged_n = filter_relevant_articles(all_new, profile, MAX_NOTIFY_PER_RUN)

    if skipped:
        print(f"  スキップ: {len(skipped)} 件（関係薄い）")
        for art, reason in skipped[:3]:
            print(f"    × {art.get('title', '')[:30]}… → {reason}")

    if not to_notify:
        print("\n関係ありそうな新着なし（通知しません）。")
        return 0

    sent = send_discord(to_notify, profile, merged_n)
    if sent:
        threshold = profile.get("digest_threshold", 3)
        if len(to_notify) > threshold:
            print(f"\nDiscord にまとめ通知（{len(to_notify)}件）を送信しました。")
        else:
            print(f"\nDiscord に {len(to_notify)} 件送信しました。")
    else:
        print("\nDISCORD_WEBHOOK_URL 未設定 → ターミナルに表示します。")
        print_notifications(to_notify, profile)

    return 1 if error_count else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="厚労省 一次情報収集ボット")
    parser.add_argument("--test", action="store_true", help="Discordテスト通知を1件送る")
    parser.add_argument("--demo", action="store_true", help="最新記事1件を試し送り")
    parser.add_argument("--demo-money", action="store_true", help="金融庁・日銀・財務省のデモ通知")
    parser.add_argument("--demo-digest", action="store_true", help="複数件をまとめ通知で試し送り")
    parser.add_argument("--preview", action="store_true", help="Discord送信せず通知プレビュー")
    parser.add_argument("--preview-money", action="store_true", help="お金系ソースのプレビュー")
    args = parser.parse_args()

    if args.test:
        load_dotenv(ROOT / ".env")
        raise SystemExit(run_test_notify())
    if args.preview_money:
        load_dotenv(ROOT / ".env")
        raise SystemExit(run_preview(money_mode=True))
    if args.preview:
        load_dotenv(ROOT / ".env")
        raise SystemExit(run_preview(digest_mode=args.demo_digest))
    if args.demo_money:
        load_dotenv(ROOT / ".env")
        raise SystemExit(run_demo_money())
    if args.demo or args.demo_digest:
        load_dotenv(ROOT / ".env")
        raise SystemExit(run_demo_notify(digest_mode=args.demo_digest))

    raise SystemExit(main())
