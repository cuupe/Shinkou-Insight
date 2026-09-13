from __future__ import annotations

import asyncio
import inspect
import math
from dataclasses import dataclass
from typing import Any

from documents.chunker import DocumentChunk, DocumentChunker
from embeddings.providers import EmbeddingProvider
from models.schemas import RetrievalItem
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

    async def retrieve(self, *, workspace_id: int, project_id: int, question: str, top_k: int, filters: dict[str, Any] | None = None, retrieval_mode: str = "HYBRID", use_reranker: bool = False, embedding: EmbeddingProvider | None = None) -> list[RetrievalItem]:
        filters = filters or {}
        embedding = embedding or self.embedding
        allowed_assets = {str(value) for value in filters.get("assetIds", [])}
        candidates = [item for item in self.items if item.workspace_id == workspace_id and item.project_id == project_id and (not allowed_assets or str(item.asset_id) in allowed_assets)]
        query_vector = await embedding.embed_query(question)
        query_terms = set(question.casefold().split())
        vector_ranked = sorted(candidates, key=lambda item: cosine(query_vector, item.embedding), reverse=True)
        keyword_ranked = sorted(candidates, key=lambda item: sum(term in item.chunk.content.casefold() for term in query_terms), reverse=True)
        vector_scores = {id(item): cosine(query_vector, item.embedding) for item in candidates}
        keyword_scores = {id(item): float(sum(term in item.chunk.content.casefold() for term in query_terms)) for item in candidates}
        if retrieval_mode.upper() == "VECTOR":
            ordered = vector_ranked
        elif retrieval_mode.upper() == "KEYWORD":
            ordered = keyword_ranked
        else:
            scores = {id(item): rrf(index + 1) for index, item in enumerate(vector_ranked)}
            for index, item in enumerate(keyword_ranked):
                scores[id(item)] = scores.get(id(item), 0) + rrf(index + 1)
            ordered = sorted(candidates, key=lambda item: scores[id(item)], reverse=True)
        result: list[RetrievalItem] = []
        for rank, item in enumerate(ordered[:top_k], start=1):
            keyword_score = keyword_scores[id(item)]
            if keyword_score <= 0 and retrieval_mode.upper() == "KEYWORD":
                continue
            result.append(RetrievalItem(id=f"E{rank}", chunk_id=item.chunk.checksum[:16], content=item.chunk.content, source_name=item.asset_name, page_number=item.chunk.page_number, section_title=item.chunk.section_title, score=round(vector_scores[id(item)], 4), asset_id=item.asset_id, asset_name=item.asset_name, vector_score=round(vector_scores[id(item)], 4), keyword_score=keyword_score, fusion_score=round((rrf(rank) + rrf(rank)), 4), rerank_score=round(vector_scores[id(item)], 4)))
        if use_reranker:
            result = await LexicalReranker().rerank(question, result)
        return result


class KnowledgeIndexer:
    def __init__(self, parser: Any, chunker: Any, embedding: EmbeddingProvider, store: Any, graph_store: Any | None = None, graph_extractor: Any | None = None):
        self.parser = parser
        self.chunker = chunker
        self.embedding = embedding
        self.store = store
        self.graph_store = graph_store
        self.graph_extractor = graph_extractor

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
        return {"chunk_count": count, "parser_version": parsed.parser_version, "embedding_model": embedding.model_name, "embedding_dimension": embedding.dimension, "graph_entities": graph_entities, "chunks": chunks}
