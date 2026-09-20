from __future__ import annotations

import asyncio
from typing import Any

from core.cache import CacheService
from models.schemas import Evidence
from tools.source_content import hydrate_web_evidence
from tools.search_quality import (
    fallback_queries,
    focused_query,
    freshness_window,
    rank_web_evidence,
)
from tools.web import WebSearchProvider


class CachedWebSearch:
    """TTL cache for external search, keyed by provider configuration."""

    def __init__(
        self,
        provider: WebSearchProvider,
        cache: CacheService | None,
        *,
        ttl_seconds: int,
        provider_key: str = "default",
        parser: Any | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.provider_key = provider_key
        self.client = getattr(provider, "client", None)
        self.parser = parser

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        limit = max(1, min(int(top_k), 20))
        window = freshness_window(query)
        identity: dict[str, Any] = {
            "provider": self.provider_key,
            "query": str(query).strip(),
            "topK": limit,
            "contentMode": "query-grounded-fulltext-v2",
            "dateWindow": [day.isoformat() for day in window] if window else None,
            "language": getattr(self.provider, "search_language", None),
            "sources": sorted(getattr(self.provider, "sources", [])),
        }

        async def load() -> list[dict[str, Any]]:
            async def retrieve(search_query: str) -> list[Evidence]:
                return [
                    Evidence.model_validate(item)
                    for item in await self.provider.search(
                        search_query, top_k=min(20, max(10, limit * 3))
                    )
                ]

            async def verify(items: list[Evidence]) -> list[Evidence]:
                items = rank_web_evidence(query, items, 20)
                if self.client is not None:
                    items = await hydrate_web_evidence(
                        self.client, items, query, parser=self.parser
                    )
                return rank_web_evidence(query, items, limit, require_body=True)

            candidates = await retrieve(focused_query(query))
            result = await verify(candidates)
            if len(result) < min(limit, 2):
                # One bounded retry round, not recursive query drift. Always
                # validate against the ORIGINAL question and its date range.
                attempts = await asyncio.gather(
                    *(retrieve(value) for value in fallback_queries(query)),
                    return_exceptions=True,
                )
                seen_urls = {item.url for item in candidates}
                extra = [
                    item
                    for attempt in attempts
                    if isinstance(attempt, list)
                    for item in attempt
                    if item.url not in seen_urls
                ]
                result = rank_web_evidence(
                    query, [*result, *await verify(extra)], limit, require_body=True
                )
            return [
                (
                    item.model_dump(mode="json")
                    if hasattr(item, "model_dump")
                    else dict(item)
                )
                for item in result
            ]

        if self.cache is None:
            return [Evidence.model_validate(item) for item in await load()]
        value, _ = await self.cache.get_or_set(
            "web-search",
            identity,
            load,
            ttl_seconds=self.ttl_seconds,
        )
        # Re-check dates on cache hits (e.g. a "today" query crossing midnight).
        return rank_web_evidence(
            query,
            [Evidence.model_validate(item) for item in (value or [])],
            limit,
            require_body=True,
        )
