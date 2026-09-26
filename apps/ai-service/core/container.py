from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import httpx

from agents.runtime import AgentRuntime
from config import Settings
from core.events import EventBus
from core.cache import CacheService
from core.repository import DurableRunRepository
from documents.chunker import DocumentChunker
from documents.parser import DocumentParser
from embeddings.cached import CachedEmbeddingProvider
from embeddings.providers import EmbeddingProvider, build_embedding_provider
from graph.store import (
    GraphExtractor,
    LlmGraphExtractor,
    MemoryGraphStore,
    Neo4jGraphStore,
)
from models.llm import LangChainModelGateway, ModelGateway, build_model_gateway
from rag.indexer import InMemoryKnowledgeStore, KnowledgeIndexer
from rag.milvus_store import MilvusKnowledgeStore
from rag.cached import CachedRetriever
from storage.files import LocalFileStorage, MinioFileStorage
from tools.graph import GraphSearchTool
from tools.knowledge import KnowledgeTool
from tools.loader import CustomToolLoadReport, load_custom_tools
from tools.mcp_bridge import MCPToolBridge, register_mcp_tools
from tools.registry import ToolRegistry, ToolSpec
from tools.multi_source_search import MultiSourceWebSearch
from tools.web import (
    DEFAULT_DUCKDUCKGO_BASE_URL,
    BraveWebSearch,
    DisabledWebSearch,
    DuckDuckGoWebSearch,
    WebSearchProvider,
)
from tools.cached_web import CachedWebSearch
from tools.document_generation import DocumentGenerationTool


@dataclass(slots=True)
class ServiceContainer:
    """Owns provider wiring and lifecycle for one AI-service process."""

    runtime: AgentRuntime
    indexer: KnowledgeIndexer
    storage: Any
    graph_store: Any
    embedding: EmbeddingProvider
    events: EventBus
    repository: InMemoryRunRepository
    model_gateway: ModelGateway
    embedding_factory: Callable[[dict[str, Any] | None], EmbeddingProvider]
    mcp_bridge: MCPToolBridge | None
    milvus_store: MilvusKnowledgeStore | None
    neo4j_store: Neo4jGraphStore | None
    http_client: httpx.AsyncClient | None
    custom_tools_report: CustomToolLoadReport
    custom_tools_dir: str
    custom_tools_enabled: bool
    custom_tools_strict: bool
    custom_tools_modules: list[str]
    cache: CacheService

    @classmethod
    async def build(cls, settings: Settings) -> "ServiceContainer":
        events = EventBus()
        cache = await CacheService.create(
            enabled=settings.cache_enabled,
            backend=settings.cache_backend,
            redis_url=settings.redis_url,
            namespace=settings.cache_namespace,
            max_entries=settings.cache_max_entries,
        )
        repository = DurableRunRepository(events, settings.redis_url)
        await repository.start()
        http_client: httpx.AsyncClient | None = None
        milvus_store: MilvusKnowledgeStore | None = None
        neo4j_store: Neo4jGraphStore | None = None
        mcp_bridge: MCPToolBridge | None = None

        try:
            model = cls._build_model(settings, http_client)
            if isinstance(model, LangChainModelGateway):
                http_client = model.client
            elif http_client is None and settings.llm_mode.lower() != "mock":
                http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(settings.llm_timeout_seconds)
                )

            # Project-level external Embedding configs are opt-in. The base
            # provider must stay local even if an external key exists in the
            # process environment; runtime requests explicitly inject the API
            # config only after a user enables it in the workspace settings.
            base_embedding = build_embedding_provider(
                mode="hash",
                model="hash-embedding-v1",
                dimension=settings.embedding_dimension,
            )
            embedding = CachedEmbeddingProvider(
                base_embedding, cache, ttl_seconds=settings.cache_embedding_ttl_seconds
            )

            def embedding_factory(
                config: dict[str, Any] | None = None,
            ) -> EmbeddingProvider:
                if not config:
                    return embedding
                provider = build_embedding_provider(
                    mode=str(config.get("mode", settings.embedding_mode)),
                    api_key=str(config.get("apiKey") or config.get("api_key") or ""),
                    base_url=str(config.get("baseUrl") or config.get("base_url") or "")
                    or None,
                    model=str(config.get("model", settings.embedding_model)),
                    dimension=int(
                        config.get("dimension", settings.embedding_dimension)
                    ),
                )
                return CachedEmbeddingProvider(
                    provider, cache, ttl_seconds=settings.cache_embedding_ttl_seconds
                )

            storage = cls._build_storage(settings)
            graph_store, neo4j_store = cls._build_graph_store(settings)
            retriever, index_store, milvus_store = await cls._build_retriever(
                settings, embedding, cache
            )
            parser = DocumentParser(
                ocr_enabled=settings.file_ocr_enabled,
                ocr_languages=settings.file_ocr_languages,
                pdf_dpi=settings.file_pdf_dpi,
                max_ocr_pages=settings.file_max_ocr_pages,
                max_video_frames=settings.file_max_video_frames,
                whisper_model=settings.file_whisper_model,
                whisper_device=settings.file_whisper_device,
                whisper_compute_type=settings.file_whisper_compute_type,
                external_timeout_seconds=settings.file_analysis_timeout_seconds,
            )
            graph_extractor = (
                LlmGraphExtractor(model)
                if settings.graph_extraction_mode.lower() == "llm"
                and settings.llm_mode.lower() != "mock"
                else GraphExtractor()
            )
            indexer = KnowledgeIndexer(
                parser,
                DocumentChunker(),
                embedding,
                index_store,
                graph_store,
                graph_extractor,
                cache=cache,
            )
            web_search = cls._build_web_search(settings, http_client)
            if http_client is None and hasattr(web_search, "client"):
                http_client = web_search.client
            if not isinstance(web_search, DisabledWebSearch):
                web_search = CachedWebSearch(
                    web_search,
                    cache,
                    ttl_seconds=settings.cache_web_ttl_seconds,
                    provider_key=f"{settings.web_search_provider}:{settings.web_search_base_url}",
                    parser=parser,
                )

            # Registry events are used by asynchronous tools/chains. Existing
            # agent search calls stay event-silent and keep their richer
            # runtime-level progress messages, avoiding duplicate UI events.
            tools = ToolRegistry(event_sink=events.publish)
            knowledge = KnowledgeTool(retriever, embedding_factory=embedding_factory)
            tools.register(
                ToolSpec(
                    name="search_knowledge",
                    description="Search project-scoped knowledge base evidence.",
                    permission="READ",
                    timeout_seconds=min(
                        settings.request_timeout_seconds,
                        settings.knowledge_timeout_seconds,
                    ),
                    input_schema={
                        "type": "object",
                        "required": ["workspace_id", "project_id", "question"],
                        "properties": {
                            "workspace_id": {"type": "integer"},
                            "project_id": {"type": "integer"},
                            "question": {"type": "string", "maxLength": 20_000},
                            "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                            "retrieval_mode": {
                                "type": "string",
                                "enum": ["VECTOR", "KEYWORD", "HYBRID"],
                            },
                            "use_reranker": {"type": "boolean"},
                            "fusion_method": {
                                "type": "string",
                                "enum": ["RRF", "WEIGHTED_RRF", "LINEAR"],
                            },
                            "candidate_k": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 200,
                            },
                            "rank_constant": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 200,
                            },
                            "vector_weight": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "keyword_weight": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "diversity_lambda": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "rerank_top_k": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 200,
                            },
                        },
                    },
                ),
                knowledge.search_knowledge,
            )
            graph_tool = GraphSearchTool(graph_store)
            tools.register(
                ToolSpec(
                    name="search_graph",
                    description="Search project-scoped entities and relationships.",
                    permission="READ",
                    timeout_seconds=min(settings.request_timeout_seconds, 8),
                    input_schema={
                        "type": "object",
                        "required": ["workspace_id", "project_id", "query"],
                        "properties": {
                            "workspace_id": {"type": "integer"},
                            "project_id": {"type": "integer"},
                            "query": {"type": "string", "maxLength": 20_000},
                        },
                    },
                ),
                graph_tool.search_graph,
            )
            if not isinstance(web_search, DisabledWebSearch):
                tools.register(
                    ToolSpec(
                        name="search_web",
                        description="Search the configured external web provider.",
                        permission="READ",
                        timeout_seconds=min(settings.request_timeout_seconds, 30),
                        input_schema={
                            "type": "object",
                            "required": ["query"],
                            "properties": {
                                "query": {"type": "string", "maxLength": 2_000}
                            },
                        },
                    ),
                    web_search.search,
                )
            document_generator = DocumentGenerationTool()
            tools.register(
                ToolSpec(
                    name="generate_document_bundle",
                    version="1.0",
                    description=(
                        "Render a final Markdown report into native Markdown, DOCX, PDF and PPTX files. "
                        "For DOCX/PDF/PPTX, parse headings, paragraphs, lists, tables, links, emphasis and code "
                        "into the target format; never copy Markdown markers as visible document text."
                    ),
                    permission="WRITE",
                    timeout_seconds=120,
                    max_concurrency=2,
                    input_schema={
                        "type": "object",
                        "required": ["title", "markdown", "formats", "output_dir"],
                        "properties": {
                            "title": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 200,
                            },
                            "markdown": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 300_000,
                            },
                            "formats": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 4,
                                "items": {
                                    "type": "string",
                                    "enum": ["markdown", "docx", "pdf", "pptx"],
                                },
                            },
                            "output_dir": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 1_000,
                            },
                            "sources": {
                                "type": "array",
                                "maxItems": 30,
                                "items": {"type": "object"},
                            },
                        },
                    },
                ),
                document_generator.generate,
            )
            custom_tools_report = load_custom_tools(
                tools,
                settings.custom_tools_dir,
                enabled=settings.custom_tools_enabled,
                strict=settings.custom_tools_strict,
                modules=settings.custom_tools_modules,
            )
            if settings.mcp_enabled and settings.mcp_url:
                mcp_bridge = MCPToolBridge(
                    settings.mcp_url,
                    api_key=settings.mcp_api_key,
                    allowed_tools=set(settings.mcp_allowed_tools),
                    timeout_seconds=settings.mcp_timeout_seconds,
                )
                await register_mcp_tools(tools, mcp_bridge)

            runtime = AgentRuntime(
                model=model,
                retriever=retriever,
                web_search=web_search,
                tools=tools,
                repository=repository,
                events=events,
                internal_api_key=settings.internal_api_key,
                max_evidence=settings.max_evidence,
                callback_client=http_client,
                max_retries=settings.max_retries,
                structured_output_method=settings.llm_structured_output_method,
                graph_store=graph_store,
                file_parser=parser,
                file_storage=storage,
                file_analysis_timeout_seconds=settings.file_analysis_timeout_seconds,
                file_analysis_max_chars=settings.file_analysis_max_chars,
                cache=cache,
                web_cache_ttl_seconds=settings.cache_web_ttl_seconds,
                agent_worker_urls=(
                    settings.agent_worker_urls
                    if settings.agent_transport.lower() == "http"
                    else None
                ),
                agent_worker_role=settings.agent_worker_role,
            )
            return cls(
                runtime=runtime,
                indexer=indexer,
                storage=storage,
                graph_store=graph_store,
                embedding=embedding,
                events=events,
                repository=repository,
                model_gateway=model,
                embedding_factory=embedding_factory,
                mcp_bridge=mcp_bridge,
                milvus_store=milvus_store,
                neo4j_store=neo4j_store,
                http_client=http_client,
                custom_tools_report=custom_tools_report,
                custom_tools_dir=settings.custom_tools_dir,
                custom_tools_enabled=settings.custom_tools_enabled,
                custom_tools_strict=settings.custom_tools_strict,
                custom_tools_modules=list(settings.custom_tools_modules),
                cache=cache,
            )
        except Exception:
            if milvus_store:
                await milvus_store.close()
            if neo4j_store:
                await neo4j_store.close()
            if mcp_bridge:
                await mcp_bridge.close()
            if http_client:
                await http_client.aclose()
            await repository.close()
            await cache.close()
            raise

    @staticmethod
    def _build_model(
        settings: Settings, http_client: httpx.AsyncClient | None
    ) -> ModelGateway:
        mode = settings.llm_mode.lower()
        if mode == "mock":
            if settings.app_env.lower() not in {"test", "ci"}:
                raise RuntimeError(
                    "LLM_MODE=mock is test-only; configure an OpenAI-compatible provider"
                )
        return build_model_gateway(
            mode=mode,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.max_retries,
            client=http_client,
            structured_output_method=settings.llm_structured_output_method,
        )

    @staticmethod
    def _build_storage(settings: Settings) -> Any:
        if settings.storage_mode.lower() == "minio":
            if not all(
                [
                    settings.minio_endpoint,
                    settings.minio_access_key,
                    settings.minio_secret_key,
                ]
            ):
                raise RuntimeError(
                    "MINIO_ENDPOINT, MINIO_ACCESS_KEY and MINIO_SECRET_KEY are required for STORAGE_MODE=minio"
                )
            return MinioFileStorage(
                settings.minio_endpoint,
                settings.minio_access_key,
                settings.minio_secret_key,
                settings.minio_bucket,
            )
        if settings.storage_mode.lower() == "local":
            return LocalFileStorage(settings.storage_root)
        raise RuntimeError("STORAGE_MODE must be minio or local")

    @staticmethod
    def _build_graph_store(settings: Settings) -> tuple[Any, Neo4jGraphStore | None]:
        if settings.graph_mode.lower() == "memory":
            return MemoryGraphStore(), None
        if settings.graph_mode.lower() != "neo4j":
            raise RuntimeError("GRAPH_MODE must be memory or neo4j")
        if not settings.neo4j_uri or not settings.neo4j_password:
            raise RuntimeError(
                "NEO4J_URI and NEO4J_PASSWORD are required for GRAPH_MODE=neo4j"
            )
        store = Neo4jGraphStore(
            settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password
        )
        return store, store

    @staticmethod
    async def _build_retriever(
        settings: Settings, embedding: EmbeddingProvider, cache: CacheService
    ) -> tuple[Any, Any, MilvusKnowledgeStore | None]:
        mode = settings.retriever_mode.lower()
        if mode == "milvus":
            if not settings.database_url:
                raise RuntimeError(
                    "DATABASE_URL is required when RETRIEVER_MODE=milvus"
                )
            store = MilvusKnowledgeStore(
                settings.database_url,
                settings.milvus_uri,
                embedding,
                milvus_token=settings.milvus_token,
                milvus_db_name=settings.milvus_db_name,
                collection_name=settings.milvus_collection_name,
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
            )
            await store.start()
            return (
                CachedRetriever(
                    store, cache, ttl_seconds=settings.cache_retrieval_ttl_seconds
                ),
                store,
                store,
            )
        if mode == "memory":
            store = InMemoryKnowledgeStore(embedding)
            return (
                CachedRetriever(
                    store, cache, ttl_seconds=settings.cache_retrieval_ttl_seconds
                ),
                store,
                None,
            )
        raise RuntimeError("RETRIEVER_MODE must be milvus or memory")

    @staticmethod
    def _build_web_search(
        settings: Settings, http_client: httpx.AsyncClient | None
    ) -> WebSearchProvider:
        if not settings.enable_web_search:
            return DisabledWebSearch()
        provider = settings.web_search_provider.lower()
        if provider not in {"brave", "duckduckgo", "multi", "hybrid"}:
            raise RuntimeError(
                "WEB_SEARCH_PROVIDER must be brave, duckduckgo, multi, or hybrid"
            )
        # The system-level key is optional. Project runs can inject a personal or
        # creator-owned key through RuntimeWebSearchConfig at execution time.
        if provider == "brave" and not settings.web_search_api_key:
            return DisabledWebSearch()
        client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds)
        )
        if provider in {"multi", "hybrid"}:
            if settings.web_search_api_key:
                general: WebSearchProvider = BraveWebSearch(
                    client=client,
                    api_key=settings.web_search_api_key,
                    base_url=settings.web_search_base_url,
                    search_language=settings.web_search_language,
                )
            else:
                general = DuckDuckGoWebSearch(
                    client=client,
                    base_url=DEFAULT_DUCKDUCKGO_BASE_URL,
                    search_language=settings.web_search_language,
                )
            return MultiSourceWebSearch(
                client=client,
                general=general,
                sources=settings.web_search_sources,
                timeout_seconds=settings.request_timeout_seconds,
            )
        if provider == "duckduckgo":
            return DuckDuckGoWebSearch(
                client=client,
                base_url=settings.web_search_base_url or DEFAULT_DUCKDUCKGO_BASE_URL,
                search_language=settings.web_search_language,
            )
        return BraveWebSearch(
            client=client,
            api_key=settings.web_search_api_key,
            base_url=settings.web_search_base_url,
            search_language=settings.web_search_language,
        )

    async def close(self) -> None:
        await self.runtime.close()
        if self.milvus_store:
            await self.milvus_store.close()
        if self.neo4j_store:
            await self.neo4j_store.close()
        if self.mcp_bridge:
            await self.mcp_bridge.close()
        if self.http_client:
            await self.http_client.aclose()
        await self.repository.close()
        await self.cache.close()

    def reload_custom_tools(self) -> CustomToolLoadReport:
        self.runtime.tools.remove_source("custom")
        self.custom_tools_report = load_custom_tools(
            self.runtime.tools,
            self.custom_tools_dir,
            enabled=self.custom_tools_enabled,
            strict=self.custom_tools_strict,
            modules=self.custom_tools_modules,
        )
        return self.custom_tools_report
