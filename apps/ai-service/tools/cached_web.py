from __future__ import annotations

from typing import Any

from core.cache import CacheService
from models.schemas import Evidence
from tools.web import WebSearchProvider


class CachedWebSearch:
    """TTL cache for external search, keyed by provider configuration."""

    def __init__(self, provider: WebSearchProvider, cache: CacheService, *, ttl_seconds: int, provider_key: str = "default") -> None:
        self.provider = provider
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.provider_key = provider_key
        self.client = getattr(provider, "client", None)

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        identity: dict[str, Any] = {
            "provider": self.provider_key,
            "query": str(query).strip(),
            "topK": max(1, min(int(top_k), 20)),
        }
        async def load() -> list[dict[str, Any]]:
            result = await self.provider.search(query, top_k=top_k)
            return [item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) for item in result]

        value, _ = await self.cache.get_or_set(
            "web-search",
            identity,
            load,
            ttl_seconds=self.ttl_seconds,
        )
        return [Evidence.model_validate(item) for item in (value or [])]
