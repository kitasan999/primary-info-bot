"""Gemini API でやさしい要約＋介護職向けアドバイス"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any

import requests

# 429時は次のモデルへ。404のモデルは自動スキップ
GEMINI_MODELS = (
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-3.6-flash",
)
MAX_BODY_CHARS = 4000


def get_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _reader_context(profile: dict[str, Any]) -> str:
    ctx = profile.get("context", {})
    parts = [
        ctx.get("job", "介護職"),
        ctx.get("workplace", "グループホーム"),
        f"{ctx.get('region', '')}で働いている" if ctx.get("region") else "",
    ]
    interests = ctx.get("interests", [])
    if interests:
        parts.append("関心: " + "・".join(str(i) for i in interests))
    return " / ".join(p for p in parts if p)


def build_gemini_prompt(article: dict[str, Any], body: str, profile: dict[str, Any] | None = None) -> str:
    profile = profile or {}
    dec = article.get("decision_status", {})
    reader = _reader_context(profile)

    return (
        f"読者: {reader}\n"
        f"記事: {article.get('title', '')}\n"
        f"状態: {dec.get('label', '')}\n\n"
        f"本文:\n{body[:MAX_BODY_CHARS]}\n\n"
        "中学生にもわかる日本語で要約してください。"
    )


def summarize_with_gemini(
    article: dict[str, Any],
    body: str,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    api_key = get_api_key()
    if not api_key:
        return None

    profile = profile or {}
    dec = article.get("decision_status", {})
    reader = _reader_context(profile)

    prompt = (
        f"あなたは{reader}向けのニュース解説者です。\n"
        "ルール:\n"
        "- 中学生にもわかるやさしい日本語\n"
        "- 同じ内容を繰り返さない\n"
        "- 「手洗い・換気」だけの一般論禁止。記事の具体情報を使う\n"
        "- わからないことは「わからない」と書く\n"
        "- 資料更新（info）なら content_category は knowledge\n"
        "- action_today は「様子見でOK」でもよい\n\n"
        f"タイトル: {article.get('title', '')}\n"
        f"URL: {article.get('url', '')}\n"
        f"状態: {dec.get('label', '')} / {dec.get('hint', '')}\n\n"
        f"本文:\n{body[:MAX_BODY_CHARS]}\n\n"
        "次のJSONだけ返してください:\n"
        "{\n"
        '  "short_title": "20字以内の見出し",\n'
        '  "what_changed": "今回の変更点（1文。なければ大きな変更なし）",\n'
        '  "one_line": "全体の要約（1文）",\n'
        '  "impact": "グループホーム現場への影響（1文。なければ空文字）",\n'
        '  "action_today": "今日やること1つ",\n'
        '  "relevance_line": "自分に関係ある？への答え（1文）",\n'
        '  "content_category": "money または action または knowledge",\n'
        '  "category_reason": "分類理由（1文）",\n'
        '  "followup_question": "もっと知りたいときの質問1つ"\n'
        "}"
    )

    last_error = ""
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    params={"key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "temperature": 0.2,
                        },
                    },
                    timeout=60,
                )
                if response.status_code == 404:
                    last_error = f"{model} 未対応"
                    break
                if response.status_code == 429:
                    last_error = f"{model} 混雑中（429）"
                    time.sleep(3 * (attempt + 1))
                    continue
                response.raise_for_status()
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return {
                    "short_title": _trim(parsed.get("short_title", ""), 24),
                    "what_changed": _trim(parsed.get("what_changed", ""), 160),
                    "one_line": _trim(parsed.get("one_line", ""), 140),
                    "impact": _trim(parsed.get("impact", ""), 160),
                    "action_today": _trim(parsed.get("action_today", ""), 120),
                    "relevance_line": _trim(parsed.get("relevance_line", ""), 100),
                    "content_category": _normalize_category(parsed.get("content_category", "")),
                    "category_reason": _trim(parsed.get("category_reason", ""), 80),
                    "followup_question": _trim(parsed.get("followup_question", ""), 120),
                    "source": model,
                }
            except Exception as exc:
                last_error = str(exc)
                if attempt < 2:
                    time.sleep(2)
                    continue
        time.sleep(1)

    print(f"[Gemini] 要約失敗: {last_error}", file=sys.stderr)
    return None


def _normalize_category(value: str) -> str:
    v = str(value).lower().strip()
    if "money" in v or "お金" in v or "給" in v:
        return "money"
    if "action" in v or "現場" in v:
        return "action"
    return "knowledge"


def _trim(text: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", str(text).strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
