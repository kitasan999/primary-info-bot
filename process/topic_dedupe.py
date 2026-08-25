"""同じトピックの記事を1つにまとめる"""

from __future__ import annotations

import re
from typing import Any

_TOPIC_RULES: list[tuple[str, str]] = [
    ("新型コロナ", r"新型コロナ|コロナウイルス"),
    ("インフルエンザ", r"インフルエンザ|インフル"),
    ("介護報酬", r"介護報酬|報酬改定|加算"),
    ("処遇改善", r"処遇改善"),
    ("感染症", r"感染症"),
    ("障害福祉", r"障害福祉|障害者"),
    ("虐待防止", r"虐待"),
    ("身体拘束", r"身体拘束"),
    ("賃金", r"賃金|残業|不正"),
    ("ワクチン", r"ワクチン"),
    ("NISA", r"NISA|ニーサ|つみたて投資"),
    ("日銀金融政策", r"金融政策決定会合|政策金利|利上げ|利下げ"),
    ("国債発行", r"国債.*発行|物価連動国債|利付国債"),
]


def topic_key(title: str) -> str:
    for key, pattern in _TOPIC_RULES:
        if re.search(pattern, title):
            return key

    cleaned = re.sub(r"(を更新しました|の推移|に関する|について|を公表).*", "", title)
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned[:24] or title[:24]


def _pick_score(article: dict[str, Any]) -> int:
    rel = article.get("relevance", {}).get("relevance_score", 0)
    if rel:
        return rel
    return int(article.get("_pre_score", 0))


def merge_same_topic(articles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    best: dict[str, dict[str, Any]] = {}
    merged_total = 0

    for art in articles:
        key = topic_key(art.get("title", ""))
        if key not in best:
            best[key] = art
            art["merged_count"] = 1
            art["merged_titles"] = [art.get("title", "")]
            continue

        merged_total += 1
        existing = best[key]
        existing["merged_count"] = existing.get("merged_count", 1) + 1
        existing.setdefault("merged_titles", [existing.get("title", "")]).append(art.get("title", ""))

        if _pick_score(art) > _pick_score(existing):
            art["merged_count"] = existing["merged_count"]
            art["merged_titles"] = existing["merged_titles"]
            best[key] = art

    return list(best.values()), merged_total


def clean_detail_text(text: str) -> str:
    if not text:
        return ""
    bad_signs = ("政策について", "ホーム >", "ホーム＞", "分野別", "一覧", "トップ")
    if any(s in text for s in bad_signs):
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:90]
