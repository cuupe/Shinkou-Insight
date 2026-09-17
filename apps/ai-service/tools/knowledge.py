# tools/knowledge.py

from embeddings.providers import EmbeddingProvider
from models.schemas import Evidence
from rag.retriever import Retriever


class KnowledgeTool:

    def __init__(
        self,
        retriever: Retriever,
        embedding_factory: object | None = None,
    ):
        self.retriever = retriever
        self.embedding_factory = embedding_factory

    async def search_knowledge(
        self,
        *,
        workspace_id: int,
        project_id: int,
        question: str,
        top_k: int = 5,
        filters: dict | None = None,
        retrieval_mode: str = "HYBRID",
        use_reranker: bool = False,
        embedding_config: dict | None = None,
        fusion_method: str = "WEIGHTED_RRF",
        candidate_k: int = 40,
        rank_constant: int = 60,
        vector_weight: float = 0.55,
        keyword_weight: float = 0.45,
        diversity_lambda: float = 0.9,
        rerank_top_k: int = 20,
    ) -> list[Evidence]:
        embedding: EmbeddingProvider | None = None
        if embedding_config and self.embedding_factory:
            embedding = self.embedding_factory(embedding_config)
        return await self.retriever.retrieve(
            workspace_id=workspace_id,
            project_id=project_id,
            question=question,
            top_k=top_k,
            filters=filters,
            retrieval_mode=retrieval_mode,
            use_reranker=use_reranker,
            embedding=embedding,
            fusion_method=fusion_method,
            candidate_k=candidate_k,
            rank_constant=rank_constant,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            diversity_lambda=diversity_lambda,
            rerank_top_k=rerank_top_k,
        )
