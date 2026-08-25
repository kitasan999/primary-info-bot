"""Discord Webhook で通知する"""

from __future__ import annotations

import os
from typing import Any

import requests

from notify.base import format_discord_embed, format_message
from notify.digest import format_digest_embed, format_digest_terminal
from process.category import sort_by_category
from process.quality_gate import unique_by_display_title
from process.topic_dedupe import merge_same_topic


def get_webhook_url() -> str:
    return os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


def send_embed(article: dict[str, Any]) -> None:
    webhook_url = get_webhook_url()
    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL が未設定です")

    embed = format_discord_embed(article)
    payload = {"embeds": [embed]}
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


def send_digest(articles: list[dict[str, Any]], merged_count: int = 0) -> None:
    webhook_url = get_webhook_url()
    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL が未設定です")

    embed = format_digest_embed(articles, merged_count)
    payload = {"embeds": [embed], "content": "📬 **一次情報 新着まとめ**"}
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


def send_raw_message(message: str) -> None:
    webhook_url = get_webhook_url()
    if not webhook_url:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL が未設定です。\n"
            "  方法1: .env ファイルに DISCORD_WEBHOOK_URL=... と書く\n"
            "  方法2: PowerShell で $env:DISCORD_WEBHOOK_URL = \"URL\" と設定"
        )

    embed = {
        "title": "接続テストOK",
        "description": "厚労省ボット → Discord の通知経路は正常です。",
        "color": 0x2ECC71,
        "fields": [
            {"name": "次に起きること", "value": "新着が多い日はまとめ通知、少ない日は1件ずつ届きます", "inline": False}
        ],
    }
    payload = {"embeds": [embed], "content": "✅ **テスト通知**"}
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


def send_discord(
    articles: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    merged_count: int = 0,
) -> bool:
    if not get_webhook_url():
        return False

    profile = profile or {}
    threshold = profile.get("digest_threshold", 3)
    articles, extra = merge_same_topic(articles)
    articles = unique_by_display_title(articles)
    articles = sort_by_category(articles)
    merged_count += extra

    if not articles:
        return False

    if len(articles) > threshold:
        send_digest(articles, merged_count)
    else:
        for article in articles:
            send_embed(article)

    return True


def print_notifications(articles: list[dict[str, Any]], profile: dict[str, Any] | None = None) -> None:
    profile = profile or {}
    threshold = profile.get("digest_threshold", 3)
    articles = sort_by_category(articles)

    if len(articles) > threshold:
        print(format_digest_terminal(articles))
        return

    for article in articles:
        print("--- 新着 ---")
        print(format_message(article))
        print()
