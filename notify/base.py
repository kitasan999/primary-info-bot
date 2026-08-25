"""通知メッセージの共通フォーマット"""

from __future__ import annotations

from typing import Any

from notify.format_parts import ai_footer_note, build_embed_parts, short_display_title


def format_published(iso: str) -> str:
    if not iso:
        return "日時不明"
    return iso[:16].replace("T", " ")


def _status_color(article: dict[str, Any]) -> int:
    dtype = article.get("decision_status", {}).get("type", "")
    cat = article.get("content_type", {}).get("type", "")
    if cat == "money":
        return 0xE74C3C
    if cat == "action" or dtype == "decided":
        return 0x2ECC71
    if dtype == "discussing":
        return 0xF39C12
    if dtype == "info":
        return 0x3498DB
    return 0x95A5A6


def _badge_line(article: dict[str, Any]) -> str:
    dec = article.get("decision_status", {})
    rel = article.get("relevance", {})
    ct = article.get("content_type", {})
    return f"{dec.get('label', '')} ｜ {rel.get('relevance_label', '')} ｜ {ct.get('label', '')}"


def format_message(article: dict[str, Any]) -> str:
    summary = article.get("easy_summary", {})
    lines = [_badge_line(article)]

    for part in build_embed_parts(article)[1:]:
        lines.append(part.replace("\n", " — ", 1) if part.startswith("**") else part)

    note = ai_footer_note(summary)
    if note:
        lines.append(f"（{note}）")

    lines.append(article.get("url", ""))
    return "\n".join(line for line in lines if line)


def format_discord_embed(article: dict[str, Any]) -> dict[str, Any]:
    summary = article.get("easy_summary", {})
    dec = article.get("decision_status", {})
    rel = article.get("relevance", {})

    title = summary.get("easy_title") or short_display_title(article.get("title", ""))
    description = "\n\n".join(build_embed_parts(article))

    footer_text = (
        f"{article.get('source_name', '')} · {format_published(article.get('published', ''))}"
        f" · {ai_footer_note(summary)} · タップで原文"
    )

    embed: dict[str, Any] = {
        "title": title[:256],
        "url": article.get("url", ""),
        "description": description[:4096],
        "color": _status_color(article),
        "fields": [
            {"name": "状態", "value": _status_field(dec), "inline": True},
            {"name": "関連度", "value": f"{rel.get('relevance_score', 0)}/10", "inline": True},
        ],
        "footer": {"text": footer_text[:256]},
    }
    return embed


def _status_field(dec: dict[str, Any]) -> str:
    mapping = {
        "decided": "決定・公表",
        "discussing": "協議中",
        "info": "資料更新",
        "unknown": "要確認",
    }
    return mapping.get(dec.get("type", ""), "—")
