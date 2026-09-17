from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qs, unquote, urlparse
from typing import Protocol

import httpx
from bs4 import BeautifulSoup

from models.schemas import Evidence
from prompts.search_prompts import WEB_SEARCH_STOPWORDS


class WebSearchProvider(Protocol):
    async def search(self, query: str, top_k: int = 5) -> list[Evidence]: ...


class WebSearchError(RuntimeError):
    """Base error for an external search provider."""


DEFAULT_DUCKDUCKGO_BASE_URL = "https://html.duckduckgo.com/html/"

def _search_terms(query: str) -> set[str]:
    """Extract topic anchors while ignoring conversational search commands."""

    normalized = str(query or "").casefold()
    for stopword in sorted(WEB_SEARCH_STOPWORDS, key=len, reverse=True):
        normalized = normalized.replace(stopword, " ")
    terms = set(re.findall(r"[a-z0-9][a-z0-9._-]{1,}|[\u4e00-\u9fff]{2,}", normalized))
    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        terms.update(block[index : index + 2] for index in range(len(block) - 1))
    return {term for term in terms if len(term) >= 2}


def _relevant_candidates(query: str, candidates: list[tuple[str, str, str]], top_k: int) -> list[tuple[str, str, str]]:
    """Drop search-engine noise before it reaches the model or citation panel."""

    terms = _search_terms(query)
    if not terms:
        return candidates[:top_k]
    relevant: list[tuple[str, str, str]] = []
    for candidate in candidates:
        title, url, description = candidate
        haystack = f"{title} {description} {url}".casefold()
        if any(term in haystack for term in terms):
            relevant.append(candidate)
    return relevant[:top_k]


class DisabledWebSearch:
    """Explicitly fail when a request needs an unconfigured web provider."""

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        raise WebSearchError("external web search is not configured")


class BraveWebSearch:
    """Brave Search API adapter that returns URL-backed evidence."""

    def __init__(self, *, client: httpx.AsyncClient, api_key: str, base_url: str, search_language: str = "zh-hans"):
        if not api_key:
            raise ValueError("runtime web search API key is required when web search is enabled")
        self.client = client
        self.api_key = api_key
        self.base_url = base_url
        self.search_language = search_language

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        try:
            response = await self.client.get(
                self.base_url,
                headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                params={
                    "q": query,
                    "count": max(1, min(max(top_k * 3, 10), 20)),
                    "search_lang": self.search_language,
                    "text_decorations": "false",
                },
            )
        except httpx.TimeoutException as exc:
            raise WebSearchError("web search request timed out") from exc
        except httpx.RequestError as exc:
            raise WebSearchError(f"web search request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise WebSearchError("web search authentication failed")
        if response.status_code == 429:
            raise WebSearchError("web search rate limit exceeded")
        if response.is_error:
            raise WebSearchError(f"web search failed with HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise WebSearchError("web search returned invalid JSON") from exc

        results = ((payload.get("web") or {}).get("results") or [])
        candidates: list[tuple[str, str, str]] = []
        for item in results:
            title = _plain_text(item.get("title"))
            url = str(item.get("url") or "").strip()
            description = _plain_text(item.get("description"))
            if not title or not url or not description:
                continue
            candidates.append((title, url, description))

        evidence: list[Evidence] = []
        for title, url, description in _relevant_candidates(query, candidates, top_k):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            evidence.append(
                Evidence(
                    id=f"W{digest[:12]}",
                    chunk_id=f"web:{digest[:16]}",
                    content=f"{title}\n{description}",
                    source_name=title,
                    score=round(1 / (len(evidence) + 1), 4),
                    url=url,
                    source_type="web",
                )
            )
        return evidence


class DuckDuckGoWebSearch:
    """Public HTML search adapter used when a project has no provider key."""

    def __init__(self, *, client: httpx.AsyncClient, base_url: str = DEFAULT_DUCKDUCKGO_BASE_URL, search_language: str = "zh-hans"):
        self.client = client
        self.base_url = base_url
        self.search_language = search_language

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        try:
            response = await self.client.get(
                self.base_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "Shinkou-Insight/0.1 (+local development)",
                },
                params={
                    "q": query,
                    "kl": _duckduckgo_region(self.search_language),
                },
            )
        except httpx.TimeoutException as exc:
            raise WebSearchError("web search request timed out") from exc
        except httpx.RequestError as exc:
            raise WebSearchError(f"web search request failed: {exc}") from exc

        if response.status_code == 429:
            raise WebSearchError("web search rate limit exceeded")
        if response.status_code in {401, 403}:
            raise WebSearchError("public web search was blocked by the provider")
        if response.is_error:
            raise WebSearchError(f"web search failed with HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        candidate_limit = max(10, min(top_k * 3, 20))
        candidates: list[tuple[str, str, str]] = []
        seen_urls: set[str] = set()
        for item in soup.select(".result"):
            link = item.select_one("a.result__a")
            snippet = item.select_one(".result__snippet")
            title = _plain_text(link.get_text(" ", strip=True) if link else "")
            url = _duckduckgo_result_url(link.get("href") if link else "")
            description = _plain_text(snippet.get_text(" ", strip=True) if snippet else "")
            if not title or not url or not description or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append((title, url, description))
            if len(candidates) >= candidate_limit:
                break
        evidence: list[Evidence] = []
        for title, url, description in _relevant_candidates(query, candidates, top_k):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            evidence.append(
                Evidence(
                    id=f"W{digest[:12]}",
                    chunk_id=f"web:{digest[:16]}",
                    content=f"{title}\n{description}",
                    source_name=title,
                    score=round(1 / (len(evidence) + 1), 4),
                    url=url,
                    source_type="web",
                )
            )
        return evidence


def _duckduckgo_region(language: str) -> str:
    normalized = str(language or "").lower().replace("_", "-")
    return {"zh-hans": "cn-zh", "zh-cn": "cn-zh", "en-us": "us-en"}.get(normalized, normalized or "wt-wt")


def _duckduckgo_result_url(value: object) -> str:
    raw_url = html.unescape(str(value or "")).strip()
    if raw_url.startswith("//"):
        raw_url = f"https:{raw_url}"
    parsed = urlparse(raw_url)
    redirect = parse_qs(parsed.query).get("uddg", [])
    return unquote(redirect[0]).strip() if redirect else raw_url


def _plain_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"<[^>]+>", "", text).strip()
