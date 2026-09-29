import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import httpx
from api.routes.research import get_run
from agents.coordinator import AgentCoordinator
from agents.contracts import AgentContext, AgentResult
from agents.model_router import AgentModelRouter
from core.events import EventBus
from core.repository import InMemoryRunRepository, RunRecord
from models.schemas import ExecuteRunRequest
from test_agent_runtime import make_runtime
from models.llm import HttpModelGateway


@pytest.mark.asyncio
async def test_detail_exposes_observable_tasks_and_stable_timing_without_reasoning():
    events = EventBus()
    repository = InMemoryRunRepository(events)
    await repository.create(RunRecord("1", 1, 1, 1, "试点", {}))
    await events.publish("1", "run.started", {})
    await events.publish("1", "thinking.delta", {"delta": "private reasoning"})
    await events.publish("1", "agent.started", {"task": {"id": "task-1", "title": "目标拆解", "status": "running"}})
    await events.publish("1", "run.failed", {"durationMs": 65000, "message": "模型超时"})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        repository=repository, events=events,
        runtime=SimpleNamespace(tools=SimpleNamespace(history=lambda _: [])))))
    detail = await get_run("1", request)
    assert detail["startedAt"] and detail["finishedAt"]
    assert detail["durationSeconds"] == 65
    assert detail["events"][1]["task"]["title"] == "目标拆解"
    assert "private reasoning" not in str(detail)
    assert detail["tokenCount"] is None


@pytest.mark.asyncio
async def test_failed_model_result_records_the_failed_step():
    events = EventBus()
    repository = InMemoryRunRepository(events)
    await repository.create(RunRecord("1", 1, 1, 1, "试点", {}))
    coordinator = AgentCoordinator(repository=repository, events=events)
    coordinator.bus.request = AsyncMock(return_value=AgentResult(agent="planner", status="FAILED", error="模型连续 60 秒没有数据"))
    context = AgentContext(run_id="1", workspace_id=1, project_id=1, user_id=1,
                           model_router=AgentModelRouter(SimpleNamespace(timeout_seconds=10, max_retries=1)),
                           web_search=None, tools=None, repository=repository, events=events, max_evidence=12)
    with pytest.raises(RuntimeError, match="60 秒没有数据"):
        await coordinator._dispatch(context, {}, "planner", "plan.create", {"goal": "试点"}, "拆解目标")
    assert events.history("1")[-1].event_type == "node.failed"
    assert events.history("1")[-1].payload["node"] == "PLAN"


@pytest.mark.asyncio
async def test_completion_keeps_versioned_plan_and_cancel_cannot_reopen_it():
    runtime, repository = make_runtime()
    try:
        await runtime.execute(ExecuteRunRequest(run_id="plan-shape", workspace_id=1, project_id=1,
                                                goal="What database does production use?"))
        run = repository.get("plan-shape")
        assert run.status == "COMPLETED", run.error_message
        assert isinstance(run.plan, dict) and run.plan["steps"]
        assert run.report["executive_summary"]
        assert await runtime.cancel("plan-shape")
        assert run.status == "COMPLETED"
        await repository.update("plan-shape", status="FAILED", error_message="LLM request timed out")
        assert await runtime.cancel("plan-shape")
        assert run.status == "FAILED"
        assert run.error_message == "LLM request timed out"
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_runtime_model_timeout_overrides_the_shared_clients_default():
    seen = []
    def handle(request):
        seen.append(request.extensions["timeout"]["read"])
        if b'"stream":true' in request.content:
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n', headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle), timeout=1) as client:
        model = HttpModelGateway(client=client, base_url="https://model.test/v1", api_key="test", model="test", timeout_seconds=120)
        await model.chat([{"role": "user", "content": "test"}])
        _ = [chunk async for chunk in model.stream([{"role": "user", "content": "test"}])]
    assert seen == [120, 120]


@pytest.mark.asyncio
async def test_internal_callbacks_do_not_reuse_the_model_transport():
    runtime, _ = make_runtime()
    external = AsyncMock()
    runtime.callback_client = external
    requests = []
    runtime._internal_callback_client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: (requests.append(request), httpx.Response(200))[1]), trust_env=False)
    try:
        await runtime._callback(ExecuteRunRequest(run_id="callback", workspace_id=1, project_id=1,
                                goal="test", callback={"eventEndpoint": "http://localhost/internal/callback"}), {"status": "COMPLETED"})
        assert len(requests) == 1
        external.post.assert_not_called()
    finally:
        await runtime.close()
