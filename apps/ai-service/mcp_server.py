from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from config import get_settings
from embeddings.providers import build_embedding_provider
from graph.store import MemoryGraphStore, Neo4jGraphStore
from prompts.security import enforce_scope, sanitize_untrusted_text
from rag.indexer import InMemoryKnowledgeStore

try:
    from mcp.server.fastmcp import Context, FastMCP
except ImportError:  # optional until MCP mode is enabled
    Context = Any  # type: ignore[misc,assignment]
    FastMCP = None  # type: ignore[assignment]


@dataclass(slots=True)
class MCPContext:
    retriever: Any
    graph_store: Any
    api_key: str | None = None
    startup: Any | None = None
    shutdown: Any | None = None

    async def start(self) -> None:
        if self.startup:
            await self.startup()

    async def stop(self) -> None:
        if self.shutdown:
            await self.shutdown()


def create_mcp_server(context: MCPContext):
    """Create the Shinkou MCP server.

    Every tool requires an explicit workspace/project scope. The server is
    intentionally read-only; indexing and research execution stay behind the
    authenticated Java-to-AI API and LangGraph runtime.
    """

    if FastMCP is None:
        exc = ImportError("mcp is not installed")
        raise RuntimeError("mcp is required to run the MCP server") from exc

    @asynccontextmanager
    async def lifespan(_server: Any):
        await context.start()
        try:
            yield {}
        finally:
            await context.stop()

    mcp = FastMCP("shinkou-insight", instructions="Tenant-scoped read-only knowledge and graph tools for Shinkou Insight.", lifespan=lifespan, host=os.getenv("MCP_HOST", "0.0.0.0"), port=int(os.getenv("MCP_PORT", "8001")), json_response=True, stateless_http=True)

    def authorize(ctx: Context) -> None:
        if not context.api_key or ctx.request_context.request is None:
            return
        headers = getattr(ctx.request_context.request, "headers", {})
        supplied = headers.get("x-internal-api-key") or headers.get("authorization", "").removeprefix("Bearer ")
        if not supplied or not secrets.compare_digest(supplied, context.api_key):
            raise PermissionError("Invalid MCP API key")

    @mcp.tool()
    async def search_knowledge(ctx: Context, workspace_id: int, project_id: int, query: str, top_k: int = 8, retrieval_mode: str = "HYBRID") -> dict[str, Any]:
        """Search project knowledge using vector, keyword, or hybrid retrieval."""

        authorize(ctx)
        enforce_scope(workspace_id, project_id)
        if retrieval_mode.upper() not in {"VECTOR", "KEYWORD", "HYBRID"}:
            raise ValueError("retrieval_mode must be VECTOR, KEYWORD, or HYBRID")
        top_k = max(1, min(top_k, 20))
        items = await context.retriever.retrieve(
            workspace_id=workspace_id,
            project_id=project_id,
            question=sanitize_untrusted_text(query, max_chars=2_000),
            top_k=top_k,
            retrieval_mode=retrieval_mode,
        )
        return {"contractVersion": "1.0", "query": query, "items": [item.model_dump(mode="json") for item in items]}

    @mcp.tool()
    async def search_graph(ctx: Context, workspace_id: int, project_id: int, query: str, limit: int = 10) -> dict[str, Any]:
        """Search entities and relationships in the project knowledge graph."""

        authorize(ctx)
        enforce_scope(workspace_id, project_id)
        limit = max(1, min(limit, 50))
        nodes, edges = await context.graph_store.search(
            workspace_id=workspace_id,
            project_id=project_id,
            query=sanitize_untrusted_text(query, max_chars=2_000),
            limit=limit,
        )
        return {
            "contractVersion": "1.0",
            "nodes": [{"key": node.key, "name": node.name, "nodeType": node.node_type, **node.properties} for node in nodes],
            "relationships": [{"source": edge.source, "target": edge.target, "relation": edge.relation, **edge.properties} for edge in edges],
        }

    @mcp.resource("shinkou://capabilities")
    def capabilities() -> str:
        return "read-only knowledge search and tenant-scoped graph search; no write tools"

    return mcp


def build_default_context() -> MCPContext:
    settings = get_settings()
    embedding = build_embedding_provider(mode=settings.embedding_mode, api_key=settings.embedding_api_key, base_url=settings.embedding_base_url, model=settings.embedding_model, dimension=settings.embedding_dimension)
    graph_store: Any = MemoryGraphStore()
    shutdowns: list[Any] = []
    if settings.graph_mode.lower() == "neo4j":
        if not settings.neo4j_uri or not settings.neo4j_password:
            raise RuntimeError("NEO4J_URI and NEO4J_PASSWORD are required for GRAPH_MODE=neo4j")
        graph_store = Neo4jGraphStore(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
        shutdowns.append(graph_store.close)
    if settings.retriever_mode.lower() == "milvus":
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is required when RETRIEVER_MODE=milvus")
        from rag.milvus_store import MilvusKnowledgeStore
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
        shutdowns.insert(0, store.close)

        async def shutdown() -> None:
            for close in shutdowns:
                await close()

        return MCPContext(retriever=store, graph_store=graph_store, api_key=settings.mcp_api_key or settings.internal_api_key, startup=store.start, shutdown=shutdown)
    if settings.retriever_mode.lower() != "memory":
        raise RuntimeError("RETRIEVER_MODE must be milvus or memory")
    return MCPContext(retriever=InMemoryKnowledgeStore(embedding), graph_store=graph_store, api_key=settings.mcp_api_key or settings.internal_api_key, shutdown=(shutdowns[0] if shutdowns else None))


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    server = create_mcp_server(build_default_context())
    if transport not in {"stdio", "streamable-http", "sse"}:
        raise SystemExit("MCP_TRANSPORT must be stdio, streamable-http, or sse")
    server.run(transport=transport)


if __name__ == "__main__":
    main()
