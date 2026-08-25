"""通知して意味があるか（商品レベル）を判定する"""

from __future__ import annotations

import re
from typing import Any

_THIN_MONEY = (
    "銘柄別残高",
    "国債金利情報",
    "DPS",
    "日銀レビュー",
    "論文",
    "職員を募集",
    "ファイナンス",
    "広報誌",
    "発行予定額",
    "物価連動国債",
    "利付国債",
    "国債の発行",
    "入札",
    "ダッチ",
    "会合における主な意見",
    "議事要旨",
    "記者会見",
)

_ACTIONABLE_MONEY = (
    "NISA",
    "ニーサ",
    "つみたて",
    "iDeCo",
    "イデコ",
    "所得税",
    "住民税",
    "確定申告",
    "税制",
    "利上げ",
    "利下げ",
    "政策金利",
)


def apply_quality_gate(article: dict[str, Any], profile: dict[str, Any], *, demo: bool = False) -> tuple[bool, str]:
    """残すなら True。落とすなら False と理由。"""
    quality = article.get("quality", {})
    if quality.get("skip") and not demo:
        return False, quality.get("skip_reason", "差分なし")

    title = article.get("title", "")
    if any(w in title for w in _THIN_MONEY):
        return False, "今日動く話ではない（発行・会合資料・広報）"

    summary = article.get("easy_summary", {})
    status = summary.get("ai_status", "")
    if status in ("title_only", "title") and article.get("genre") == "金融":
        if not any(w in title for w in profile.get("priority_keywords", [])):
            return False, "本文が読めず、関心キーワードもない"

    if article.get("genre") == "金融" or article.get("source_id") in {"fsa_news", "boj_news", "mof_news"}:
        if not any(w in title for w in _ACTIONABLE_MONEY):
            return False, "NISA・税制・金利変更のどれでもない"

    if summary.get("skip_notify") and not demo:
        return False, "商品の増減なし"

    return True, ""


def unique_by_display_title(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同じ見出しのカードを1つに潰す"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for art in articles:
        title = (art.get("easy_summary", {}) or {}).get("easy_title") or art.get("title", "")
        key = re.sub(r"\s+", "", title)[:24]
        if key in seen:
            continue
        seen.add(key)
        out.append(art)
    return out
