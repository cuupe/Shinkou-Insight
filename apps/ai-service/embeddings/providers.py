from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class HashEmbeddingProvider:
    """Deterministic local embedding for development and offline tests."""

    def __init__(self, dimension: int = 384):
        self.model_name = "hash-embedding-v1"
        self.dimension = dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = [text[index : index + 2].casefold() for index in range(max(0, len(text) - 1))] or [text.casefold()]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 8) for value in vector]


class LangChainEmbeddingProvider:
    """Async adapter around any LangChain Embeddings implementation."""

    def __init__(self, embeddings: object, *, model_name: str, dimension: int):
        self.embeddings = embeddings
        self.model_name = model_name
        self.dimension = dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        method = getattr(self.embeddings, "aembed_documents", None)
        if method:
            return await method(texts)
        return await asyncio.to_thread(self.embeddings.embed_documents, texts)

    async def embed_query(self, text: str) -> list[float]:
        method = getattr(self.embeddings, "aembed_query", None)
        if method:
            return await method(text)
        return await asyncio.to_thread(self.embeddings.embed_query, text)


def build_embedding_provider(*, mode: str = "openai", api_key: str | None = None, base_url: str | None = None, model: str = "text-embedding-3-small", dimension: int = 384) -> EmbeddingProvider:
    normalized_mode = mode.casefold()
    if normalized_mode in {"openai", "compatible", "http"}:
        if not api_key:
            # External embedding credentials are injected per project at runtime.
            # Keep a deterministic local provider for bootstrapping and tests when
            # no project embedding has been configured yet.
            return HashEmbeddingProvider(dimension=dimension)
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:
            raise RuntimeError("langchain-openai is required for HTTP embeddings") from exc
        kwargs = {"model": model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        embeddings = OpenAIEmbeddings(**kwargs)
        return LangChainEmbeddingProvider(embeddings, model_name=model, dimension=dimension)
    if normalized_mode not in {"hash", "local"}:
        raise ValueError("EMBEDDING_MODE must be openai, compatible, http, hash, or local")
    return HashEmbeddingProvider(dimension=dimension)
