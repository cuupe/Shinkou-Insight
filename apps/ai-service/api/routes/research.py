from __future__ import annotations

from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.dependencies import verify_internal_api_key
from core.events import EventBus
from core.repository import InMemoryRunRepository
from models.schemas import ExecuteRunRequest, PlanUpdateRequest, RunAccepted

router = APIRouter(tags=["research"])


@router.post(
    "/internal/research/runs/{run_id}/execute",
    response_model=RunAccepted,
    status_code=202,
    dependencies=[Depends(verify_internal_api_key)],
)
async def execute_run(
    run_id: str,
    request: ExecuteRunRequest,
    http_request: Request,
) -> RunAccepted:
    if str(request.run_id) != str(run_id):
        raise HTTPException(400, "run_id in path and body must match")
    existing = http_request.app.state.repository.get(request.run_id)
    run = await http_request.app.state.runtime.accept(request)
    queue = getattr(http_request.app.state, "task_queue", None)
    if queue is not None and not (existing and run.queue_task_id):
        task_id = await queue.enqueue(request)
        await http_request.app.state.repository.update(run.run_id, queue_task_id=task_id)
        await http_request.app.state.events.publish(run.run_id, "run.queued", {"status": "PENDING", "taskId": task_id})
    else:
        # Keeps direct unit-test app instances compatible with the production
        # queue while still avoiding a blocking HTTP request.
        import asyncio
        asyncio.create_task(http_request.app.state.runtime.execute(request))
    return RunAccepted(
        run_id=run.run_id,
        status=run.status,
        events_url=f"/internal/research/runs/{run.run_id}/events",
    )


@router.post("/internal/research/runs/{run_id}/cancel", dependencies=[Depends(verify_internal_api_key)])
async def cancel_run(run_id: str, http_request: Request) -> dict[str, str]:
    if not await http_request.app.state.runtime.cancel(run_id):
        raise HTTPException(404, "research run not found")
    return {"runId": run_id, "status": "CANCELLING"}


@router.get("/internal/research/runs/{run_id}", dependencies=[Depends(verify_internal_api_key)])
async def get_run(run_id: str, http_request: Request) -> dict[str, Any]:
    run = http_request.app.state.repository.get(run_id)
    if not run:
        raise HTTPException(404, "research run not found")
    return {
        "runId": run.run_id,
        "status": run.status,
        "progress": run.progress,
        "currentNode": run.current_node,
        "currentStep": run.current_step,
        "errorMessage": run.error_message,
        "report": run.report,
        "evidence": [item.model_dump() for item in run.evidence],
        "promptSnapshot": run.prompt_snapshot,
        "toolCalls": http_request.app.state.runtime.tools.history(run.run_id),
        "plan": run.plan,
        "planVersion": run.plan_version,
        "planHistory": run.plan_history,
        "paused": run.paused,
        "reviewResult": run.review_result,
        "queueTaskId": run.queue_task_id,
    }


@router.patch("/internal/research/runs/{run_id}/plan", dependencies=[Depends(verify_internal_api_key)])
async def update_plan(run_id: str, request: PlanUpdateRequest, http_request: Request) -> dict[str, Any]:
    try:
        run = await http_request.app.state.repository.update_plan(
            run_id,
            mode=request.mode,
            steps=[item.model_dump() for item in request.steps],
            summary=request.summary,
            expected_version=request.expected_version,
        )
    except KeyError as exc:
        raise HTTPException(404, "research run not found") from exc
    except ValueError as exc:
        if "version conflict" in str(exc):
            raise HTTPException(409, str(exc)) from exc
        raise HTTPException(422, str(exc)) from exc
    await http_request.app.state.events.publish(
        run_id,
        "plan.updated",
        {"mode": request.mode, "plan": run.plan, "planVersion": run.plan_version, "paused": run.paused},
    )
    return {"runId": run.run_id, "status": run.status, "plan": run.plan, "planVersion": run.plan_version, "paused": run.paused}


async def _event_stream(http_request: Request, run_id: str, after_id: int) -> AsyncIterator[str]:
    event_bus: EventBus = http_request.app.state.events
    repository: InMemoryRunRepository = http_request.app.state.repository
    run = repository.get(run_id)
    if run is None:
        return
    terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED"}
    if run.status in terminal_statuses:
        for event in event_bus.history(run_id, after_id):
            yield event.as_sse()
        return
    async for event in event_bus.subscribe(run_id, after_id):
        if await http_request.is_disconnected():
            return
        yield event.as_sse()
        if event.event_type in {"run.completed", "run.failed", "run.cancelled"}:
            return


@router.get("/internal/research/runs/{run_id}/events", dependencies=[Depends(verify_internal_api_key)])
async def run_events(
    run_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        after_id = int(last_event_id or 0)
    except ValueError:
        after_id = 0
    return StreamingResponse(
        _event_stream(request, run_id, after_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
