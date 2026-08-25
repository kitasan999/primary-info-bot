"""記事ページから本文テキストを取得する"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

USER_AGENT = "primary-info-bot/1.0 (news notifier; +https://github.com)"


def fetch_page_text(url: str, timeout: int = 20) -> str:
    """URLのページから本文っぽいテキストを抽出"""
    if url.lower().endswith(".pdf"):
        return ""

    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    main = _pick_main(soup, url)
    if main is None:
        return ""

    text = main.get_text("\n", strip=True)
    return _clean_noise(text)


def _pick_main(soup: BeautifulSoup, url: str):
    """サイトごとに本文エリアを優先"""
    selectors: list[str] = []
    if "fsa.go.jp" in url:
        selectors = ["#main", ".contents", "#contents", "article", "main"]
    elif "mhlw.go.jp" in url:
        selectors = ["#main", ".contents", "main", "#contents"]
    elif "mof.go.jp" in url:
        selectors = ["#main", ".contents", "main", "#contents"]
    elif "boj.or.jp" in url:
        selectors = ["#contents", "#main", "main", "article"]
    else:
        selectors = ["#main", "main", "article", "body"]

    for sel in selectors:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 80:
            return node
    return soup.body


def _clean_noise(text: str) -> str:
    """パンくず・JavaScript警告などを除去"""
    lines = []
    skip_patterns = (
        "JavaScript",
        "ホーム >",
        "ホーム＞",
        "お問合せ",
        "代表電話",
        "報道関係",
        "サイトマップ",
        "本文へ",
    )
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or len(line) < 3:
            continue
        if any(p in line for p in skip_patterns):
            continue
        if re.fullmatch(r"[>\s　]+", line):
            continue
        lines.append(line)

    joined = "\n".join(lines)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()
