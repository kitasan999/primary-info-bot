"""通知メッセージの共通フォーマット"""

from __future__ import annotations

from typing import Any


def format_message(article: dict[str, Any]) -> str:
    """Discord等に送る1件分のテキスト"""
    published = article.get("published", "")[:16].replace("T", " ")
    lines = [
        f"[{article.get('genre', 'その他')}][重要度:{article.get('score_label', '中')}] {article.get('title', '')}",
        article.get("url", ""),
        f"出典: {article.get('source_name', '')}",
        published,
    ]
    return "\n".join(line for line in lines if line)
