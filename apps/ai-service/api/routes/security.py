from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from api.dependencies import verify_internal_api_key
from models.llm import build_model_gateway
from models.schemas import RuntimeModelConfig
from security.harness import case_catalog, run_harness

router = APIRouter(tags=["security"])


class HarnessRequest(BaseModel):
    workspace_id: int = Field(gt=0)
    project_id: int = Field(gt=0)
    case_ids: list[str] = Field(default_factory=list, max_length=30)
    include_model_probes: bool = False
    runtime_model: RuntimeModelConfig | None = None


@router.get("/internal/security-harness/cases", dependencies=[Depends(verify_internal_api_key)])
async def cases() -> dict[str, Any]:
    return {"cases": case_catalog()}


@router.post("/internal/security-harness/run", dependencies=[Depends(verify_internal_api_key)])
async def run(request: HarnessRequest, http_request: Request) -> dict[str, Any]:
    model = None
    if request.include_model_probes and request.runtime_model:
        container = http_request.app.state.container
        model = build_model_gateway(
            mode="http",
            client=container.http_client,
            base_url=request.runtime_model.base_url,
            api_key=request.runtime_model.api_key,
            model=request.runtime_model.model,
            provider=request.runtime_model.provider,
            timeout_seconds=request.runtime_model.timeout_seconds,
            max_retries=request.runtime_model.retries,
            structured_output_method=request.runtime_model.structured_output_method,
            generation=request.runtime_model.generation,
        )
    return await run_harness(
        workspace_id=request.workspace_id,
        project_id=request.project_id,
        case_ids=request.case_ids,
        include_model_probes=request.include_model_probes,
        model=model,
    )
