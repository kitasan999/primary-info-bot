"""介護職向け「自分に関係ある？」判定"""

from __future__ import annotations

from typing import Any

from process.decision_status import classify_decision_status, should_notify_by_status


def assess_relevance(article: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    title = article.get("title", "")
    body = article.get("body_for_score", "")
    if not body:
        body = article.get("summary", "")
    text = f"{title}\n{body}"

    score = 0
    matched_high: list[str] = []
    matched_medium: list[str] = []
    matched_ignore: list[str] = []

    for word in profile.get("keywords", {}).get("high", []):
        if word in text:
            score += 3
            matched_high.append(word)

    for word in profile.get("keywords", {}).get("medium", []):
        if word in text:
            score += 1
            matched_medium.append(word)

    for word in profile.get("keywords", {}).get("ignore", []):
        if word in text:
            score -= 3
            matched_ignore.append(word)

    score = max(0, min(10, score))
    score = _apply_interest_boost(title, score, profile)
    min_score = profile.get("min_score_to_notify", 3)

    decision = classify_decision_status(article)
    article["decision_status"] = decision

    topic_ok = score >= min_score
    status_ok = should_notify_by_status(decision, profile, score, title=title)
    notify = topic_ok and status_ok

    label, reason = _build_relevance_message(
        score, matched_high, matched_medium, matched_ignore, profile, decision, notify
    )

    result = {
        "relevance_score": score,
        "relevance_label": label,
        "relevance_reason": reason,
        "notify": notify,
        "matched_high": matched_high,
        "matched_medium": matched_medium,
        "matched_ignore": matched_ignore,
    }
    article["relevance"] = result
    return result


def _build_relevance_message(
    score: int,
    high: list[str],
    medium: list[str],
    ignore: list[str],
    profile: dict[str, Any],
    decision: dict[str, Any],
    notify: bool,
) -> tuple[str, str]:
    role = profile.get("role", "介護職")
    dtype = decision.get("type", "unknown")

    if not notify and dtype == "discussing" and score >= profile.get("min_score_to_notify", 3):
        return "⏳ 協議中（通知せず）", "検討会・会議段階。決まったらまた通知する。"

    if not notify and dtype == "info":
        return "📊 更新情報（通知せず）", "統計や資料の更新。決定事項ではない。"

    if not notify and score < profile.get("min_score_to_notify", 3):
        if ignore:
            return "⚪ 関係薄い", f"今回は{role}向けではなさそう（{ignore[0]}など）"
        return "⚪ 関係薄い", f"{role}の日常業務とは直接関係なさそう"

    if score >= 6:
        words = "・".join(high[:3]) if high else "介護・福祉"
        if dtype == "info":
            return "🟢 関係大", f"重要な資料更新（{words}）。変更点を確認"
        return "🟢 関係大", f"{role}の仕事と関係しそう（{words}）"

    if score >= 3:
        words = "・".join((high + medium)[:3]) if (high or medium) else "福祉・健康"
        return "🟡 要チェック", f"現場に関係する可能性あり（{words}）"

    return decision.get("label", "❓ 要確認"), decision.get("hint", "")


def priority_score(title: str, profile: dict[str, Any]) -> int:
    """ユーザー関心の高い順（数字が大きいほど優先）"""
    t = title.lower()
    words = profile.get("priority_keywords", [])
    for i, word in enumerate(words):
        if word.lower() in t:
            return len(words) - i
    return 0


def quick_title_score(title: str, profile: dict[str, Any]) -> int:
    fake: dict[str, Any] = {"title": title, "summary": "", "body_for_score": title}
    text = title
    score = 0
    for word in profile.get("keywords", {}).get("high", []):
        if word in text:
            score += 3
    for word in profile.get("keywords", {}).get("medium", []):
        if word in text:
            score += 1
    for word in profile.get("keywords", {}).get("ignore", []):
        if word in text:
            score -= 3
    score = max(0, min(10, score))
    return _apply_interest_boost(title, score, profile)


def _apply_interest_boost(title: str, score: int, profile: dict[str, Any]) -> int:
    for word in profile.get("interest_boost", []):
        if word.lower() in title.lower():
            return min(10, score + 2)
    return score


def is_obvious_discussing_title(title: str) -> bool:
    decided = any(w in title for w in ("決定", "施行", "公表", "是正結果", "改定"))
    if decided:
        return False
    return any(w in title for w in ("検討会", "審議会", "専門委員会", "開催案内", "議事録", "意見募集", "を開催"))
