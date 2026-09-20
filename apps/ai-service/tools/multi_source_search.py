"""Bounded multi-source search for papers and technical references.

The adapters use public, documented endpoints and return the same Evidence
contract as the general web provider.  A failed specialist source is isolated
from the rest of the search, so one rate limit or provider outage never
discards otherwise useful results.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any, Awaitable, Callable

import httpx

from models.schemas import Evidence
from prompts.search_prompts import PAPER_SEARCH_HINTS, TECH_SEARCH_HINTS
from rag.hybrid import fuse_ranked_candidates
from tools.search_quality import canonical_url, rank_web_evidence
from tools.web import WebSearchError

SourceSearch = Callable[[str, int], Awaitable[list[Evidence]]]


def _evidence_id(prefix: str, url: str) -> str:
    return f"{prefix}{hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]}"


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _evidence(
    prefix: str, title: str, url: str, description: str, rank: int
) -> Evidence | None:
    title, url, description = _plain(title), _plain(url), _plain(description)
    if not title or not url:
        return None
    return Evidence(
        id=_evidence_id(prefix, url),
        chunk_id=f"web:{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}",
        content=f"{title}\n{description}" if description else title,
        source_name=title,
        source_type="web",
        content_kind="search_snippet",
        url=url,
        score=1.0 / max(rank, 1),
    )


class MultiSourceWebSearch:
    """Route one query to general, paper, and technical source adapters."""

    DEFAULT_SOURCES = frozenset(
        {"general", "arxiv", "openalex", "crossref", "github", "stackoverflow"}
    )
    SOURCE_WEIGHTS = {
        "general": 0.35,
        "arxiv": 0.18,
        "openalex": 0.18,
        "crossref": 0.12,
        "github": 0.1,
        "stackoverflow": 0.07,
    }

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        general: Any,
        sources: list[str] | set[str] | None = None,
        timeout_seconds: float = 8,
    ) -> None:
        self.client = client
        self.general = general
        requested = {
            str(item).strip().casefold()
            for item in (sources or self.DEFAULT_SOURCES)
            if str(item).strip()
        }
        self.sources = requested or set(self.DEFAULT_SOURCES)
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))

    def _selected_sources(self, query: str) -> list[str]:
        normalized = _plain(query).casefold()
        paper = any(term in normalized for term in PAPER_SEARCH_HINTS)
        technical = any(term in normalized for term in TECH_SEARCH_HINTS)
        selected = ["general"] if "general" in self.sources else []
        if paper:
            selected.extend(
                item
                for item in ("arxiv", "openalex", "crossref")
                if item in self.sources
            )
        if technical:
            selected.extend(
                item for item in ("github", "stackoverflow") if item in self.sources
            )
        # Explicit source names in configuration can opt into all sources for
        # broad research. Generic chat remains one general request by default.
        if "all" in self.sources:
            selected = [
                item
                for item in self.DEFAULT_SOURCES
                if item != "general" or "general" in self.sources
            ]
        return list(dict.fromkeys(selected))

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        limit = max(1, min(int(top_k), 20))
        handlers: dict[str, SourceSearch] = {
            "general": self.general.search,
            "arxiv": self._search_arxiv,
            "openalex": self._search_openalex,
            "crossref": self._search_crossref,
            "github": self._search_github,
            "stackoverflow": self._search_stackoverflow,
        }
        selected = [
            source for source in self._selected_sources(query) if source in handlers
        ]
        results = await asyncio.gather(
            *(
                self._safe_search(source, handlers[source], query, limit)
                for source in selected
            ),
            return_exceptions=True,
        )
        if results and all(isinstance(result, BaseException) for result in results):
            raise WebSearchError("所有搜索渠道请求失败，未取得可核验来源")
        channels: dict[str, list[tuple[str, Evidence, float]]] = {}
        for source, items in zip(selected, results):
            if isinstance(items, BaseException):
                continue
            channels[source] = [
                (canonical_url(item.url or ""), item, float(item.score or 0.0))
                for item in rank_web_evidence(query, items, limit)
            ]
        fused = fuse_ranked_candidates(
            channels,
            method="WEIGHTED_RRF",
            weights={
                source: self.SOURCE_WEIGHTS.get(source, 0.1) for source in channels
            },
            rank_constant=60,
            rank_window_size=max(limit * 3, 10),
        )
        output: list[Evidence] = []
        seen: set[str] = set()
        for candidate in fused:
            item = candidate.item
            identity = item.url or re.sub(r"\s+", " ", item.content).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            item.score = round(candidate.score, 6)
            item.fusion_score = round(candidate.score, 6)
            output.append(item)
            if len(output) >= limit:
                break
        return rank_web_evidence(query, output, limit)

    async def _safe_search(
        self, source: str, handler: SourceSearch, query: str, limit: int
    ) -> list[Evidence]:
        return await asyncio.wait_for(
            handler(query, limit), timeout=self.timeout_seconds
        )

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.get(
            url,
            params=params,
            timeout=self.timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "Shinkou-Insight/0.1"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def _search_arxiv(self, query: str, limit: int) -> list[Evidence]:
        response = await self.client.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max(limit, 5),
            },
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/atom+xml",
                "User-Agent": "Shinkou-Insight/0.1",
            },
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        items: list[Evidence] = []
        for rank, entry in enumerate(root.findall("atom:entry", namespace), start=1):
            title = entry.findtext("atom:title", default="", namespaces=namespace)
            abstract_url = entry.findtext("atom:id", default="", namespaces=namespace)
            pdf_url = next(
                (
                    str(link.get("href"))
                    for link in entry.findall("atom:link", namespace)
                    if str(link.get("title") or "").casefold() == "pdf"
                    and link.get("href")
                ),
                "",
            )
            url = pdf_url or abstract_url
            summary = entry.findtext("atom:summary", default="", namespaces=namespace)
            item = _evidence("A", title, url, summary, rank)
            if item:
                item.published_at = (
                    entry.findtext("atom:published", default="", namespaces=namespace)
                    or None
                )
                items.append(item)
        return items[:limit]

    async def _search_openalex(self, query: str, limit: int) -> list[Evidence]:
        payload = await self._get_json(
            "https://api.openalex.org/works",
            {
                "search": query,
                "per-page": max(limit, 5),
                "select": "id,title,doi,publication_year,abstract_inverted_index",
            },
        )
        items: list[Evidence] = []
        for rank, work in enumerate(payload.get("results") or [], start=1):
            if not isinstance(work, dict):
                continue
            abstract_index = work.get("abstract_inverted_index") or {}
            words = sorted(
                (
                    (position, word)
                    for word, positions in abstract_index.items()
                    for position in positions
                ),
                key=lambda item: item[0],
            )
            abstract = " ".join(word for _position, word in words)
            location = work.get("primary_location") or {}
            url = str(
                location.get("pdf_url") or work.get("doi") or work.get("id") or ""
            )
            item = _evidence(
                "O",
                work.get("title"),
                url,
                f"{work.get('publication_year') or ''} {abstract}".strip(),
                rank,
            )
            if item:
                items.append(item)
        return items[:limit]

    async def _search_crossref(self, query: str, limit: int) -> list[Evidence]:
        payload = await self._get_json(
            "https://api.crossref.org/works",
            {
                "query": query,
                "rows": max(limit, 5),
                "select": "DOI,title,author,published,abstract",
            },
        )
        items: list[Evidence] = []
        for rank, work in enumerate(
            (payload.get("message") or {}).get("items") or [], start=1
        ):
            if not isinstance(work, dict):
                continue
            title = (work.get("title") or [""])[0]
            url = f"https://doi.org/{work.get('DOI')}" if work.get("DOI") else ""
            abstract = re.sub(r"<[^>]+>", "", str(work.get("abstract") or ""))
            links = work.get("link") or []
            pdf_url = next(
                (
                    str(link.get("URL"))
                    for link in links
                    if isinstance(link, dict)
                    and "pdf" in str(link.get("content-type") or "").casefold()
                    and link.get("URL")
                ),
                "",
            )
            item = _evidence("C", title, pdf_url or url, abstract, rank)
            if item:
                items.append(item)
        return items[:limit]

    async def _search_github(self, query: str, limit: int) -> list[Evidence]:
        payload = await self._get_json(
            "https://api.github.com/search/repositories",
            {"q": query, "sort": "stars", "order": "desc", "per_page": max(limit, 5)},
        )
        items: list[Evidence] = []
        for rank, repo in enumerate(payload.get("items") or [], start=1):
            if not isinstance(repo, dict):
                continue
            item = _evidence(
                "G",
                repo.get("full_name"),
                repo.get("html_url"),
                repo.get("description"),
                rank,
            )
            if item:
                items.append(item)
        return items[:limit]

    async def _search_stackoverflow(self, query: str, limit: int) -> list[Evidence]:
        payload = await self._get_json(
            "https://api.stackexchange.com/2.3/search/advanced",
            {
                "q": query,
                "site": "stackoverflow",
                "order": "desc",
                "sort": "relevance",
                "pagesize": max(limit, 5),
            },
        )
        items: list[Evidence] = []
        for rank, result in enumerate(payload.get("items") or [], start=1):
            if not isinstance(result, dict):
                continue
            item = _evidence(
                "S",
                result.get("title"),
                result.get("link"),
                "Stack Overflow question",
                rank,
            )
            if item:
                items.append(item)
        return items[:limit]
