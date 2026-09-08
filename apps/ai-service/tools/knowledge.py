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
        )
