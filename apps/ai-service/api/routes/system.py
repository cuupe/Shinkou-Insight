from __future__ import annotations

from dataclasses import asdict
import logging
import shutil
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from agents.contracts import AgentMessage
from agents.runtime import AgentRuntime
from api.dependencies import http_model_error, verify_internal_api_key
from config import get_settings
from models.llm import ModelGatewayError, build_model_gateway, fetch_model_context_window
from models.schemas import (
    HealthResponse,
    LlmChatRequest,
    LlmChatResponse,
    RuntimeEmbeddingConfig,
    RuntimeModelConfig,
    RuntimeWebSearchConfig,
)
from documents.parser import SUPPORTED_EXTENSIONS
from tools.multi_source_search import MultiSourceWebSearch
from tools.mcp_bridge import MCPToolBridge
from tools.web import DEFAULT_DUCKDUCKGO_BASE_URL, BraveWebSearch, DuckDuckGoWebSearch

router = APIRouter(tags=["system"])
settings = get_settings()
logger = logging.getLogger(__name__)


def _whisper_available() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("faster_whisper") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, mode=settings.llm_mode)


@router.get(
    "/internal/health",
    response_model=HealthResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def internal_health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, mode=settings.llm_mode)


@router.get("/internal/runtime/status", dependencies=[Depends(verify_internal_api_key)])
async def runtime_status(http_request: Request) -> dict[str, Any]:
    container = http_request.app.state.container
    queue = getattr(http_request.app.state, "task_queue", None)
    return {
        "cache": await container.cache.stats(),
        "taskQueue": await queue.stats() if queue else {"backend": "not-started"},
        "durableRuns": bool(getattr(container.repository, "_redis", None)),
    }


@router.post("/internal/cache/invalidate", dependencies=[Depends(verify_internal_api_key)])
async def invalidate_cache(http_request: Request) -> dict[str, Any]:
    body = await http_request.json()
    workspace_id = body.get("workspaceId", body.get("workspace_id"))
    project_id = body.get("projectId", body.get("project_id"))
    if workspace_id is None or project_id is None:
        raise HTTPException(400, "workspaceId and projectId are required")
    version = await http_request.app.state.container.cache.bump_version(
        "retrieval", {"workspaceId": int(workspace_id), "projectId": int(project_id)}
    )
    return {"status": "ok", "scope": {"workspaceId": int(workspace_id), "projectId": int(project_id)}, "version": version}


@router.get("/internal/files/tools", dependencies=[Depends(verify_internal_api_key)])
async def file_tools(http_request: Request) -> dict[str, Any]:
    """Expose local file-analysis readiness without uploading any file."""

    parser = getattr(http_request.app.state.runtime, "file_parser", None)
    return {
        "supportedExtensions": sorted(SUPPORTED_EXTENSIONS),
        "ocr": {
            "enabled": bool(parser and parser.ocr_enabled),
            "tesseract": bool(shutil.which("tesseract")),
            "poppler": bool(shutil.which("pdftoppm")),
            "languages": parser.ocr_languages if parser else None,
        },
        "media": {
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "ffprobe": bool(shutil.which("ffprobe")),
            "whisper": _whisper_available(),
            "model": parser.whisper_model if parser else None,
        },
        "office": {"libreoffice": bool(shutil.which("soffice") or shutil.which("libreoffice"))},
    }


@router.get("/internal/mcp/tools", dependencies=[Depends(verify_internal_api_key)])
async def mcp_tools(http_request: Request) -> dict[str, Any]:
    bridge: MCPToolBridge | None = getattr(http_request.app.state, "mcp_bridge", None)
    if bridge is None:
        return {"enabled": False, "tools": []}
    definitions = await bridge.list_tools()
    return {"enabled": True, "tools": [item.model_dump(by_alias=True) for item in definitions]}


@router.get("/internal/agents", dependencies=[Depends(verify_internal_api_key)])
async def agents(http_request: Request) -> dict[str, Any]:
    agent_runtime: AgentRuntime = http_request.app.state.runtime
    return {
        "architecture": "multi-agent-coordinator",
        "transport": "http-workers" if agent_runtime.coordinator.bus.remote else "in-process-message-bus",
        "workerRole": agent_runtime.agent_worker_role,
        "agents": agent_runtime.agent_registry.describe(),
    }


@router.post("/internal/agents/{agent_name}/messages", dependencies=[Depends(verify_internal_api_key)])
async def agent_message(agent_name: str, http_request: Request) -> dict[str, Any]:
    body = await http_request.json()
    if str(body.get("recipient")) != agent_name:
        raise HTTPException(status_code=400, detail="agent recipient mismatch")
    agent_runtime: AgentRuntime = http_request.app.state.runtime
    if agent_runtime.agent_worker_role and agent_runtime.agent_worker_role != agent_name:
        raise HTTPException(status_code=404, detail="agent worker role is not available")
    message = AgentMessage(
        message_id=str(body["message_id"]),
        run_id=str(body["run_id"]),
        sender=str(body["sender"]),
        recipient=agent_name,
        intent=str(body["intent"]),
        payload=dict(body.get("payload") or {}),
        trace_id=str(body.get("trace_id") or body["run_id"]),
        workspace_id=int(body.get("workspace_id") or 0),
        project_id=int(body.get("project_id") or 0),
        user_id=int(body.get("user_id") or 0),
        attempt=int(body.get("attempt") or 0),
    )
    result = await agent_runtime.handle_agent_message(message)
    return asdict(result)


@router.post(
    "/internal/llm/chat",
    response_model=LlmChatResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def llm_chat(request: LlmChatRequest, http_request: Request) -> LlmChatResponse:
    try:
        result = await http_request.app.state.model_gateway.chat(
            [message.model_dump() for message in request.messages],
            temperature=request.temperature,
        )
    except ModelGatewayError as exc:
        raise http_model_error(exc) from exc
    return LlmChatResponse.model_validate(result.model_dump())


@router.post("/internal/llm/test", dependencies=[Depends(verify_internal_api_key)])
async def test_llm(request: RuntimeModelConfig, http_request: Request) -> dict[str, Any]:
    client = http_request.app.state.container.http_client
    if client is None:
        raise HTTPException(500, "LLM HTTP client is not available")
    gateway = build_model_gateway(
        mode="http",
        client=client,
        base_url=request.base_url,
        api_key=request.api_key,
        model=request.model,
        provider=request.provider,
        timeout_seconds=request.timeout_seconds,
        max_retries=request.retries,
        structured_output_method=request.structured_output_method,
        generation=request.generation,
    )
    try:
        result = await gateway.chat([{"role": "user", "content": "Reply with OK."}])
    except ModelGatewayError as exc:
        logger.warning("LLM connection test failed: %s", exc)
        raise http_model_error(exc) from exc
    return {"status": "ok", "model": result.model, "latencyMs": result.latency_ms}


@router.post("/internal/llm/context", dependencies=[Depends(verify_internal_api_key)])
async def llm_context(request: RuntimeModelConfig, http_request: Request) -> dict[str, Any]:
    client = http_request.app.state.container.http_client
    if client is None:
        raise HTTPException(500, "LLM HTTP client is not available")
    return await fetch_model_context_window(
        client,
        base_url=request.base_url,
        api_key=request.api_key,
        model=request.model,
        timeout_seconds=request.timeout_seconds,
    )


@router.post("/internal/embedding/test", dependencies=[Depends(verify_internal_api_key)])
async def test_embedding(request: RuntimeEmbeddingConfig, http_request: Request) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        embedding = http_request.app.state.container.embedding_factory(request.model_dump())
        vectors = await embedding.embed_documents(["Shinkou embedding connection test"])
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc
    return {
        "status": "ok",
        "model": embedding.model_name,
        "dimension": len(vectors[0]) if vectors else embedding.dimension,
        "latencyMs": int((time.perf_counter() - started) * 1000),
    }


@router.post("/internal/web-search/test", dependencies=[Depends(verify_internal_api_key)])
async def test_web_search(request: RuntimeWebSearchConfig, http_request: Request) -> dict[str, Any]:
    client = http_request.app.state.container.http_client
    if client is None:
        raise HTTPException(500, "Web search HTTP client is not available")
    provider_name = request.provider.lower()
    if provider_name not in {"brave", "duckduckgo", "multi", "hybrid"}:
        raise HTTPException(400, "Supported web search providers are Brave, DuckDuckGo, and multi-source search")
    started = time.perf_counter()
    try:
        if provider_name in {"multi", "hybrid"}:
            general = (
                BraveWebSearch(client=client, api_key=request.api_key, base_url=request.base_url, search_language=request.language)
                if request.api_key
                else DuckDuckGoWebSearch(client=client, base_url=DEFAULT_DUCKDUCKGO_BASE_URL, search_language=request.language)
            )
            provider = MultiSourceWebSearch(client=client, general=general, sources=request.sources or None)
        elif provider_name == "duckduckgo":
            provider = DuckDuckGoWebSearch(client=client, base_url=request.base_url, search_language=request.language)
        else:
            provider = BraveWebSearch(client=client, api_key=request.api_key, base_url=request.base_url, search_language=request.language)
        results = await provider.search("Shinkou Insight connection test", top_k=1)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc
    return {
        "status": "ok",
        "provider": request.provider,
        "resultCount": len(results),
        "latencyMs": int((time.perf_counter() - started) * 1000),
    }
