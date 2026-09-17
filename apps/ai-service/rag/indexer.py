from __future__ import annotations

import asyncio
import inspect
import math
from dataclasses import dataclass
from typing import Any

from documents.chunker import DocumentChunk, DocumentChunker
from embeddings.providers import EmbeddingProvider
from models.schemas import RetrievalItem
from rag.hybrid import (
    bm25_scores,
    build_query_variants,
    diversify_candidates,
    fuse_ranked_candidates,
)
from rag.reranker import LexicalReranker


def cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def rrf(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


@dataclass(slots=True)
class IndexedChunk:
    workspace_id: int
    project_id: int
    asset_id: int | str
    asset_name: str
    chunk: DocumentChunk
    embedding: list[float]


class InMemoryKnowledgeStore:
    """Hybrid vector/keyword store used for local mode and unit tests."""

    def __init__(self, embedding: EmbeddingProvider):
        self.embedding = embedding
        self.items: list[IndexedChunk] = []

    async def index(self, *, workspace_id: int, project_id: int, asset_id: int | str, asset_name: str, chunks: list[DocumentChunk], embedding: EmbeddingProvider | None = None, parser_version: str = "parser-v2") -> int:
        embedding = embedding or self.embedding
        self.items = [item for item in self.items if not (item.workspace_id == workspace_id and item.project_id == project_id and str(item.asset_id) == str(asset_id))]
        vectors = await embedding.embed_documents([chunk.content for chunk in chunks])
        self.items.extend(IndexedChunk(workspace_id, project_id, asset_id, asset_name, chunk, vector) for chunk, vector in zip(chunks, vectors))
        return len(chunks)

    async def retrieve(
        self,
        *,
        workspace_id: int,
        project_id: int,
        question: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
        retrieval_mode: str = "HYBRID",
        use_reranker: bool = False,
        embedding: EmbeddingProvider | None = None,
        fusion_method: str = "WEIGHTED_RRF",
        candidate_k: int | None = None,
        rank_constant: int = 60,
        vector_weight: float = 0.55,
        keyword_weight: float = 0.45,
        diversity_lambda: float = 0.9,
        query_variants: list[str] | None = None,
        rerank_top_k: int | None = None,
    ) -> list[RetrievalItem]:
        filters = filters or {}
        embedding = embedding or self.embedding
        allowed_assets = {str(value) for value in filters.get("assetIds", [])}
        candidates = [item for item in self.items if item.workspace_id == workspace_id and item.project_id == project_id and (not allowed_assets or str(item.asset_id) in allowed_assets)]
        mode = retrieval_mode.upper()
        candidate_limit = max(top_k, min(int(candidate_k or max(top_k * 4, 20)), 200))
        channels: dict[str, list[tuple[str, IndexedChunk, float]]] = {}
        vector_scores: dict[str, float] = {}
        if mode in {"VECTOR", "HYBRID"}:
            query_vector = await embedding.embed_query(question)
            vector_values = sorted(
                ((item, cosine(query_vector, item.embedding)) for item in candidates),
                key=lambda value: value[1],
                reverse=True,
            )[:candidate_limit]
            channels["vector"] = [
                (item.chunk.checksum[:16], item, score)
                for item, score in vector_values
            ]
            vector_scores = {item.chunk.checksum[:16]: score for item, score in vector_values}

        keyword_scores: dict[str, float] = {}
        if mode in {"KEYWORD", "HYBRID"}:
            variants = query_variants or build_query_variants(question)
            # The original query receives the full BM25 weight. Focused
            # variants are a cheap recall boost and never trigger an LLM call.
            keyword_values: dict[str, float] = {}
            for variant_index, variant in enumerate(variants or [question]):
                scores = bm25_scores(variant, [item.chunk.content for item in candidates])
                variant_weight = 1.0 if variant_index == 0 else 0.65
                for item, score in zip(candidates, scores):
                    key = item.chunk.checksum[:16]
                    keyword_values[key] = max(keyword_values.get(key, 0.0), score * variant_weight)
            keyword_values = {
                key: score for key, score in keyword_values.items() if score > 0
            }
            keyword_values = dict(
                sorted(keyword_values.items(), key=lambda value: value[1], reverse=True)[:candidate_limit]
            )
            by_key = {item.chunk.checksum[:16]: item for item in candidates}
            channels["keyword"] = [
                (key, by_key[key], score) for key, score in keyword_values.items()
            ]
            keyword_scores = keyword_values

        if mode == "VECTOR":
            fused = fuse_ranked_candidates(channels, method="LINEAR", weights={"vector": 1.0})
        elif mode == "KEYWORD":
            fused = fuse_ranked_candidates(channels, method="LINEAR", weights={"keyword": 1.0})
        else:
            fused = fuse_ranked_candidates(
                channels,
                method=fusion_method,
                weights={"vector": vector_weight, "keyword": keyword_weight},
                rank_constant=rank_constant,
                rank_window_size=candidate_limit,
            )
        fused = diversify_candidates(
            fused,
            top_k=max(top_k, min(candidate_limit, int(rerank_top_k or top_k))),
            content_fn=lambda item: item.chunk.content,
            diversity_lambda=diversity_lambda,
        )
        result: list[RetrievalItem] = []
        for rank, candidate in enumerate(fused, start=1):
            key = candidate.key
            result.append(
                RetrievalItem(
                    id=f"E{rank}",
                    chunk_id=key,
                    content=candidate.item.chunk.content,
                    source_name=candidate.item.asset_name,
                    page_number=candidate.item.chunk.page_number,
                    section_title=candidate.item.chunk.section_title,
                    score=round(candidate.score, 6),
                    asset_id=candidate.item.asset_id,
                    asset_name=candidate.item.asset_name,
                    vector_score=round(vector_scores[key], 6) if key in vector_scores else None,
                    keyword_score=round(keyword_scores[key], 6) if key in keyword_scores else None,
                    fusion_score=round(candidate.score, 6),
                    rerank_score=round(candidate.score, 6),
                )
            )
        if use_reranker:
            result = await LexicalReranker().rerank(question, result)
        return result[:top_k]


class KnowledgeIndexer:
    def __init__(self, parser: Any, chunker: Any, embedding: EmbeddingProvider, store: Any, graph_store: Any | None = None, graph_extractor: Any | None = None, cache: Any | None = None):
        self.parser = parser
        self.chunker = chunker
        self.embedding = embedding
        self.store = store
        self.graph_store = graph_store
        self.graph_extractor = graph_extractor
        self.cache = cache

    async def index_bytes(self, *, data: bytes, file_name: str, mime_type: str | None, workspace_id: int, project_id: int, asset_id: int | str, embedding: EmbeddingProvider | None = None, chunking: dict[str, Any] | None = None) -> dict[str, Any]:
        embedding = embedding or self.embedding
        parsed = await asyncio.to_thread(self.parser.parse_bytes, data, file_name=file_name, mime_type=mime_type)
        chunker = self.chunker if chunking is None else DocumentChunker.from_config(chunking)
        chunks = await asyncio.to_thread(chunker.split, parsed.documents)
        count = await self.store.index(workspace_id=workspace_id, project_id=project_id, asset_id=asset_id, asset_name=file_name, chunks=chunks, embedding=embedding, parser_version=parsed.parser_version)
        graph_entities = 0
        if self.graph_store and self.graph_extractor:
            for chunk in chunks:
                extracted = self.graph_extractor.extract(text=chunk.content, workspace_id=workspace_id, project_id=project_id, asset_id=asset_id, chunk_id=chunk.checksum[:16])
                if inspect.isawaitable(extracted):
                    nodes, edges = await extracted
                else:
                    nodes, edges = extracted
                await self.graph_store.upsert(nodes, edges)
                graph_entities += len(nodes)
        if self.cache is not None:
            await self.cache.bump_version("retrieval", {"workspaceId": workspace_id, "projectId": project_id})
        return {
            "chunk_count": count,
            "parser_version": parsed.parser_version,
            "embedding_model": embedding.model_name,
            "embedding_dimension": embedding.dimension,
            "graph_entities": graph_entities,
            "chunks": chunks,
            "warnings": list(parsed.warnings),
            "tools": list(parsed.tools),
            "metadata": dict(parsed.metadata),
        }
