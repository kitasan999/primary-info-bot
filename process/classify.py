"""ジャンル分類（ソース設定 + キーワード補正）"""

from __future__ import annotations

from typing import Any


def classify_article(article: dict[str, Any], keywords: dict[str, list[str]]) -> dict[str, Any]:
    """タイトルからジャンルを補正する（必要なときだけ）"""
    title = article.get("title", "")
    genre = article.get("genre", "その他")

    if any(k in title for k in ("感染", "新型", "インフル", "ワクチン")):
        genre = "災害・防災"
    elif any(k in title for k in ("AI", "人工知能", "デジタル")):
        genre = "AI"

    article["genre"] = genre
    return article
