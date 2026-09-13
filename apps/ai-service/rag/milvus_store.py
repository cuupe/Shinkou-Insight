from __future__ import annotations

import asyncio
import re
from typing import Any

from embeddings.providers import EmbeddingProvider
from models.schemas import RetrievalItem
from rag.indexer import rrf
from rag.reranker import LexicalReranker


def _keyword_terms(question: str, max_terms: int = 64) -> list[str]:
    """Extract searchable terms without treating a Chinese question as one token.

    PostgreSQL's ``simple`` text search configuration does not segment Chinese
    naturally. A query such as ``乎古哀是什么时代的人`` can therefore become a
    single lexeme that never matches the standalone name ``乎古哀`` in a chunk.
    Keep exact short runs and add Chinese n-grams so entity names remain
    discoverable even when the surrounding question is longer.
    """

    normalized = re.sub(r"\s+", " ", str(question or "").casefold()).strip()
    terms: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip()
        if len(value) < 2 or value in seen or len(terms) >= max_terms:
            return
        seen.add(value)
        terms.append(value)

    for token in re.findall(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]+", normalized):
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if len(token) <= 6:
                add(token)
            for width in (3, 2):
                for index in range(max(0, len(token) - width + 1)):
                    add(token[index : index + width])
        else:
            add(token)
        if len(terms) >= max_terms:
            break
    return terms


def _like_patterns(terms: list[str]) -> list[str]:
    return [
        "%"
        + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        + "%"
        for term in terms
    ]


class MilvusKnowledgeStore:
    """Hybrid knowledge store backed by PostgreSQL metadata and Milvus vectors.

    PostgreSQL remains the source of truth for chunk text, citations and
    keyword search. Milvus stores only the vector plus the PostgreSQL chunk id
    and tenant metadata needed for filtered ANN search.
    """

    VECTOR_FIELD = "embedding"
    OUTPUT_FIELDS = ["workspace_id", "project_id", "asset_id"]

    def __init__(
        self,
        database_url: str,
        milvus_uri: str,
        embedding: EmbeddingProvider,
        *,
        milvus_token: str | None = None,
        milvus_db_name: str = "default",
        collection_name: str = "shinkou_knowledge_chunks",
        min_size: int = 2,
        max_size: int = 10,
    ):
        self.database_url = database_url
        self.milvus_uri = milvus_uri
        self.milvus_token = milvus_token
        self.milvus_db_name = milvus_db_name
        self.collection_name = collection_name
        self.embedding = embedding
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Any | None = None
        self.client: Any | None = None

    async def start(self) -> None:
        from psycopg_pool import AsyncConnectionPool

        self.pool = AsyncConnectionPool(
            self.database_url,
            min_size=self.min_size,
            max_size=self.max_size,
            open=True,
        )
        try:
            self.client = await asyncio.to_thread(self._connect_milvus)
        except Exception:
            await self.pool.close()
            self.pool = None
            raise

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
        if self.client:
            close = getattr(self.client, "close", None)
            if close:
                await asyncio.to_thread(close)
            self.client = None

    def _connect_milvus(self) -> Any:
        from pymilvus import DataType, MilvusClient

        kwargs: dict[str, Any] = {"uri": self.milvus_uri}
        if self.milvus_token:
            kwargs["token"] = self.milvus_token
        if self.milvus_db_name:
            kwargs["db_name"] = self.milvus_db_name
        client = MilvusClient(**kwargs)
        if not client.has_collection(collection_name=self.collection_name):
            schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True)
            schema.add_field(field_name="workspace_id", datatype=DataType.INT64)
            schema.add_field(field_name="project_id", datatype=DataType.INT64)
            schema.add_field(field_name="asset_id", datatype=DataType.INT64)
            schema.add_field(
                field_name=self.VECTOR_FIELD,
                datatype=DataType.FLOAT_VECTOR,
                dim=self.embedding.dimension,
            )
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name=self.VECTOR_FIELD,
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )
            client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=index_params,
                consistency_level="Bounded",
            )
        else:
            description = client.describe_collection(collection_name=self.collection_name)
            vector_field = next(
                (field for field in description.get("fields", []) if field.get("name") == self.VECTOR_FIELD),
                None,
            )
            configured_dimension = int((vector_field or {}).get("params", {}).get("dim", 0))
            if configured_dimension and configured_dimension != self.embedding.dimension:
                raise RuntimeError(
                    f"Milvus collection {self.collection_name!r} has dimension "
                    f"{configured_dimension}, expected {self.embedding.dimension}; "
                    "use a new collection name when changing embedding dimensions"
                )
        client.load_collection(collection_name=self.collection_name)
        return client

    def _require_started(self) -> tuple[Any, Any]:
        if self.pool is None or self.client is None:
            raise RuntimeError("Milvus knowledge store has not been started")
        return self.pool, self.client

    @staticmethod
    def _asset_id(value: int | str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Milvus requires numeric asset ids") from exc

    @staticmethod
    def _milvus_filter(workspace_id: int, project_id: int, asset_ids: list[int]) -> str:
        expression = f"workspace_id == {int(workspace_id)} and project_id == {int(project_id)}"
        if asset_ids:
            expression += f" and asset_id in [{', '.join(str(value) for value in asset_ids)}]"
        return expression

    async def index(
        self,
        *,
        workspace_id: int,
        project_id: int,
        asset_id: int | str,
        asset_name: str,
        chunks: list[Any],
        embedding: EmbeddingProvider | None = None,
        parser_version: str = "parser-v2",
    ) -> int:
        pool, client = self._require_started()
        numeric_asset_id = self._asset_id(asset_id)
        embedding = embedding or self.embedding
        if embedding.dimension != self.embedding.dimension:
            raise ValueError(
                f"Embedding dimension {embedding.dimension} does not match the active Milvus collection dimension {self.embedding.dimension}"
            )
        vectors = await embedding.embed_documents([chunk.content for chunk in chunks])

        # Remove the previous asset snapshot first. PostgreSQL and Milvus are
        # separate stores, so a failed re-index is safe to retry and never
        # leaves old vectors eligible for this asset.
        await asyncio.to_thread(
            client.delete,
            collection_name=self.collection_name,
            filter=f"asset_id == {numeric_asset_id}",
        )

        milvus_rows: list[dict[str, Any]] = []
        async with pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("DELETE FROM asset_chunks WHERE asset_id = %s", (numeric_asset_id,))
                for chunk, vector in zip(chunks, vectors):
                    await cursor.execute(
                        """
                        INSERT INTO asset_chunks(
                            asset_id, chunk_index, content, page_number, section_title,
                            start_offset, end_offset, parser_version, chunking_version,
                            checksum, embedding_model
                        )
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING id
                        """,
                        (
                            numeric_asset_id,
                            chunk.chunk_index,
                            chunk.content,
                            chunk.page_number,
                            chunk.section_title,
                            chunk.start_offset,
                            chunk.end_offset,
                            parser_version,
                            "chunker-v2",
                            chunk.checksum,
                            embedding.model_name,
                        ),
                    )
                    row = await cursor.fetchone()
                    if row is None:
                        raise RuntimeError("PostgreSQL did not return the inserted chunk id")
                    milvus_rows.append(
                        {
                            "chunk_id": int(row[0]),
                            "workspace_id": int(workspace_id),
                            "project_id": int(project_id),
                            "asset_id": numeric_asset_id,
                            self.VECTOR_FIELD: vector,
                        }
                    )
                await connection.commit()

        if milvus_rows:
            await asyncio.to_thread(
                client.insert,
                collection_name=self.collection_name,
                data=milvus_rows,
            )
            flush = getattr(client, "flush", None)
            if flush:
                await asyncio.to_thread(flush, collection_name=self.collection_name)
        return len(milvus_rows)

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
    ) -> list[RetrievalItem]:
        pool, client = self._require_started()
        embedding = embedding or self.embedding
        if embedding.dimension != self.embedding.dimension:
            raise ValueError(
                f"Embedding dimension {embedding.dimension} does not match the active Milvus collection dimension {self.embedding.dimension}"
            )
        filters = filters or {}
        asset_ids = [int(value) for value in filters.get("assetIds", [])]
        mode = retrieval_mode.upper()
        candidate_limit = max(top_k, 20)

        vector_hits: list[dict[str, Any]] = []
        if mode in {"VECTOR", "HYBRID"}:
            query_vector = await embedding.embed_query(question)
            vector_hits = await asyncio.to_thread(
                self._search_vectors,
                client,
                self.collection_name,
                query_vector,
                self._milvus_filter(workspace_id, project_id, asset_ids),
                candidate_limit,
            )

        vector_ids = [int(hit["id"]) for hit in vector_hits if hit.get("id") is not None]
        vector_rows = await self._fetch_rows_by_ids(
            pool,
            workspace_id,
            project_id,
            vector_ids,
            asset_ids,
        )
        vector_row_ids = {int(row[0]) for row in vector_rows}
        vector_rank: dict[int, tuple[int, float]] = {}
        for rank, hit in enumerate(vector_hits, start=1):
            if hit.get("id") is None:
                continue
            chunk_id = int(hit["id"])
            if chunk_id in vector_row_ids:
                vector_rank[chunk_id] = (rank, float(hit["score"]))

        keyword_rows: list[tuple] = []
        if mode in {"KEYWORD", "HYBRID"}:
            keyword_rows = await self._fetch_keyword_rows(
                pool,
                workspace_id,
                project_id,
                question,
                asset_ids,
                candidate_limit,
            )
        keyword_rank = {
            int(row[0]): (rank, float(row[6]))
            for rank, row in enumerate(keyword_rows, start=1)
        }

        rows = {int(row[0]): row for row in [*vector_rows, *keyword_rows]}
        ids = list(dict.fromkeys([*vector_rank.keys(), *keyword_rank.keys()]))
        ids.sort(
            key=lambda chunk_id: (
                rrf(vector_rank[chunk_id][0]) if chunk_id in vector_rank else 0
            )
            + (rrf(keyword_rank[chunk_id][0]) if chunk_id in keyword_rank else 0),
            reverse=True,
        )

        result: list[RetrievalItem] = []
        for rank, chunk_id in enumerate(ids[:top_k], start=1):
            row = rows[chunk_id]
            fusion = (rrf(vector_rank[chunk_id][0]) if chunk_id in vector_rank else 0) + (
                rrf(keyword_rank[chunk_id][0]) if chunk_id in keyword_rank else 0
            )
            vector_score = vector_rank.get(chunk_id, (0, None))[1]
            keyword_score = keyword_rank.get(chunk_id, (0, None))[1]
            result.append(
                RetrievalItem(
                    id=f"E{rank}",
                    chunk_id=chunk_id,
                    asset_id=row[1],
                    asset_name=row[2],
                    source_name=row[2],
                    page_number=row[3],
                    section_title=row[4],
                    content=row[5],
                    score=round(fusion, 6),
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                    fusion_score=round(fusion, 6),
                    rerank_score=round(fusion, 6),
                )
            )
        if use_reranker:
            result = await LexicalReranker().rerank(question, result)
        return result

    @staticmethod
    def _search_vectors(
        client: Any,
        collection_name: str,
        query_vector: list[float],
        expression: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        response = client.search(
            collection_name=collection_name,
            data=[query_vector],
            anns_field=MilvusKnowledgeStore.VECTOR_FIELD,
            filter=expression,
            limit=limit,
            output_fields=MilvusKnowledgeStore.OUTPUT_FIELDS,
            search_params={"metric_type": "COSINE", "params": {}},
        )
        return [
            {
                "id": hit.get("id", hit.get("chunk_id")),
                "score": hit.get("distance", hit.get("score", 0.0)),
            }
            for hit in (response[0] if response else [])
        ]

    async def _fetch_rows_by_ids(
        self,
        pool: Any,
        workspace_id: int,
        project_id: int,
        chunk_ids: list[int],
        asset_ids: list[int],
    ) -> list[tuple]:
        if not chunk_ids:
            return []
        base = """
            SELECT c.id,c.asset_id,a.name,c.page_number,c.section_title,c.content,0::float AS score
            FROM asset_chunks c
            JOIN knowledge_assets a ON a.id = c.asset_id
            JOIN projects p ON p.id = a.project_id
            WHERE p.workspace_id = %s AND p.id = %s
              AND a.index_status IN ('SUCCESS','INDEXED')
              AND c.id = ANY(%s)
        """
        params: list[Any] = [workspace_id, project_id, chunk_ids]
        if asset_ids:
            base += " AND c.asset_id = ANY(%s)"
            params.append(asset_ids)
        async with pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(base, params)
                return await cursor.fetchall()

    async def _fetch_keyword_rows(
        self,
        pool: Any,
        workspace_id: int,
        project_id: int,
        question: str,
        asset_ids: list[int],
        limit: int,
    ) -> list[tuple]:
        patterns = _like_patterns(_keyword_terms(question))
        base = """
            FROM asset_chunks c
            JOIN knowledge_assets a ON a.id = c.asset_id
            JOIN projects p ON p.id = a.project_id
            WHERE p.workspace_id = %s AND p.id = %s
              AND a.index_status IN ('SUCCESS','INDEXED')
              AND (
                    c.search_vector @@ plainto_tsquery('simple', %s)
                    OR c.content ILIKE ANY(%s)
              )
        """
        params: list[Any] = [workspace_id, project_id, question, patterns]
        if asset_ids:
            base += " AND c.asset_id = ANY(%s)"
            params.append(asset_ids)
        sql = (
            "SELECT c.id,c.asset_id,a.name,c.page_number,c.section_title,c.content,"
            "GREATEST("
            "ts_rank_cd(c.search_vector, plainto_tsquery('simple', %s)),"
            "CASE WHEN c.content ILIKE ANY(%s) THEN 0.1 ELSE 0 END"
            ") AS score "
            + base
            + " ORDER BY score DESC, c.chunk_index LIMIT %s"
        )
        params = [question, patterns, *params, limit]
        async with pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(sql, params)
                return await cursor.fetchall()
