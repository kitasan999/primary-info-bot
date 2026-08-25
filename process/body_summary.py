"""ページ本文から具体的な要約を作る（Gemini不要）"""

from __future__ import annotations

import re
from typing import Any


def summarize_from_body(body: str, title: str, url: str, agency: str) -> dict[str, str] | None:
    body = (body or "").strip()
    if len(body) < 40:
        return None
    if url.lower().endswith(".pdf"):
        return None

    if "nisa" in url.lower() or "つみたて" in title:
        parsed = _nisa_page(body, agency)
        if parsed:
            return parsed

    return _generic_page(body, title, agency)


def apply_body_summary(summary: dict[str, Any], parsed: dict[str, str]) -> bool:
    if not parsed.get("one_line"):
        return False
    summary["easy_title"] = parsed.get("easy_title", summary.get("easy_title", ""))
    summary["one_line"] = parsed["one_line"]
    summary["what_changed"] = parsed.get("what_changed", "")
    summary["gemini_relevance"] = parsed.get("relevance", "")
    summary["gemini_action"] = parsed.get("action", "")
    summary["gemini_impact"] = parsed.get("impact", "")
    return True


def _nisa_page(body: str, agency: str) -> dict[str, str] | None:
    dates = re.findall(r"20\d{2}/\d{1,2}/\d{1,2}", body)
    latest = dates[0] if dates else ""

    files: list[str] = []
    if "運用会社別" in body:
        files.append("運用会社別の届出一覧")
    if "資産別" in body or "対象資産" in body:
        files.append("資産別の届出一覧")
    if "概要" in body:
        files.append("対象商品の概要")

    if not files and "対象商品" not in body:
        return None

    file_text = "・".join(files) if files else "対象商品リスト"
    date_note = f"{latest}付" if latest else "最新版"

    return {
        "easy_title": "つみたてNISA商品リスト更新",
        "one_line": f"{agency}ページ上の{file_text}が{date_note}に更新されている。",
        "what_changed": f"最終更新日は{latest or 'ページ参照'}。Excel形式の一覧{len(files) or 1}種類が差し替わった。",
        "relevance": "つみたてNISAで積立中なら、自分のファンドがまだ対象か要確認。",
        "action": f"リンク先のExcel（{date_note}）を開き、自分の商品名を検索。",
        "impact": "対象外になった商品は新規積立不可。すでに持ってる分は基本そのまま。",
    }


def _generic_page(body: str, title: str, agency: str) -> dict[str, str] | None:
    lines = [_clean_line(ln) for ln in body.splitlines()]
    lines = [ln for ln in lines if len(ln) >= 15]

    key_lines: list[str] = []
    for ln in lines[:20]:
        if title and title in ln:
            continue
        if any(skip in ln for skip in _SKIP):
            continue
        if re.search(r"(公表|発表|更新|決定|施行|記者会見|概要|内容|について)", ln):
            key_lines.append(ln)
        if len(key_lines) >= 3:
            break

    if not key_lines:
        for ln in lines[:6]:
            if len(ln) >= 20 and title not in ln:
                key_lines.append(ln)
            if len(key_lines) >= 2:
                break

    if not key_lines:
        return None

    lead = key_lines[0]
    if len(lead) > 100:
        lead = lead[:99] + "…"

    # タイトルとほぼ同じ内容なら、title_summaryに任せる（Noneを返す）
    # 例: タイトル「新型コロナ...を更新しました」→ lead「新型コロナ...について」は情報増えてない
    title_key = re.sub(r"(を更新しました|について|に関する|報道発表資料|\s)", "", title)[:12]
    lead_key = re.sub(r"(について|に関する|\s)", "", lead)
    if title_key and title_key in lead_key:
        return None  # タイトルの繰り返しなので、title_summaryの方が有益

    detail = ""
    if len(key_lines) > 1:
        detail = key_lines[1][:80]

    what = lead
    if detail and detail not in what:
        what = f"{lead}（補足: {detail}）"

    return {
        "easy_title": title[:24],
        "one_line": f"{agency}のページ: {lead}",
        "what_changed": what,
        "relevance": "公式ページの内容。自分の生活・仕事・お金に関係するか確認。",
        "action": "上記を踏まえ、リンク先で詳細を確認。",
        "impact": "",
    }


_SKIP = (
    "ホーム",
    "政策について",
    "JavaScript",
    "お問合せ",
    "サイトマップ",
    "メニュー",
    "本文へ",
    "印刷",
)


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()
