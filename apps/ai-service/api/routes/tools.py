from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import verify_internal_api_key
from models.schemas import AsyncToolCallRequest, ToolChainRequest
from tools.registry import ToolCallError, ToolChainStep

router = APIRouter(tags=["tools"])


def _tool_http_error(error: ToolCallError) -> HTTPException:
    message = str(error)
    status = 409 if "limit exceeded" in message.casefold() or "already exists" in message.casefold() else 400
    return HTTPException(status_code=status, detail=message)


def _spec_payload(spec: Any) -> dict[str, Any]:
    return {
        "name": spec.name,
        "version": spec.version,
        "description": spec.description,
        "permission": spec.permission,
        "timeoutSeconds": spec.timeout_seconds,
        "maxConcurrency": spec.max_concurrency,
        "requiresConfirmation": spec.requires_confirmation,
        "inputSchema": spec.input_schema,
    }


@router.get("/internal/tools", dependencies=[Depends(verify_internal_api_key)])
async def list_tools(http_request: Request) -> dict[str, Any]:
    container = http_request.app.state.container
    registry = container.runtime.tools
    return {
        "tools": registry.describe(),
        "async": True,
        "chains": True,
        "custom": container.custom_tools_report.as_dict(),
    }


@router.post("/internal/tools/custom/reload", dependencies=[Depends(verify_internal_api_key)])
async def reload_custom_tools(http_request: Request) -> dict[str, Any]:
    report = http_request.app.state.container.reload_custom_tools()
    http_request.app.state.custom_tools_report = report
    return {"status": "ok", "custom": report.as_dict(), "tools": http_request.app.state.container.runtime.tools.describe()}


@router.post(
    "/internal/tools/calls",
    status_code=202,
    dependencies=[Depends(verify_internal_api_key)],
)
async def submit_tool_call(request: AsyncToolCallRequest, http_request: Request) -> dict[str, Any]:
    registry = http_request.app.state.container.runtime.tools
    try:
        task = await registry.submit_async(
            request.tool,
            run_id=str(request.run_id),
            input_data=request.input_data,
            allow_writes=request.allow_writes,
            confirmed=request.confirmed,
            call_id=request.call_id,
        )
    except ToolCallError as exc:
        raise _tool_http_error(exc) from exc
    task["statusUrl"] = f"/internal/tools/calls/{task['callId']}"
    return task


@router.get("/internal/tools/calls/{call_id}", dependencies=[Depends(verify_internal_api_key)])
async def get_tool_call(call_id: str, http_request: Request) -> dict[str, Any]:
    registry = http_request.app.state.container.runtime.tools
    result = registry.get_task(call_id, include_result=True)
    if result is None:
        raise HTTPException(status_code=404, detail="tool call not found")
    return result


@router.post("/internal/tools/calls/{call_id}/cancel", dependencies=[Depends(verify_internal_api_key)])
async def cancel_tool_call(call_id: str, http_request: Request) -> dict[str, Any]:
    registry = http_request.app.state.container.runtime.tools
    result = await registry.cancel_task(call_id)
    if result is None:
        raise HTTPException(status_code=404, detail="tool call not found")
    return result


@router.post(
    "/internal/tools/chains",
    status_code=202,
    dependencies=[Depends(verify_internal_api_key)],
)
async def submit_tool_chain(request: ToolChainRequest, http_request: Request) -> dict[str, Any]:
    registry = http_request.app.state.container.runtime.tools
    steps = [
        ToolChainStep(
            id=step.id,
            tool=step.tool,
            input_data=step.input_data,
            depends_on=tuple(step.depends_on),
            continue_on_error=step.continue_on_error,
        )
        for step in request.steps
    ]
    try:
        chain = await registry.submit_chain(
            steps,
            run_id=str(request.run_id),
            allow_writes=request.allow_writes,
            confirmed=request.confirmed,
            chain_id=request.chain_id,
            timeout_seconds=request.timeout_seconds,
        )
    except ToolCallError as exc:
        raise _tool_http_error(exc) from exc
    chain["statusUrl"] = f"/internal/tools/chains/{chain['chainId']}"
    return chain


@router.get("/internal/tools/chains/{chain_id}", dependencies=[Depends(verify_internal_api_key)])
async def get_tool_chain(chain_id: str, http_request: Request) -> dict[str, Any]:
    registry = http_request.app.state.container.runtime.tools
    result = registry.get_chain(chain_id, include_results=True)
    if result is None:
        raise HTTPException(status_code=404, detail="tool chain not found")
    return result


@router.post("/internal/tools/chains/{chain_id}/cancel", dependencies=[Depends(verify_internal_api_key)])
async def cancel_tool_chain(chain_id: str, http_request: Request) -> dict[str, Any]:
    registry = http_request.app.state.container.runtime.tools
    result = await registry.cancel_chain(chain_id)
    if result is None:
        raise HTTPException(status_code=404, detail="tool chain not found")
    return result
