from __future__ import annotations

import re
from typing import Protocol, Sequence

from embeddings.providers import EmbeddingProvider
from models.schemas import Evidence
from rag.hybrid import bm25_scores, build_query_variants
from rag.keyword import asset_name_matches, explicit_file_names, fetch_keyword_rows
from rag.reranker import LexicalReranker, retain_relevant_items


class Retriever(Protocol):
    async def retrieve(
        self,
        *,
        workspace_id: int,
        project_id: int,
        question: str,
        top_k: int,
        filters: dict | None = None,
        embedding: EmbeddingProvider | None = None,
        retrieval_mode: str = "HYBRID",
        use_reranker: bool = False,
        fusion_method: str = "WEIGHTED_RRF",
        candidate_k: int | None = None,
        rank_constant: int = 60,
        vector_weight: float = 0.55,
        keyword_weight: float = 0.45,
        diversity_lambda: float = 0.9,
        rerank_top_k: int | None = None,
    ) -> list[Evidence]: ...


def _terms(text: str) -> set[str]:
    normalized = text.casefold()
    words = set(re.findall(r"[\w.-]+", normalized, flags=re.UNICODE))
    compact = "".join(ch for ch in normalized if not ch.isspace())
    words.update(
        compact[index : index + 2] for index in range(max(0, len(compact) - 1))
    )
    return {term for term in words if len(term) >= 2}


class InMemoryRetriever:
    """Deterministic lexical retriever with strict tenant/project isolation."""

    def __init__(self, chunks: Sequence[dict] | None = None):
        self.chunks = list(chunks or [])

    async def retrieve(
        self,
        *,
        workspace_id: int,
        project_id: int,
        question: str,
        top_k: int,
        filters: dict | None = None,
        retrieval_mode: str = "HYBRID",
        use_reranker: bool = False,
        embedding: EmbeddingProvider | None = None,
        fusion_method: str = "WEIGHTED_RRF",
        candidate_k: int | None = None,
        rank_constant: int = 60,
        vector_weight: float = 0.55,
        keyword_weight: float = 0.45,
        diversity_lambda: float = 0.9,
        rerank_top_k: int | None = None,
    ) -> list[Evidence]:
        filters = filters or {}
        allowed_assets = {str(value) for value in filters.get("assetIds", [])}
        file_names = explicit_file_names(question)
        candidates: list[dict] = []
        for chunk in self.chunks:
            if (
                chunk.get("workspace_id") != workspace_id
                or chunk.get("project_id") != project_id
            ):
                continue
            if allowed_assets and str(chunk.get("asset_id")) not in allowed_assets:
                continue
            if file_names and not asset_name_matches(
                str(chunk.get("asset_name") or chunk.get("source_name") or ""), file_names
            ):
                continue
            candidates.append(chunk)
        variants = build_query_variants(question)
        variant_scores = [
            bm25_scores(
                variant, [str(chunk.get("content", "")) for chunk in candidates]
            )
            for variant in variants or [question]
        ]
        scores = (
            [
                max(
                    (
                        score * (1.0 if index == 0 else 0.65)
                        for index, score in enumerate(row)
                    ),
                    default=0.0,
                )
                for row in zip(*variant_scores)
            ]
            if variant_scores
            else [0.0] * len(candidates)
        )
        ranked = sorted(
            zip(scores, candidates),
            key=lambda item: (-item[0], str(item[1].get("chunk_id", ""))),
        )
        matched = [item for item in ranked if item[0] > 0]
        if not matched and ranked and retrieval_mode.upper() != "KEYWORD":
            # The legacy in-memory adapter may have no multilingual embedding
            # provider. Keep semantic-mode behavior useful in local/dev mode
            # by returning the tenant-scoped best-effort candidates; Milvus
            # production retrieval always has dense recall for this case.
            matched = ranked
        items = [
            Evidence(
                id=f"E{index}",
                chunk_id=chunk["chunk_id"],
                content=chunk["content"],
                page_number=chunk.get("page_number"),
                section_title=chunk.get("section_title"),
                source_name=chunk.get("source_name", "项目资料"),
                asset_id=chunk.get("asset_id"),
                asset_name=chunk.get("asset_name", chunk.get("source_name")),
                score=round(score, 4),
            )
            for index, (score, chunk) in enumerate(matched[:top_k], start=1)
        ]
        if use_reranker:
            reranked = await LexicalReranker().rerank(question, items)
            return retain_relevant_items(question, reranked)
        return items


class PostgresKeywordRetriever:
    """Postgres adapter for the existing `asset_chunks` schema.

    Tenant filtering is mandatory in the SQL itself. The production hybrid
    adapter composes this PostgreSQL keyword path with Milvus vector search.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None

    async def start(self) -> None:
        from psycopg_pool import AsyncConnectionPool

        self._pool = AsyncConnectionPool(self.database_url, open=True)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def retrieve(
        self,
        *,
        workspace_id: int,
        project_id: int,
        question: str,
        top_k: int,
        filters: dict | None = None,
        retrieval_mode: str = "HYBRID",
        use_reranker: bool = False,
        embedding: EmbeddingProvider | None = None,
        fusion_method: str = "WEIGHTED_RRF",
        candidate_k: int | None = None,
        rank_constant: int = 60,
        vector_weight: float = 0.55,
        keyword_weight: float = 0.45,
        diversity_lambda: float = 0.9,
        rerank_top_k: int | None = None,
    ) -> list[Evidence]:
        if self._pool is None:
            raise RuntimeError("Postgres retriever has not been started")
        filters = filters or {}
        asset_ids = [int(value) for value in filters.get("assetIds", [])]
        rows = await fetch_keyword_rows(
            self._pool, workspace_id, project_id, question, asset_ids, top_k,
        )
        items = [
            Evidence(
                id=f"E{index}",
                chunk_id=row[0],
                content=row[5],
                source_name=row[2],
                page_number=row[3],
                section_title=row[4],
                asset_id=row[1],
                asset_name=row[2],
                score=float(row[6]),
                keyword_score=float(row[6]),
            )
            for index, row in enumerate(rows, start=1)
        ]
        if use_reranker:
            reranked = await LexicalReranker().rerank(question, items)
            return retain_relevant_items(question, reranked)
        return items
