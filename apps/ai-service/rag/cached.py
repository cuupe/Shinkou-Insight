from __future__ import annotations

from typing import Any

from core.cache import CacheService
from models.schemas import Evidence
from rag.retriever import Retriever


class CachedRetriever:
    """Project/version scoped retrieval cache with complete query fingerprint."""

    def __init__(self, base: Retriever, cache: CacheService, *, ttl_seconds: int) -> None:
        self.base = base
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    async def retrieve(self, **kwargs: Any) -> list[Evidence]:
        workspace_id = kwargs.get("workspace_id")
        project_id = kwargs.get("project_id")
        scope = {"workspaceId": workspace_id, "projectId": project_id}
        version = await self.cache.get_version("retrieval", scope)
        embedding = kwargs.get("embedding")
        identity = {
            **scope,
            "question": kwargs.get("question", ""),
            "topK": kwargs.get("top_k", 8),
            "filters": kwargs.get("filters") or {},
            "retrievalMode": kwargs.get("retrieval_mode", "HYBRID"),
            "reranker": bool(kwargs.get("use_reranker", False)),
            "fusion": kwargs.get("fusion_method", "WEIGHTED_RRF"),
            "candidateK": kwargs.get("candidate_k"),
            "rankConstant": kwargs.get("rank_constant", 60),
            "vectorWeight": kwargs.get("vector_weight", 0.55),
            "keywordWeight": kwargs.get("keyword_weight", 0.45),
            "diversityLambda": kwargs.get("diversity_lambda", 0.9),
            "rerankTopK": kwargs.get("rerank_top_k"),
            "embeddingModel": getattr(embedding, "model_name", None),
            "embeddingDimension": getattr(embedding, "dimension", None),
        }
        async def load() -> list[dict[str, Any]]:
            result = await self.base.retrieve(**kwargs)
            return [item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) for item in result]

        value, _ = await self.cache.get_or_set(
            "retrieval",
            identity,
            load,
            ttl_seconds=self.ttl_seconds,
            version=version,
        )
        return [Evidence.model_validate(item) for item in (value or [])]
