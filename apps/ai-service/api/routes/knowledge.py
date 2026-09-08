from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import http_model_error, verify_internal_api_key
from config import get_settings
from models.llm import ModelGatewayError, build_model_gateway
from models.schemas import (
    GraphSearchRequest,
    GraphSearchResponse,
    IndexAssetRequest,
    IndexAssetResponse,
    KnowledgeAnswerDraft,
    KnowledgeAnswerRequest,
    KnowledgeAnswerResponse,
    KnowledgeCitation,
    KnowledgeSearchRequest,
    RetrievalResponse,
    RuntimeModelConfig,
)
from prompts.security import render_evidence_context, sanitize_untrusted_text

router = APIRouter(tags=["knowledge"])
settings = get_settings()


def _embedding_for_request(request: Any, http_request: Request) -> Any:
    config = request.runtime_embedding.model_dump() if request.runtime_embedding else None
    return http_request.app.state.container.embedding_factory(config)


def _model_for_request(config: RuntimeModelConfig | None, http_request: Request) -> Any:
    if config is None:
        return http_request.app.state.model_gateway
    client = http_request.app.state.container.http_client
    if client is None:
        raise HTTPException(500, "LLM HTTP client is not available")
    return build_model_gateway(
        mode="http",
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.retries,
        client=client,
        structured_output_method=config.structured_output_method,
        generation=config.generation,
    )


@router.post(
    "/internal/knowledge/search",
    response_model=RetrievalResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def search_knowledge(request: KnowledgeSearchRequest, http_request: Request) -> RetrievalResponse:
    embedding = _embedding_for_request(request, http_request)
    items = await http_request.app.state.runtime.retriever.retrieve(
        workspace_id=request.workspace_id,
        project_id=request.project_id,
        question=request.query,
        top_k=request.top_k,
        filters=request.filters,
        retrieval_mode=request.retrieval_mode,
        use_reranker=request.use_reranker,
        embedding=embedding,
    )
    return RetrievalResponse(query=request.query, items=items)


@router.post(
    "/internal/knowledge/answer",
    response_model=KnowledgeAnswerResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def answer_knowledge(request: KnowledgeAnswerRequest, http_request: Request) -> KnowledgeAnswerResponse:
    embedding = _embedding_for_request(request, http_request)
    items = await http_request.app.state.runtime.retriever.retrieve(
        workspace_id=request.workspace_id,
        project_id=request.project_id,
        question=request.query,
        top_k=request.top_k,
        filters=request.filters,
        retrieval_mode=request.retrieval_mode,
        use_reranker=request.use_reranker,
        embedding=embedding,
    )
    if not items:
        message = (
            "当前项目资料不足，无法给出有依据的回答。"
            if request.answer_language.lower().startswith("zh")
            else "The project does not contain enough evidence for a reliable answer."
        )
        return KnowledgeAnswerResponse(answer=message, citations=[], insufficient_evidence=True)
    evidence = [item.model_dump() for item in items]
    query = sanitize_untrusted_text(request.query, max_chars=4_000)
    prompt = [
        {
            "role": "system",
            "content": f"Answer only from the supplied evidence. Do not invent facts. Return a concise answer in {request.answer_language}. Cite supporting evidence by exact id in evidence_ids. If support is insufficient, say so.",
        },
        {
            "role": "user",
            "content": f"Question:\n{query}\n\nEvidence:\n{render_evidence_context(evidence, max_chars=18_000)}",
        },
    ]
    try:
        draft, _ = await _model_for_request(request.runtime_model, http_request).structured(
            prompt,
            KnowledgeAnswerDraft,
        )
    except ModelGatewayError as exc:
        raise http_model_error(exc) from exc
    by_id = {item.id: item for item in items}
    cited_items = [by_id[item_id] for item_id in draft.evidence_ids if item_id in by_id]
    if not cited_items:
        message = (
            "当前证据不足以支持可靠回答。"
            if request.answer_language.lower().startswith("zh")
            else "The available evidence is insufficient for a reliable answer."
        )
        return KnowledgeAnswerResponse(answer=message, citations=[], insufficient_evidence=True)
    citations = [
        KnowledgeCitation(
            evidence_id=item.id,
            chunk_id=item.chunk_id,
            asset_name=item.asset_name or item.source_name,
            page_number=item.page_number,
            quote=item.content[:300],
            url=item.url,
        )
        for item in cited_items
    ]
    return KnowledgeAnswerResponse(answer=draft.answer, citations=citations, insufficient_evidence=False)


@router.post(
    "/internal/indexing/assets/{asset_id}",
    response_model=IndexAssetResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def index_asset(asset_id: str, request: IndexAssetRequest, http_request: Request) -> IndexAssetResponse:
    if str(request.asset_id) != str(asset_id):
        raise HTTPException(400, "asset_id in path and body must match")
    try:
        data = (
            request.content.encode("utf-8")
            if request.content is not None
            else await http_request.app.state.storage.get(request.storage_key or "")
        )
        embedding = _embedding_for_request(request, http_request)
        result = await http_request.app.state.indexer.index_bytes(
            data=data,
            file_name=request.file_name,
            mime_type=request.mime_type,
            workspace_id=request.workspace_id,
            project_id=request.project_id,
            asset_id=request.asset_id,
            embedding=embedding,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, "asset content not found") from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return IndexAssetResponse(
        asset_id=request.asset_id,
        parse_status="PARSED",
        index_status="INDEXED",
        chunk_count=result["chunk_count"],
        embedding_model=result["embedding_model"],
        embedding_dimension=result["embedding_dimension"],
        graph_entities=result["graph_entities"],
    )


@router.post(
    "/internal/knowledge/graph/search",
    response_model=GraphSearchResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def search_graph(request: GraphSearchRequest, http_request: Request) -> GraphSearchResponse:
    nodes, edges = await http_request.app.state.graph_store.search(
        workspace_id=request.workspace_id,
        project_id=request.project_id,
        query=request.query,
        limit=request.limit,
    )
    return GraphSearchResponse(
        nodes=[{"key": node.key, "name": node.name, "nodeType": node.node_type, **node.properties} for node in nodes],
        relationships=[
            {"source": edge.source, "target": edge.target, "relation": edge.relation, **edge.properties}
            for edge in edges
        ],
    )
