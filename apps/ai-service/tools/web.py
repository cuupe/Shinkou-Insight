from __future__ import annotations

import hashlib
import html
import re
from typing import Protocol

import httpx

from models.schemas import Evidence


class WebSearchProvider(Protocol):
    async def search(self, query: str, top_k: int = 5) -> list[Evidence]: ...


class WebSearchError(RuntimeError):
    """Base error for an external search provider."""


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
                    "count": max(1, min(top_k, 20)),
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
        evidence: list[Evidence] = []
        for item in results[:top_k]:
            title = _plain_text(item.get("title"))
            url = str(item.get("url") or "").strip()
            description = _plain_text(item.get("description"))
            if not title or not url or not description:
                continue
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


def _plain_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"<[^>]+>", "", text).strip()
