from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from models.schemas import Evidence
from security.policy import SecurityPolicyError, validate_external_url
from tools.search_quality import rank_web_evidence, topic_score


_BOILERPLATE_CLASS = re.compile(
    r"(?:^|[-_ ])(?:nav|menu|breadcrumb|sidebar|footer|header|toc|table[-_ ]of[-_ ]contents|"
    r"pagination|share|comment|cookie|advert|ad|recommend|related)(?:$|[-_ ])",
    re.IGNORECASE,
)
_DIRECTORY_PATH = re.compile(r"/(?:issue|archive|category|tag|search|results|directory|index|list)(?:/|$)", re.IGNORECASE)
_BLOCKED_PAGE_MARKERS = (
    "captcha",
    "verify you are human",
    "access denied",
    "请求过于频繁",
    "访问被拒绝",
    "安全验证",
    "javascript required",
)


def _clean(value: object) -> str:
    text = str(value or "").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _passage(blocks: list[str], query: str, *, max_chars: int = 2_400) -> tuple[str, float] | None:
    # Window long PDF pages/paragraphs before scoring so a hit near the end is
    # not lost when an unrelated introduction is truncated to the prompt budget.
    windows = [_clean(block[start:start + 1000]) for block in blocks
               for start in range(0, len(block), 850)]
    candidates = [(index, block) for index, block in enumerate(windows) if len(block) >= 28]
    if not candidates:
        return None
    ranked = sorted(
        ((topic_score(query, block), index, block) for index, block in candidates),
        key=lambda item: (-item[0], -len(item[2]), item[1]),
    )
    best_score, best_index, _ = ranked[0]
    if best_score <= 0:
        return None
    selected = {best_index: windows[best_index]}
    for score, index, value in ranked[1:]:
        if score > 0 and sum(map(len, selected.values())) + len(value) + 4 <= max_chars:
            selected[index] = value
    output = "\n\n".join(value for _, value in sorted(selected.items()))
    return output, best_score


def _page_title(soup: BeautifulSoup, fallback: str) -> str:
    for selector, attribute in (("meta[property='og:title']", "content"), ("meta[name='twitter:title']", "content")):
        node = soup.select_one(selector)
        value = _clean(node.get(attribute, "") if node else "")
        if value:
            return value[:300]
    for selector in ("h1", "title"):
        node = soup.select_one(selector)
        value = _clean(node.get_text(" ", strip=True) if node else "")
        if value:
            return value[:300]
    return _clean(fallback)[:300] or "网页原文"


def _published_date(soup: BeautifulSoup) -> str | None:
    values: list[str] = []
    for node in soup.select("meta[property='article:published_time'],meta[itemprop='datePublished'],meta[name='pubdate'],meta[name='publishdate'],meta[name='date'],time[itemprop='datePublished'],article time[datetime]"):
        values.append(str(node.get("content") or node.get("datetime") or node.get_text()))
    for node in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(node.get_text())
        except (ValueError, TypeError):
            continue
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if not isinstance(row, dict):
                continue
            objects = row.get("@graph", [row])
            for obj in objects if isinstance(objects, list) else []:
                if isinstance(obj, dict) and obj.get("datePublished"):
                    values.append(str(obj["datePublished"]))
    for value in values:
        match = re.match(r"\s*(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", value)
        if match:
            try:
                return date(*map(int, match.groups())).isoformat()
            except ValueError:
                pass
    return None


def _html_blocks(data: bytes, url: str, fallback_title: str) -> tuple[str, list[str], str | None] | None:
    soup = BeautifulSoup(data[:2_000_000], "html.parser")
    title = _page_title(soup, fallback_title)
    published_at = _published_date(soup)
    for node in soup.select("script,style,noscript,template,svg,canvas,nav,footer,form,menu,button,iframe"):
        node.decompose()

    roots = soup.select("article, main, [role='main'], .article-content, .post-content, .entry-content, .paper-content")
    root = max(roots, key=lambda node: len(node.get_text(" ", strip=True)), default=soup.body or soup)
    for node in root.select("[class], [id]"):
        if node.attrs is None:  # A containing sidebar may already be removed.
            continue
        identity = " ".join([*node.get("class", []), node.get("id", "")])
        if _BOILERPLATE_CLASS.search(identity):
            node.decompose()

    blocks: list[str] = []
    for node in root.select("p,blockquote,pre,li,td"):
        value = _clean(node.get_text(" ", strip=True))
        linked = sum(len(_clean(link.get_text(" ", strip=True))) for link in node.select("a"))
        if linked / max(len(value), 1) > 0.45:
            continue
        if len(value) >= 28 and value not in blocks:
            blocks.append(value)
    if not blocks:
        for node in root.select("a,h1,h2,h3,h4"):
            node.decompose()
        blocks = [_clean(line) for line in root.get_text("\n", strip=True).splitlines() if _clean(line)]

    page_text = "\n\n".join(blocks)
    link_text = sum(len(_clean(node.get_text(" ", strip=True))) for node in root.select("a"))
    link_ratio = link_text / max(len(page_text), 1)
    path = urlparse(url).path
    has_article = bool(soup.select_one("article"))
    if len(page_text) < 220:
        return None
    if any(marker in page_text.casefold() for marker in _BLOCKED_PAGE_MARKERS):
        return None
    # Issue/archive/category pages are useful navigation, not evidence. Keep
    # them only when the page contains a real article container and enough text.
    if _DIRECTORY_PATH.search(path) and link_ratio > 0.35 and not has_article:
        return None
    if link_ratio > 0.45:
        return None
    return title, blocks, published_at


def _pdf_pages(data: bytes, fallback_title: str) -> tuple[str, list[tuple[int, str]]] | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return None
    metadata = reader.metadata or {}
    title = _clean(metadata.get("/Title") or fallback_title)[:300] or "论文 PDF"
    pages: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = _clean(page.extract_text() or "")
        if len(text) >= 80:
            pages.append((page_number, text))
    return (title, pages) if pages else None


async def _hydrate_one(
    client: httpx.AsyncClient,
    item: Evidence,
    query: str,
    parser: Any | None,
) -> Evidence | None:
    if not item.url:
        return None
    try:
        url = validate_external_url(item.url)
    except SecurityPolicyError:
        return None
    try:
        response = await client.get(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain",
                "User-Agent": "Shinkou-Insight/0.1 (+source extraction)",
            },
            timeout=15,
            follow_redirects=True,
        )
    except httpx.RequestError:
        return None
    if response.status_code < 200 or response.status_code >= 300:
        return None
    content_type = response.headers.get("content-type", "").casefold()
    is_pdf = "application/pdf" in content_type or urlparse(str(response.url)).path.casefold().endswith(".pdf")
    if is_pdf:
        parsed = await asyncio.to_thread(_pdf_pages, response.content, item.source_name)
        if parsed is None and parser is not None:
            try:
                parsed_document = await asyncio.to_thread(
                    parser.parse_bytes,
                    response.content,
                    file_name=Path(urlparse(str(response.url)).path).name or "paper.pdf",
                    mime_type=content_type,
                )
                pages = [
                    (int(document.metadata.get("page", index + 1)), _clean(document.page_content))
                    for index, document in enumerate(parsed_document.documents)
                    if _clean(document.page_content)
                ]
                parsed = (item.source_name, pages) if pages else None
            except Exception:
                parsed = None
        if parsed is None:
            return None
        title, pages = parsed
        ranked = sorted(((topic_score(query, text), page, text) for page, text in pages), key=lambda value: (-value[0], value[1]))
        if not ranked or ranked[0][0] <= 0:
            return None
        score, page_number, text = ranked[0]
        passage = _passage([text], query, max_chars=2_400)
        if passage is None:
            return None
        content, _ = passage
        digest = hashlib.sha256(f"{item.url}#page={page_number}".encode("utf-8")).hexdigest()[:16]
        return item.model_copy(update={
            "id": f"{item.id}-p{page_number}",
            "chunk_id": f"web:{digest}",
            "content": content,
            "source_name": title,
            "page_number": page_number,
            "url": item.url,
            "content_kind": "fulltext",
            "score": max(float(item.score or 0), float(score)),
        })

    extracted = await asyncio.to_thread(_html_blocks, response.content, str(response.url), item.source_name)
    if extracted is None:
        return None
    title, blocks, published_at = extracted
    passage = _passage(blocks, query)
    if passage is None:
        return None
    content, score = passage
    return item.model_copy(update={
        "content": content,
        "source_name": title,
        "url": item.url,
        "content_kind": "fulltext",
        "published_at": published_at,
        "score": max(float(item.score or 0), float(score)),
    })


async def hydrate_web_evidence(
    client: httpx.AsyncClient | None,
    evidence: list[Evidence],
    query: str,
    *,
    parser: Any | None = None,
    max_concurrency: int = 4,
) -> list[Evidence]:
    """Replace search snippets with source passages, dropping unextractable pages."""

    if client is None or not evidence:
        return []
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def load(item: Evidence) -> Evidence | None:
        async with semaphore:
            return await _hydrate_one(client, item, query, parser)

    results = await asyncio.gather(*(load(item) for item in evidence), return_exceptions=True)
    return rank_web_evidence(query, [item for item in results if isinstance(item, Evidence)], len(evidence), require_body=True)
