"""RSSフィードから記事を取得する"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import feedparser


def fetch_rss(source: dict[str, Any]) -> list[dict[str, Any]]:
    """sources.yaml の1件分のRSSを読み、記事リストを返す"""
    feed = feedparser.parse(source["url"])

    if feed.bozo and not feed.entries:
        raise RuntimeError(f"RSS取得失敗: {source['id']} ({feed.bozo_exception})")

    articles = []
    for entry in feed.entries:
        published = _parse_date(entry)
        articles.append(
            {
                "title": (entry.get("title") or "").strip(),
                "url": (entry.get("link") or "").strip(),
                "published": published,
                "summary": (entry.get("summary") or entry.get("description") or "").strip(),
                "source_id": source["id"],
                "source_name": source["name"],
                "genre": source.get("genre", "その他"),
                "priority": source.get("priority", "normal"),
            }
        )
    return articles


def _parse_date(entry: Any) -> str:
    """公開日時を ISO形式文字列に変換"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return datetime.now(timezone.utc).isoformat()
