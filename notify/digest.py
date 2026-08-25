"""まとめ通知フォーマット"""

from __future__ import annotations

from typing import Any

from process.category import CATEGORIES
from process.quality_gate import unique_by_display_title
from process.topic_dedupe import clean_detail_text


def _article_detail(art: dict[str, Any]) -> str:
    summary = art.get("easy_summary", {})
    for field in ("what_changed", "one_line", "gemini_impact"):
        text = clean_detail_text(summary.get(field, ""))
        if text:
            return text
    return clean_detail_text(art.get("title", ""))[:60]


def format_digest_embed(articles: list[dict[str, Any]], merged_count: int = 0) -> dict[str, Any]:
    """複数記事を1つのDiscord Embedにまとめる"""
    articles = unique_by_display_title(articles)
    grouped: dict[str, list[dict[str, Any]]] = {"money": [], "action": [], "knowledge": []}
    for art in articles:
        cat = art.get("content_type", {}).get("type", "knowledge")
        grouped.setdefault(cat, []).append(art)

    sections = []
    for cat_id in ("money", "action", "knowledge"):
        items = grouped.get(cat_id, [])
        if not items:
            continue
        meta = CATEGORIES[cat_id]
        lines = [f"**{meta['label']}** _{meta['hint']}_"]
        for art in items:
            summary = art.get("easy_summary", {})
            title = summary.get("easy_title") or art.get("title", "")[:30]
            detail = _article_detail(art)
            url = art.get("url", "")
            extra = ""
            if art.get("merged_count", 1) > 1:
                extra = f"（同トピック{art['merged_count']}件を統合）"
            lines.append(f"• [{title}]({url}){extra}\n  {detail}")
        sections.append("\n".join(lines))

    intro = f"**{len(articles)}トピックの新着**"
    if merged_count > 0:
        intro += f"\n（似た話題 {merged_count} 件を統合してスッキリ表示）"
    else:
        intro += f"\n（{len(articles)}件を1通にまとめました）"

    description = intro + "\n\n" + "\n\n".join(sections)

    has_money = bool(grouped.get("money"))
    has_action = bool(grouped.get("action"))
    color = 0xE74C3C if has_money or has_action else 0x3498DB

    return {
        "title": f"📬 新着まとめ（{len(articles)}トピック）",
        "description": description[:4096],
        "color": color,
        "footer": {"text": "詳細は各リンクから · 優先: お金 → 現場対応 → 知っておく"},
    }


def format_digest_terminal(articles: list[dict[str, Any]]) -> str:
    lines = [f"=== まとめ通知（{len(articles)}件）==="]
    for art in articles:
        ct = art.get("content_type", {})
        summary = art.get("easy_summary", {})
        lines.append(f"{ct.get('label', '')} {summary.get('easy_title', art.get('title', '')[:30])}")
        lines.append(f"  {summary.get('what_changed') or summary.get('one_line', '')}")
        lines.append(f"  {art.get('url', '')}")
    return "\n".join(lines)
