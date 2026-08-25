"""既読記事の重複を除去する"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def filter_new_articles(
    articles: list[dict[str, Any]],
    seen_ids: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """未読だけ返し、seen_ids を更新する"""
    new_articles = []
    now = datetime.now(timezone.utc).isoformat()

    for article in articles:
        article_id = article["id"]
        if article_id in seen_ids:
            continue
        seen_ids[article_id] = {
            "url": article["url"],
            "title": article["title"],
            "first_seen": now,
        }
        new_articles.append(article)

    return new_articles, seen_ids


def cleanup_seen_ids(seen_ids: dict[str, Any], days: int = 30) -> dict[str, Any]:
    """古い既読データを削除してファイル肥大を防ぐ"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cleaned = {}

    for article_id, meta in seen_ids.items():
        first_seen = meta.get("first_seen", "")
        try:
            dt = datetime.fromisoformat(first_seen)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt >= cutoff:
            cleaned[article_id] = meta

    return cleaned
