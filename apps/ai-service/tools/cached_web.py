from __future__ import annotations

import asyncio
from typing import Any

from core.cache import CacheService
from core.clock import current_date
from models.schemas import Evidence
from tools.source_content import hydrate_web_evidence
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
        return await self.search_semantic(query, top_k)

    async def search_semantic(self, query: str, top_k: int = 5, *, sources: list[str] | None = None) -> list[Evidence]:
        """Cache one explicit model-selected query, never launch hidden fallback queries."""
        limit = max(1, min(int(top_k), 20))
        identity = dict(provider=self.provider_key, query=query.strip(), topK=limit,
                        sources=sources or ["general"], contentMode="semantic-fulltext-v1", asOfDate=current_date().isoformat())

        async def load():
            if hasattr(self.provider, "search_semantic"):
                raw = await self.provider.search_semantic(query, top_k=min(10, limit * 3), sources=sources)
            else:
                raw = await self.provider.search(query, top_k=min(10, limit * 3))
            items = [Evidence.model_validate(item) for item in raw]
            if self.client:
                items = await hydrate_web_evidence(self.client, items, query, parser=self.parser, semantic=True)
            seen = set()
            selected = []
            for item in items:
                if item.url and item.url not in seen and item.content_kind == "fulltext":
                    seen.add(item.url)
                    selected.append(item.model_dump(mode="json"))
            return selected[:limit]

        if self.cache is None:
            return [Evidence.model_validate(item) for item in await load()]
        value, _ = await self.cache.get_or_set("web-search", identity, load, ttl_seconds=self.ttl_seconds)
        return [Evidence.model_validate(item) for item in value or []]
