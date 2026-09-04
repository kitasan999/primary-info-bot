#!/usr/bin/env python3
"""
日本の一次情報（経済・政策）を取得し、重要なものだけ Gemini で解説して Discord に通知する。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import feedparser
import google.generativeai as genai
import requests

# ---------------------------------------------------------------------------
# 設定（フィードやキーワードはここを編集すれば追加・削除しやすい）
# ---------------------------------------------------------------------------

FEEDS: list[dict[str, str]] = [
    {"name": "TDnet", "url": "https://webapi.yanoshin.jp/webapi/tdnet/list/recent.rss"},
    {"name": "内閣府", "url": "https://www.cao.go.jp/rss/news.rdf"},
    {"name": "厚生労働省", "url": "https://www.mhlw.go.jp/stf/news.rdf"},
    {"name": "防衛省", "url": "https://www.mod.go.jp/j/press/rss.xml"},
]

ECONOMY_KEYWORDS: list[str] = [
    "業績予想",
    "上方修正",
    "下方修正",
    "自己株式",
    "自社株買い",
    "公開買付け",
    "TOB",
    "合併",
    "買収",
    "特別損失",
    "減損",
    "増資",
    "第三者割当",
    "上場廃止",
]

POLICY_KEYWORDS: list[str] = [
    "防衛",
    "予算",
    "補正予算",
    "規制",
    "法改正",
    "閣議決定",
    "日銀",
    "金利",
    "利上げ",
    "利下げ",
    "消費税",
    "税制",
    "エネルギー",
    "半導体",
    "安全保障",
]

IMPORTANT_KEYWORDS: list[str] = ECONOMY_KEYWORDS + POLICY_KEYWORDS

# 直近何時間分を対象にするか
HOURS_LOOKBACK = 6

GEMINI_MODELS = (
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
)

GEMINI_PROMPT = """あなたはニュース解説者です。中学生でも理解できる言葉だけを使ってください。
次の一次情報について、必ず次の形式だけで答えてください。余計な前置きは不要です。

【一言で言うと】
（30文字以内）

【どういうこと？】
（3〜5行で中学生でもわかる説明。難しい言葉は使わない）

【なぜ大事？】
（1〜2行）

---
情報源: {source}
タイトル: {title}
要約: {summary}
"""


def load_dotenv(path: Path) -> None:
    """pip不要の簡易 .env 読み込み（ローカル実行用）。"""
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


TEST_ITEM: dict[str, Any] = {
    "source": "テスト",
    "title": "【テスト】日銀が政策金利を見直す可能性を示唆",
    "summary": "日本銀行が今後の金融政策について、金利の調整を検討する姿勢を示したというテスト用の架空ニュースです。",
    "link": "https://github.com/kitasan999/primary-info-bot",
}


def log(message: str) -> None:
    print(message, flush=True)


def get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"環境変数 {name} が未設定です")
    return value


def parse_entry_time(entry: dict[str, Any]) -> datetime | None:
    """RSSエントリの公開日時を UTC の datetime に変換する。"""
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue

    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def entry_text(entry: dict[str, Any]) -> str:
    """タイトルと要約を結合したテキスト。"""
    title = entry.get("title", "") or ""
    summary = entry.get("summary", "") or entry.get("description", "") or ""
    return f"{title}\n{summary}"


def matches_keywords(text: str) -> bool:
    return any(keyword in text for keyword in IMPORTANT_KEYWORDS)


def fetch_recent_entries(feed_info: dict[str, str], cutoff: datetime) -> list[dict[str, Any]]:
    """1つのフィードから、指定期間内かつキーワード一致のエントリを返す。"""
    results: list[dict[str, Any]] = []
    try:
        parsed = feedparser.parse(feed_info["url"])
    except Exception as exc:
        log(f"[警告] {feed_info['name']} の取得に失敗: {exc}")
        return results

    if getattr(parsed, "bozo", False) and not parsed.entries:
        log(f"[警告] {feed_info['name']} のパースに問題がありました")

    for entry in parsed.entries:
        published = parse_entry_time(entry)
        if published and published < cutoff:
            continue

        text = entry_text(entry)
        if not matches_keywords(text):
            continue

        link = entry.get("link", "") or ""
        results.append(
            {
                "source": feed_info["name"],
                "title": (entry.get("title") or "").strip(),
                "summary": (entry.get("summary") or entry.get("description") or "").strip(),
                "link": link,
                "published": published,
            }
        )
    return results


def generate_explanation(api_key: str, item: dict[str, Any]) -> str:
    """Gemini で中学生向け解説を生成する。"""
    genai.configure(api_key=api_key)

    prompt = GEMINI_PROMPT.format(
        source=item["source"],
        title=item["title"],
        summary=item["summary"] or "（要約なし）",
    )

    last_error = ""
    for model_name in GEMINI_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = (response.text or "").strip()
            if text:
                return text
            last_error = f"{model_name}: 空の応答"
        except Exception as exc:
            last_error = f"{model_name}: {exc}"
            continue

    raise RuntimeError(f"Gemini 解説の生成に失敗しました（{last_error}）")


def format_discord_message(item: dict[str, Any], explanation: str) -> str:
    """Discord Webhook 用のテキストメッセージを組み立てる。"""
    lines = [
        "【重要一次情報】",
        item["title"],
        "",
        explanation,
        "",
        f"元の発表 → {item['link']}",
    ]
    message = "\n".join(lines)
    # Discord content の上限は 2000 文字
    if len(message) > 1900:
        message = message[:1897] + "..."
    return message


def send_discord(webhook_url: str, content: str) -> None:
    response = requests.post(
        webhook_url,
        json={"content": content},
        timeout=30,
    )
    response.raise_for_status()


def collect_items(cutoff: datetime) -> list[dict[str, Any]]:
    """全フィードから対象エントリを集める。個別エラーは握りつぶして続行。"""
    items: list[dict[str, Any]] = []
    for feed in FEEDS:
        try:
            entries = fetch_recent_entries(feed, cutoff)
            items.extend(entries)
            log(f"{feed['name']}: {len(entries)} 件が条件に一致")
        except Exception as exc:
            log(f"[警告] {feed['name']} の処理中にエラー: {exc}")
    return items


def run_test(webhook_url: str, gemini_api_key: str) -> int:
    """Discord と Gemini の接続テスト（架空ニュースを1件送る）。"""
    log("テストモード: 架空ニュースを1件 Discord に送ります")
    try:
        explanation = generate_explanation(gemini_api_key, TEST_ITEM)
        message = format_discord_message(TEST_ITEM, explanation)
        send_discord(webhook_url, message)
        log("テスト通知を Discord に送信しました。チャンネルを確認してください。")
        return 0
    except Exception as exc:
        log(f"[エラー] テスト送信に失敗: {exc}")
        return 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="一次情報を Discord に通知")
    parser.add_argument(
        "--test",
        action="store_true",
        help="架空ニュース1件で Discord / Gemini の接続テスト",
    )
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    try:
        webhook_url = get_env("DISCORD_WEBHOOK_URL")
        gemini_api_key = get_env("GEMINI_API_KEY")
    except RuntimeError as exc:
        log(f"[エラー] {exc}")
        return 1

    if args.test:
        return run_test(webhook_url, gemini_api_key)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_LOOKBACK)
    log(f"対象期間: {cutoff.isoformat()} 以降（直近 {HOURS_LOOKBACK} 時間）")

    items = collect_items(cutoff)
    if not items:
        log("重要な新着はありませんでした。通知は送りません。")
        return 0

    log(f"通知対象: {len(items)} 件")

    sent = 0
    for item in items:
        try:
            explanation = generate_explanation(gemini_api_key, item)
            message = format_discord_message(item, explanation)
            send_discord(webhook_url, message)
            sent += 1
            log(f"送信完了: {item['title'][:60]}")
        except Exception as exc:
            log(f"[警告] 通知をスキップ ({item['title'][:40]}...): {exc}")

    log(f"完了: {sent}/{len(items)} 件を Discord に送信しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
