"""通知して意味があるか（商品レベル）を判定する"""

from __future__ import annotations

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
)


def apply_quality_gate(article: dict[str, Any], profile: dict[str, Any], *, demo: bool = False) -> tuple[bool, str]:
    """残すなら True。落とすなら False と理由。"""
    quality = article.get("quality", {})
    if quality.get("skip") and not demo:
        return False, quality.get("skip_reason", "差分なし")

    title = article.get("title", "")
    if any(w in title for w in _THIN_MONEY):
        return False, "数字・論文・広報だけで、今日動く話ではない"

    summary = article.get("easy_summary", {})
    status = summary.get("ai_status", "")
    if status in ("title_only", "title") and article.get("genre") == "金融":
        if not any(w in title for w in profile.get("priority_keywords", [])):
            return False, "本文が読めず、関心キーワードもない"

    if summary.get("skip_notify") and not demo:
        return False, "商品の増減なし"

    return True, ""
