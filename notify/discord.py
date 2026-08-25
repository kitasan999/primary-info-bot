"""Discord Webhook で通知する"""

from __future__ import annotations

import os
from typing import Any

import requests

from notify.base import format_message


def get_webhook_url() -> str:
    return os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


def send_raw_message(message: str) -> None:
    """任意テキストを Discord に送る（テスト用）"""
    webhook_url = get_webhook_url()
    if not webhook_url:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL が未設定です。\n"
            "  方法1: .env ファイルに DISCORD_WEBHOOK_URL=... と書く\n"
            "  方法2: PowerShell で $env:DISCORD_WEBHOOK_URL = \"URL\" と設定"
        )
    payload = {"content": message[:2000]}
    response = requests.post(webhook_url, json=payload, timeout=15)
    response.raise_for_status()


def send_discord(articles: list[dict[str, Any]]) -> bool:
    """新着記事を Discord に送る。Webhook未設定なら False"""
    if not get_webhook_url():
        return False

    for article in articles:
        send_raw_message(format_message(article))

    return True


def print_notifications(articles: list[dict[str, Any]]) -> None:
    """Webhookがないとき用：ターミナルに表示"""
    for article in articles:
        print("--- 新着 ---")
        print(format_message(article))
        print()
