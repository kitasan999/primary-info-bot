"""Gemini失敗時の自動要約（フォールバック）"""

from __future__ import annotations

import re
from typing import Any

from notify.format_parts import short_display_title


def _agency_label(article: dict[str, Any]) -> str:
    name = article.get("source_name", "")
    if "金融庁" in name:
        return "金融庁"
    if "日本銀行" in name:
        return "日銀"
    if "財務省" in name:
        return "財務省"
    if "厚生" in name:
        return "厚労省"
    return name.split()[0] if name else "公式"


def apply_fallback_summary(
    summary: dict[str, Any],
    article: dict[str, Any],
    body: str = "",
) -> None:
    title = article.get("title", "")
    dec = article.get("decision_status", {})
    dec_type = dec.get("type", "")
    body = body or article.get("body_for_score", "") or article.get("summary", "")
    agency = _agency_label(article)

    summary["easy_title"] = short_display_title(title)
    url = article.get("url", "")

    from process.body_summary import apply_body_summary, summarize_from_body

    body_parsed = summarize_from_body(body, title, url, agency)
    if body_parsed and apply_body_summary(summary, body_parsed):
        summary["gemini_followup"] = ""
        summary["content_category"] = "knowledge" if dec_type == "info" else summary.get("content_category", "")
        summary["ai_used"] = False
        summary["ai_status"] = "page"
        return

    from process.title_summary import apply_title_summary

    if apply_title_summary(summary, article, agency):
        summary["gemini_followup"] = ""
        summary["content_category"] = "knowledge" if dec_type == "info" else summary.get("content_category", "")
        summary["ai_used"] = False
        summary["ai_status"] = "title_only"
        return

    body_hint = _extract_body_hint(body, title)

    if dec_type == "info" or "更新" in title:
        summary["what_changed"] = body_hint or "最新データや資料が追加された。新ルールは決まっていない。"
        summary["gemini_action"] = "様子見でOK（急いで動く必要なし）"
        summary["gemini_impact"] = ""
        summary["one_line"] = _info_one_line(title, body_hint, agency)
        summary["gemini_relevance"] = _info_relevance(title)
    elif dec_type == "decided":
        summary["what_changed"] = body_hint or "新しい公式発表。内容を確認。"
        summary["gemini_action"] = "リンク先で要点を確認"
        summary["gemini_impact"] = "生活や資産運用に影響が出る可能性あり。"
        summary["one_line"] = body_hint or f"{agency}から「{summary['easy_title']}」の発表。"
        summary["gemini_relevance"] = "お金・税制・投資に関係する可能性があるので、要点だけ確認。"
    else:
        summary["gemini_action"] = "様子見でOK"
        summary["gemini_impact"] = ""
        summary["one_line"] = body_hint or f"{agency}から「{summary['easy_title']}」のお知らせ。"
        summary["gemini_relevance"] = "大きな変更ではなさそう。気になったらリンクを見る。"

    if "公式発表を出しました" in summary.get("one_line", ""):
        summary["one_line"] = _info_one_line(title, body_hint, agency)

    summary["gemini_followup"] = ""
    summary["content_category"] = "knowledge" if dec_type == "info" else summary.get("content_category", "")
    summary["ai_used"] = False
    summary["ai_status"] = "skipped"


def _info_one_line(title: str, body_hint: str, agency: str) -> str:
    if body_hint:
        return body_hint
    if "NISA" in title.upper() or "ニーサ" in title or "つみたて" in title:
        return f"{agency}がNISA・つみたて投資に関する情報を発表した。"
    if "税" in title:
        return f"{agency}が税制に関する情報を発表した。"
    if "金利" in title or "金融政策" in title:
        return f"{agency}が金利・金融政策に関する情報を発表した。"
    if "コロナ" in title or "新型" in title:
        return "厚労省が新型コロナの最新データ・資料を更新した。"
    if "インフル" in title:
        return "厚労省がインフルエンザ関連の最新情報を更新した。"
    return f"{agency}が{short_display_title(title)}。"


def _info_relevance(title: str) -> str:
    if any(w in title for w in ("NISA", "ニーサ", "つみたて", "投資")):
        return "NISA・投資のルールや制度変更の可能性。自分の口座に関係するか確認。"
    if "税" in title:
        return "税金のルール変更の可能性。確定申告や控除に関係するか確認。"
    if any(w in title for w in ("金利", "金融政策", "日銀")):
        return "金利・物価に関係。ローンや貯金の金利に影響することがある。"
    if any(w in title for w in ("コロナ", "インフル", "感染")):
        return "感染記録や記入ルールは変わらない。数字・資料の更新だけ。"
    return "資料の数字更新。今日から現場のやり方が変わる話ではない。"


def _extract_body_hint(body: str, title: str) -> str:
    if not body:
        return ""

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in body.splitlines()]
    lines = [ln for ln in lines if len(ln) >= 12]

    for ln in lines[:12]:
        if ln == title or title in ln:
            continue
        if any(skip in ln for skip in ("ホーム", "政策について", "一覧", "PDF", "ダウンロード")):
            continue
        if re.search(r"(更新|公表|発表|報道|推移|定点|週|月)", ln):
            return _simplify_line(ln, title)

    for ln in lines[:8]:
        if len(ln) >= 20 and title not in ln:
            return _simplify_line(ln, title)
    return ""


def _simplify_line(line: str, title: str) -> str:
    if "コロナ" in title or "コロナ" in line:
        return "新型コロナの発生状況・検疫・変異株など、最新資料が更新された。"
    if "インフル" in title or "インフル" in line:
        return "インフルエンザの最新データ・資料が更新された。"
    if "報道発表資料" in line:
        return "公式資料の内容が更新された。"
    return _trim(line, 72)


def _trim(text: str, max_len: int) -> str:
    text = text.strip()
    if not text.endswith("。"):
        text += "。"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
