"""「決まったこと」vs「まだ協議中」を判定する"""

from __future__ import annotations

import re
from typing import Any

_DECIDED = (
    "決定",
    "決まり",
    "施行",
    "施行日",
    "答申",
    "省令",
    "告示",
    "改定内容",
    "新たに決定",
    "認定しました",
    "指定しました",
    "是正結果",
    "違反として",
    "罰則",
    "確定",
)

_DECIDED_TITLE = ("決定", "施行", "公表", "答申", "是正結果", "改定", "認定", "指定")

_DISCUSSING = (
    "検討会",
    "審議会",
    "分科会",
    "専門委員会",
    "協議会",
    "研究会",
    "開催案内",
    "開催します",
    "を開催",
    "議事録",
    "たたき台",
    "パブリックコメント",
    "意見募集",
    "意見招請",
    "シンポジウム",
    "オンライン会議",
    "開催について",
)

_INFO = (
    "推移を更新",
    "更新しました",
    "資料を更新",
    "統計",
    "集計",
    "ダッシュボード",
    "定点",
)


def classify_decision_status(article: dict[str, Any]) -> dict[str, Any]:
    title = article.get("title", "")
    body = article.get("body_for_score", "") or article.get("summary", "")
    text = f"{title}\n{body}"

    decided_hits = [w for w in _DECIDED if w in text]
    discussing_hits = [w for w in _DISCUSSING if w in text]
    info_hits = [w for w in _INFO if w in text]

    title_discussing = any(w in title for w in ("検討会", "審議会", "専門委員会", "開催案内", "議事録", "意見募集"))
    title_decided = any(w in title for w in _DECIDED_TITLE)
    title_info = any(w in title for w in ("更新しました", "推移", "統計", "定点"))

    if title_info and not title_decided:
        return _pack("info", "📊 資料・数字の更新", "内容の更新。新ルールが決まったわけではない。変更点だけ確認。", info_hits)

    if title_discussing or (discussing_hits and re.search(r"第\d+回|開催|検討会|審議会|議事録", title)):
        return _pack(
            "discussing",
            "⏳ まだ協議中",
            "検討会・会議の案内。決まってないので、今すぐ動かなくてOK。",
            discussing_hits,
        )

    if title_decided or decided_hits:
        return _pack("decided", "✅ 決まったこと", "発表・決定された内容。現場のルールや対応が変わる可能性あり。", decided_hits)

    if discussing_hits and not decided_hits:
        return _pack("discussing", "⏳ まだ協議中", "これから話し合われる内容。変更になる可能性あり。", discussing_hits)

    if info_hits:
        return _pack("info", "📊 資料・数字の更新", "数字や資料の更新。急ぎの対応は基本不要。", info_hits)

    if "報道発表" in title or "公表" in title:
        return _pack("decided", "✅ 決まったこと", "公式発表。内容を確認。", ["報道発表"])

    return {
        "type": "unknown",
        "label": "❓ 要確認",
        "hint": "決定か協議中かはっきりせえへん。タップして確認。",
        "matched": [],
    }


def _pack(kind: str, label: str, hint: str, matched: list[str]) -> dict[str, Any]:
    return {"type": kind, "label": label, "hint": hint, "matched": matched[:5]}


def should_notify_by_status(
    status: dict[str, Any],
    profile: dict[str, Any],
    relevance_score: int = 0,
    title: str = "",
) -> bool:
    notify_cfg = profile.get("notify", {})
    kind = status.get("type", "unknown")
    defaults = {"decided": True, "discussing": False, "info": False, "unknown": False}

    if kind == "info" and profile.get("notify_high_relevance_info", True):
        threshold = profile.get("high_relevance_info_threshold", 6)
        if relevance_score >= threshold:
            return True
        # NISA・税制など関心キーワード付きの資料更新は通知
        title = title or status.get("_title", "")
        for word in profile.get("interest_boost", []):
            if word.lower() in title.lower() and relevance_score >= profile.get("min_score_to_notify", 3):
                return True

    return notify_cfg.get(kind, defaults.get(kind, False))
