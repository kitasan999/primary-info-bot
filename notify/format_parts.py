"""Discord通知用テキスト組み立て（重複除去）"""

from __future__ import annotations

import re
from typing import Any


def short_display_title(title: str) -> str:
    """Discordタイトル用の短い見出し"""
    if "新型コロナ" in title:
        return "新型コロナ資料の更新"
    if "NISA" in title.upper() or "ニーサ" in title or "つみたて" in title:
        return "NISA・つみたて関連"
    if "税" in title and "検討" not in title:
        return "税制関連の発表"
    if "金利" in title or "金融政策" in title:
        return "金利・金融政策"
    if "インフルエンザ" in title:
        return "インフルエンザ情報の更新"
    if "感染症" in title:
        return "感染症関連の更新"

    text = title
    for suffix in (
        "に関する報道発表資料を更新しました",
        "に関する報道発表",
        "の推移等を更新しました",
        "を更新しました",
        "について",
    ):
        text = text.replace(suffix, "")
    text = re.sub(r"\s+", "", text).strip("　 ")
    if len(text) > 28:
        return text[:27] + "…"
    return text or title[:28]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text).lower())


def _similar(a: str, b: str, threshold: float = 0.55) -> bool:
    if not a or not b:
        return False
    na, nb = _normalize(a), _normalize(b)
    if na in nb or nb in na:
        return True
    # 短い方の文字の半分以上が長い方に含まれる
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(short) < 8:
        return short in long
    hit = sum(1 for i in range(len(short) - 1) if short[i : i + 2] in long)
    return hit / max(len(short) - 1, 1) >= threshold


def build_embed_parts(article: dict[str, Any]) -> list[str]:
    """重複のないEmbed本文パーツを返す"""
    summary = article.get("easy_summary", {})
    dec = article.get("decision_status", {})
    rel = article.get("relevance", {})
    ct = article.get("content_type", {})

    header = f"{dec.get('label', '')} ｜ {rel.get('relevance_label', '')} ｜ {ct.get('label', '')}"
    parts: list[str] = [f"**{header}**"]

    merged = article.get("merged_count", 1)
    if merged > 1:
        parts.append(f"_同じ話題 {merged}件を1つにまとめて表示_")

    relevance = (summary.get("gemini_relevance") or rel.get("relevance_reason") or "").strip()
    dec_hint = dec.get("hint", "")
    if relevance and not _similar(relevance, dec_hint):
        parts.append(f"**自分に関係ある？**\n{relevance}")

    one_line = (summary.get("one_line") or "").strip()
    what_changed = (summary.get("what_changed") or "").strip()
    impact = (summary.get("gemini_impact") or "").strip()
    action = (summary.get("gemini_action") or "").strip()

    cat_type = ct.get("type", "knowledge")
    dec_type = dec.get("type", "")

    if what_changed and not _similar(what_changed, relevance):
        if not _similar(what_changed, one_line):
            parts.append(f"**📌 変更点**\n{what_changed}")

    if one_line:
        parts.append(f"**📝 要約**\n{one_line}")
    elif what_changed:
        parts.append(f"**📝 要約**\n{what_changed}")

    if impact and not _similar(impact, one_line) and not _similar(impact, action):
        if cat_type == "money" or (cat_type != "knowledge" and dec_type != "info"):
            parts.append(f"**🏠 影響**\n{impact}")

    if action:
        parts.append(f"**✅ 今日やること**\n{action}")

    hits = summary.get("holding_hits") or []
    missing = summary.get("holding_missing") or []
    if hits:
        parts.append("**🏦 あなたの保有**\n対象のまま: " + " / ".join(hits[:4]))
    if missing:
        parts.append("**⚠️ 一覧に見つからない保有**\n" + " / ".join(missing[:4]))

    added = summary.get("added_preview") or ""
    removed = summary.get("removed_preview") or ""
    if added:
        parts.append(f"**➕ 追加**\n{added}")
    if removed:
        parts.append(f"**➖ 除外**\n{removed}")

    if summary.get("ai_used") and summary.get("gemini_followup"):
        parts.append(f"**💬 もっと知りたいとき**\n{summary['gemini_followup']}")

    return [p for p in parts if p]


def ai_footer_note(summary: dict[str, Any]) -> str:
    status = summary.get("ai_status", "")
    if status == "diff":
        return "Excel差分＋保有照合"
    if status == "page":
        return "ページ本文から要約"
    if status == "title_only":
        return "タイトルのみ（本文薄い/PDF）"
    if status == "title":
        return "タイトルから要約"
    if status == "failed":
        return "自動要約（AI混雑のため）"
    if status == "no_key":
        return "自動要約（GEMINI_API_KEY未設定）"
    if summary.get("ai_used"):
        return "AI要約"
    return "自動要約"
