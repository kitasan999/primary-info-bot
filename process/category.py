"""お金 / 現場対応 / 知っておく に分類"""

from __future__ import annotations

from typing import Any

CATEGORIES = {
    "money": {
        "label": "💰 お金",
        "hint": "給料・手当・税金など、自分のお金に関係する可能性",
        "priority": 1,
    },
    "action": {
        "label": "🏠 現場対応",
        "hint": "今日または近いうちに、現場で動きが必要かも",
        "priority": 2,
    },
    "knowledge": {
        "label": "📚 知っておく",
        "hint": "すぐ動かなくてOK。背景知識として頭に入れとく",
        "priority": 3,
    },
}

_MONEY = (
    "賃金", "給与", "手当", "賞与", "ボーナス", "税金", "年金", "最低賃金", "残業", "社会保険", "源泉",
    "処遇改善", "NISA", "ニーサ", "つみたて", "投資信託", "iDeCo", "イデコ", "金融政策", "金利", "国債", "税制",
)
_ACTION = (
    "感染", "対策", "マスク", "記録", "虐待", "拘束", "届出", "報告義務",
    "避難", "緊急", "人員配置", "義務", "施行", "改定", "届け出", "ワクチン",
    "インフル", "コロナ", "加算", "基準",
)
_KNOWLEDGE = ("推移", "統計", "更新", "データ", "発生状況", "資料", "定点", "ダッシュボード")


def classify_content_type(article: dict[str, Any]) -> dict[str, Any]:
    summary = article.get("easy_summary", {})
    gemini_cat = summary.get("content_category", "")

    if gemini_cat in CATEGORIES:
        cat = gemini_cat
        reason = summary.get("category_reason", CATEGORIES[cat]["hint"])
    else:
        cat, reason = _rule_based(article)

    # 金融ソースはお金カテゴリを優先
    if article.get("genre") == "金融" and cat != "money":
        text = f"{article.get('title', '')}\n{article.get('body_for_score', '')}"
        if any(w in text for w in _MONEY) or any(w in text for w in ("金融", "日銀", "財務", "税")):
            cat = "money"
            reason = CATEGORIES["money"]["hint"]
    dec_type = article.get("decision_status", {}).get("type", "")
    action_text = summary.get("gemini_action", "")
    title = article.get("title", "")
    if any(w in title for w in ("NISA", "ニーサ", "つみたて", "税制", "所得税", "住民税", "確定申告")):
        cat = "money"
        reason = CATEGORIES["money"]["hint"]
    elif dec_type == "info" or "様子見" in action_text or "更新" in title:
        cat = "knowledge"
        reason = CATEGORIES["knowledge"]["hint"]

    result = {
        "type": cat,
        "label": CATEGORIES[cat]["label"],
        "hint": reason,
        "priority": CATEGORIES[cat]["priority"],
    }
    article["content_type"] = result
    return result


def _rule_based(article: dict[str, Any]) -> tuple[str, str]:
    title = article.get("title", "")
    body = article.get("body_for_score", "") or article.get("summary", "")
    text = f"{title}\n{body}"
    summary = article.get("easy_summary", {})

    money = sum(1 for w in _MONEY if w in text)
    action = sum(1 for w in _ACTION if w in text)
    knowledge = sum(1 for w in _KNOWLEDGE if w in text)

    action_text = summary.get("gemini_action", "")
    if "様子見" in action_text or "不要" in action_text:
        knowledge += 1

    if money >= 1 and money >= action:
        return "money", "給与・手当・税金などお金の話が含まれます"
    if action >= 1 and "様子見" not in action_text:
        dec_type = article.get("decision_status", {}).get("type", "")
        if dec_type != "info":
            return "action", "現場の対応・ルール変更の可能性があります"
    if knowledge >= 1:
        return "knowledge", "資料や数字の更新。背景として知っておく程度"
    return "knowledge", "すぐの対応は不要。必要ならリンクで確認"


def sort_by_category(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(articles, key=lambda a: a.get("content_type", {}).get("priority", 9))
