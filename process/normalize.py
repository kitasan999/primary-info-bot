"""記事データの共通フォーマットに整える"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """重複判定用にURLを整える（utm等の不要パラメータを除去）"""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=False)
    for key in list(query.keys()):
        if key.lower().startswith("utm_") or key.lower() in ("fbclid", "ref"):
            del query[key]
    clean_query = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, ""))


def make_article_id(url: str, title: str, source_id: str) -> str:
    """記事の一意IDを作る"""
    key = f"{normalize_url(url)}|{title.strip()}|{source_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def normalize_article(raw: dict[str, Any]) -> dict[str, Any]:
    """fetcher が返した生データを共通形式にする"""
    url = normalize_url(raw.get("url", ""))
    title = raw.get("title", "").strip()
    source_id = raw.get("source_id", "")

    return {
        "id": make_article_id(url, title, source_id),
        "title": title,
        "url": url,
        "published": raw.get("published", ""),
        "summary": _clean_summary(raw.get("summary", "")),
        "source_id": source_id,
        "source_name": raw.get("source_name", ""),
        "genre": raw.get("genre", "その他"),
        "priority": raw.get("priority", "normal"),
    }


def _clean_summary(text: str, max_len: int = 200) -> str:
    """HTMLタグを除去して短くする"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text
