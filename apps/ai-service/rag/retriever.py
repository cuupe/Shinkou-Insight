from __future__ import annotations

import re
from typing import Protocol, Sequence

from embeddings.providers import EmbeddingProvider
from models.schemas import Evidence
from rag.hybrid import bm25_scores, build_query_variants, extract_search_terms


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
        candidates: list[dict] = []
        for chunk in self.chunks:
            if (
                chunk.get("workspace_id") != workspace_id
                or chunk.get("project_id") != project_id
            ):
                continue
            if allowed_assets and str(chunk.get("asset_id")) not in allowed_assets:
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
        return [
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
        variants = build_query_variants(question)
        terms = extract_search_terms(" ".join(variants), max_terms=64)
        patterns: list[str] = []
        for term in terms:
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            patterns.append(f"%{escaped}%")
        patterns = patterns or ["%__shinkou_no_keyword_match__%"]
        sql = """
            SELECT c.id, c.asset_id, a.name, c.page_number, c.section_title, c.content
            FROM asset_chunks c
            JOIN knowledge_assets a ON a.id = c.asset_id
            JOIN projects p ON p.id = a.project_id
            WHERE p.workspace_id = %s AND p.id = %s AND a.index_status = 'SUCCESS'
              AND (c.search_vector @@ plainto_tsquery('simple', %s) OR c.content ILIKE ANY(%s))
        """
        params: list = [workspace_id, project_id, question, patterns]
        if asset_ids:
            sql += " AND c.asset_id = ANY(%s)"
            params.append(asset_ids)
        sql += " ORDER BY a.updated_at DESC, c.chunk_index LIMIT %s"
        params.append(top_k)
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(sql, params)
                rows = await cursor.fetchall()
        return [
            Evidence(
                id=f"E{index}",
                chunk_id=row[0],
                content=row[5],
                source_name=row[2],
                page_number=row[3],
                section_title=row[4],
                asset_id=row[1],
                asset_name=row[2],
                score=1.0,
            )
            for index, row in enumerate(rows, start=1)
        ]
