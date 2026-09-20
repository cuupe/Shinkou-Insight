from __future__ import annotations

import hashlib
from typing import Any

from core.cache import CacheService
from embeddings.providers import EmbeddingProvider


class CachedEmbeddingProvider:
    """Content-addressed embedding cache safe for repeated retrieval/indexing."""

    def __init__(
        self, provider: EmbeddingProvider, cache: CacheService, *, ttl_seconds: int
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.model_name = provider.model_name
        self.dimension = provider.dimension

    async def close(self) -> None:
        close = getattr(self.provider, "close", None)
        if close:
            result = close()
            if hasattr(result, "__await__"):
                await result

    def _identity(self, text: str) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "dimension": self.dimension,
            "sha256": hashlib.sha256(str(text).encode("utf-8")).hexdigest(),
        }

    async def embed_query(self, text: str) -> list[float]:
        identity = self._identity(text)
        value, _ = await self.cache.get_or_set(
            "embedding:query",
            identity,
            lambda: self.provider.embed_query(text),
            ttl_seconds=self.ttl_seconds,
        )
        return [float(item) for item in value]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        output: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str, dict[str, Any]]] = []
        for index, text in enumerate(texts):
            value = await self.cache.get("embedding:document", self._identity(text))
            if value is None:
                missing.append((index, text, self._identity(text)))
            else:
                output[index] = [float(item) for item in value]
        if missing:
            vectors = await self.provider.embed_documents([item[1] for item in missing])
            for (index, _text, identity), vector in zip(missing, vectors):
                normalized = [float(item) for item in vector]
                output[index] = normalized
                await self.cache.set(
                    "embedding:document",
                    identity,
                    normalized,
                    ttl_seconds=self.ttl_seconds,
                )
        return [vector or [] for vector in output]
