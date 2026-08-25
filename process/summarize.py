"""本文から中学生向けのやさしい要約を作る"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 難しい言葉 → やさしい言葉
_SIMPLE_WORDS: list[tuple[str, str]] = [
    ("厚生労働省", "厚労省"),
    ("労働政策審議会", "仕事のルールを話し合う専門家の会"),
    ("審議会", "専門家の会"),
    ("分科会", "小さな分野の会議"),
    ("報道発表", "公式発表"),
    ("公表", "発表"),
    ("実施", "行う"),
    ("開催いたします", "開きます"),
    ("通知いたします", "お知らせします"),
    ("ペーパーレス", "紙を使わない"),
    ("雇用環境", "職場の環境"),
    ("労働者", "働く人"),
    ("事業者", "会社・事業所"),
]

_DATE_LINE = re.compile(
    r"(令和|平成)?\s*(\d+)年\s*(\d+)月\s*(\d+)日.*?(\d{1,2})[:：](\d{2})?\s*[～~\-ー]\s*(\d{1,2})[:：](\d{2})?"
)
_SIMPLE_DATE = re.compile(r"(\d+)月(\d+)日")
_AGENDA = re.compile(r"[（(]([０-９0-9]+)[）)](.+?)(?=[（(]|$)")


def summarize_easy(title: str, body: str) -> dict[str, Any]:
    """タイトル＋本文から、やさしい要約を作る"""
    body = _simplify_text(body)
    title_simple = _simplify_text(title)

    when = _extract_when(body) or _extract_when(title)
    where = _extract_where(body)
    agenda = _extract_agenda(body)
    lead = _extract_lead_sentence(body, title)

    one_line = _build_one_line(title_simple, when, where, agenda, lead)
    bullets = _build_bullets(when, where, agenda, lead)

    return {
        "easy_title": _short_title(title_simple),
        "one_line": one_line,
        "bullets": bullets,
    }


def _simplify_text(text: str) -> str:
    result = text.strip()
    for old, new in _SIMPLE_WORDS:
        result = result.replace(old, new)
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def _short_title(title: str) -> str:
    text = re.sub(r"（[^）]*）", "", title)
    text = re.sub(r"を(開催|公表|発表|通知)します", "", text)
    text = re.sub(r"\s+", "", text)
    if len(text) > 40:
        return text[:39] + "…"
    return text


def _extract_when(text: str) -> str | None:
    # 「１．日時」などのブロックを優先
    block = re.search(r"日時[　\s]*(.{8,60})", text)
    if block:
        segment = block.group(1)
        m = _DATE_LINE.search(segment)
        if m:
            month, day = m.group(3), m.group(4)
            start_h, start_m = m.group(5), m.group(6) or "00"
            end_h, end_m = m.group(7), m.group(8) or "00"
            return f"{month}月{day}日 {start_h}:{start_m}〜{end_h}:{end_m}"
        m2 = _SIMPLE_DATE.search(segment)
        if m2:
            return f"{m2.group(1)}月{m2.group(2)}日"

    m = _DATE_LINE.search(text)
    if m:
        month, day = m.group(3), m.group(4)
        start_h, start_m = m.group(5), m.group(6) or "00"
        end_h, end_m = m.group(7), m.group(8) or "00"
        return f"{month}月{day}日 {start_h}:{start_m}〜{end_h}:{end_m}"

    return None


def _extract_where(text: str) -> str | None:
    m = re.search(r"場所[　\s]*(.{5,45}?)(?=議題|３\.|3\.|$)", text)
    if m:
        return _trim(m.group(1).strip(" 　:："), 35)
    m2 = re.search(r"会場[　\s]*(.{5,45})", text)
    if m2:
        return _trim(m2.group(1).strip(" 　:："), 35)
    return None


def _extract_agenda(text: str) -> list[str]:
    items = []
    block = re.search(r"議題[（(]?(?:予定)?[）)]?(.*)", text)
    if not block:
        return items
    tail = block.group(1)[:400]
    for m in _AGENDA.finditer(tail):
        topic = _simplify_text(m.group(2))
        if len(topic) >= 4:
            items.append(_trim(topic, 28))
        if len(items) >= 3:
            break
    return items


def _extract_lead_sentence(body: str, title: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if len(line) < 15:
            continue
        if line == title or title in line:
            continue
        if "について" in line or "お知らせ" in line or "開催" in line:
            return _trim(_simplify_text(line), 80)
    sentences = re.split(r"[。．!！?？]", body)
    for s in sentences:
        s = s.strip()
        if len(s) >= 15:
            return _trim(_simplify_text(s), 80)
    return ""


def _build_one_line(title: str, when: str | None, where: str | None, agenda: list[str], lead: str) -> str:
    if "開催" in title or "会議" in title or "専門家の会" in title:
        if when:
            return f"厚労省が、{when}に専門家の会議を開く予定です。"
        return "厚労省が、専門家の会議を開く予定です。"

    if "更新" in title or "推移" in title or "資料" in title:
        if "コロナ" in title or "新型" in title:
            return "厚労省が新型コロナの最新データ・資料を更新した。"
        if "インフル" in title:
            return "厚労省がインフルエンザ関連の最新情報を更新した。"
        return f"厚労省が「{_short_title(title)}」の資料を更新した。"

    if "報道発表" in title or "公式発表" in title:
        return f"厚労省から「{_short_title(title)}」の公式発表。"

    if lead:
        return _trim(lead + "。", 90)

    return _trim(f"厚労省から「{_short_title(title)}」のお知らせです。", 90)


def _build_bullets(
    when: str | None,
    where: str | None,
    agenda: list[str],
    lead: str,
) -> list[str]:
    bullets: list[str] = []
    if when:
        bullets.append(f"📅 いつ：{when}")
    if where:
        bullets.append(f"📍 どこ：{where}")
    if agenda:
        bullets.append("📝 話題：" + " / ".join(agenda[:2]))
    elif lead:
        bullets.append(f"📝 内容：{_trim(lead, 50)}")
    bullets.append("🔗 くわしく：下のタイトルをタップ")
    return bullets[:4]


def _trim(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def enrich_article(
    article: dict[str, Any],
    body_text: str | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """記事に easy_summary を付ける"""
    from fetch.page_fetcher import fetch_page_text

    body = body_text
    if body is None and article.get("url"):
        try:
            body = fetch_page_text(article["url"])
        except Exception:
            body = article.get("summary", "")

    article["body_for_score"] = body or ""

    if "decision_status" not in article:
        from process.decision_status import classify_decision_status

        article["decision_status"] = classify_decision_status(article)

    profile = profile or {}

    from process.nisa_diff import apply_nisa_diff, is_nisa_product_page

    if is_nisa_product_page(article.get("title", ""), article.get("url", "")):
        try:
            if apply_nisa_diff(article, profile, DATA_DIR):
                from process.category import classify_content_type

                classify_content_type(article)
                return article
        except Exception:
            pass

    summary = summarize_easy(article.get("title", ""), body or "")

    from process.gemini_summary import get_api_key, summarize_with_gemini

    gemini = summarize_with_gemini(article, body or "", profile)
    if gemini:
        if gemini.get("short_title"):
            summary["easy_title"] = gemini["short_title"]
        summary["one_line"] = gemini.get("one_line") or summary.get("one_line")
        summary["what_changed"] = gemini.get("what_changed", "")
        summary["gemini_impact"] = gemini.get("impact", "")
        summary["gemini_action"] = gemini.get("action_today", "")
        summary["gemini_relevance"] = gemini.get("relevance_line", "")
        summary["content_category"] = gemini.get("content_category", "")
        summary["category_reason"] = gemini.get("category_reason", "")
        summary["gemini_followup"] = gemini.get("followup_question", "")
        summary["ai_used"] = True
        summary["ai_status"] = "ok"
    else:
        from process.fallback_summary import apply_fallback_summary

        apply_fallback_summary(summary, article, body or "")
        if summary.get("ai_status") not in ("page", "title_only"):
            if get_api_key():
                summary["ai_status"] = "failed"
            else:
                summary["ai_status"] = "no_key"

    article["easy_summary"] = summary

    from process.category import classify_content_type

    classify_content_type(article)
    return article
