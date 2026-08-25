"""重要度スコアを計算する"""

from __future__ import annotations

from typing import Any

PRIORITY_SCORE = {"high": 3, "normal": 1, "low": 0}
KEYWORD_SCORE = {"high": 2, "normal": 1}


def score_article(article: dict[str, Any], keywords: dict[str, list[str]]) -> dict[str, Any]:
    """ルールベースで重要度スコアを付ける"""
    score = PRIORITY_SCORE.get(article.get("priority", "normal"), 1)
    title = article.get("title", "")

    for level, words in keywords.items():
        for word in words:
            if word in title:
                score += KEYWORD_SCORE.get(level, 0)

    if score >= 5:
        label = "高"
    elif score >= 2:
        label = "中"
    else:
        label = "低"

    article["score"] = score
    article["score_label"] = label
    return article
