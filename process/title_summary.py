"""タイトルだけから具体的な要約を作る（Gemini不要）"""

from __future__ import annotations

import re
from typing import Any


def summarize_from_title(title: str, agency: str = "公式") -> dict[str, str] | None:
    """タイトルを解析して、テンプレ以外の要約を返す。該当なければ None"""
    t = title.strip()
    rules: list[tuple[str, dict[str, str]]] = [
        (
            r"つみたて投資|NISA|ニーサ",
            {
                "easy_title": "つみたてNISA商品リスト更新",
                "one_line": f"{agency}が、つみたてNISAで買える商品の一覧を更新した。",
                "what_changed": "NISAの対象商品リスト（投資信託など）が最新版に差し替わった。",
                "relevance": "つみたてNISA口座を使ってる人は、自分の積立商品が対象から外れてないか確認。",
                "action": "金融庁サイトの一覧で、自分の商品名を検索。",
                "impact": "対象外になった商品は、新規積立ができなくなることがある。",
            },
        ),
        (
            r"金融政策決定会合|金融政策.*意見",
            {
                "easy_title": "日銀・金融政策の会合",
                "one_line": "日銀が、金融政策決定会合（金利を決める会）の主な意見を公表した。",
                "what_changed": "日銀の政策委員が出した意見の要約が公開された。",
                "relevance": "金利・物価政策の方向性。住宅ローンや預金金利に将来影響することがある。",
                "action": "「利上げ」「据え置き」どっちの意見が多いか、概要だけ見る。",
                "impact": "すぐ変わるわけじゃない。ただし金利の先行きを読む材料になる。",
            },
        ),
        (
            r"国債.*残高|国債の銘柄",
            {
                "easy_title": "日銀の国債保有データ",
                "one_line": "日銀が、保有する国債のデータを更新した。",
                "what_changed": "国債の銘柄別残高などの統計数字が更新された。",
                "relevance": "個人のNISAや税金には直接関係なし。マクロ情報。",
                "action": "様子見でOK。",
                "impact": "",
            },
        ),
        (
            r"税制|所得税|住民税|源泉|控除|税務",
            {
                "easy_title": "税制関連の発表",
                "one_line": f"{agency}が、税金・税制に関する情報を発表した。",
                "what_changed": "税制や税務手続きに関する新しい情報が出た。",
                "relevance": "確定申告・控除・手取りに関係する可能性あり。",
                "action": "タイトルに「改正」「見直し」があれば要点を確認。なければ様子見。",
                "impact": "ルール変更なら、来年の手取りや申告に影響することがある。",
            },
        ),
        (
            r"新型コロナ|コロナウイルス",
            {
                "easy_title": "新型コロナ資料の更新",
                "one_line": "厚労省が、新型コロナの最新データ・資料を更新した。",
                "what_changed": "発生状況・検疫・変異株などの最新資料が追加された。",
                "relevance": "感染記録や記入ルールは変わらない。数字・資料の更新だけ。",
                "action": "様子見でOK（急いで動く必要なし）",
                "impact": "",
            },
        ),
        (
            r"更新しました|推移|統計|データ",
            {
                "easy_title": _short_from_title(t),
                "one_line": f"{agency}が「{_short_from_title(t)}」の資料・数字を更新した。",
                "what_changed": "最新データや資料が追加された。新ルールは決まっていない。",
                "relevance": "資料の数字更新。今日からルールが変わる話ではない。",
                "action": "様子見でOK",
                "impact": "",
            },
        ),
        (
            r"公表|発表|決定|施行|改定",
            {
                "easy_title": _short_from_title(t),
                "one_line": f"{agency}が「{_short_from_title(t)}」を公表した。",
                "what_changed": "新しい公式発表。詳細はリンク先。",
                "relevance": "内容次第で生活やお金に関係する可能性あり。",
                "action": "タイトルだけじゃ判断できないので、リンク先の要点を確認。",
                "impact": "",
            },
        ),
    ]

    for pattern, data in rules:
        if re.search(pattern, t, re.I):
            return data
    return None


def _short_from_title(title: str) -> str:
    text = title
    for suffix in (
        "を更新しました",
        "について公表しました",
        "について掲載しました",
        "を公表しました",
        "について",
    ):
        text = text.replace(suffix, "")
    text = re.sub(r"^[その他記者会見採用調達,、\s]+", "", text)
    text = re.sub(r"\s+", "", text)
    if len(text) > 24:
        return text[:23] + "…"
    return text or title[:24]


def apply_title_summary(summary: dict[str, Any], article: dict[str, Any], agency: str) -> bool:
    """タイトル解析結果を summary に反映。成功なら True"""
    parsed = summarize_from_title(article.get("title", ""), agency)
    if not parsed:
        return False

    summary["easy_title"] = parsed.get("easy_title", summary.get("easy_title", ""))
    summary["one_line"] = parsed.get("one_line", "")
    summary["what_changed"] = parsed.get("what_changed", "")
    summary["gemini_relevance"] = parsed.get("relevance", "")
    summary["gemini_action"] = parsed.get("action", "")
    summary["gemini_impact"] = parsed.get("impact", "")
    return True
