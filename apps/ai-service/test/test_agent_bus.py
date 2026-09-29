import asyncio

from agents.bus import AgentMessageBus
from agents.contracts import AgentContext, AgentMessage, AgentResult
from agents.model_router import AgentModelRouter
from agents.registry import AgentRegistry
from core.events import EventBus


class EchoAgent:
    name = "echo"
    description = "test agent"
    capabilities = ("echo",)

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, payload={"received": message.payload, "model": context.model_for(self.name)})


def test_agent_registry_and_message_bus_keep_agents_isolated():
    async def scenario() -> None:
        events = EventBus()
        registry = AgentRegistry()
        registry.register(EchoAgent())
        bus = AgentMessageBus(registry)
        context = AgentContext(
            run_id="run-1",
            workspace_id=1,
            project_id=1,
            user_id=1,
            model_router=AgentModelRouter("default-model"),
            web_search=None,
            tools=None,
            repository=None,
            events=events,
            max_evidence=12,
        )

        result = await bus.request(
            run_id="run-1",
            sender="coordinator",
            recipient="echo",
            intent="test.echo",
            payload={"value": "hello"},
            context=context,
        )

        assert result.status == "SUCCEEDED"
        assert result.payload["received"] == {"value": "hello"}
        assert result.payload["model"] == "default-model"
        assert [item["name"] for item in registry.describe()] == ["echo"]
        event_types = [item.event_type for item in events.history("run-1")]
        assert event_types == ["agent.message.sent", "agent.started", "agent.completed"]
        await bus.close()

    asyncio.run(scenario())


def test_assignments_execute_in_parallel_with_three_worker_limit():
    async def scenario():
        gate = asyncio.Event()
        three_started = asyncio.Event()
        active = 0
        peak = 0

        class BlockingAgent(EchoAgent):
            async def handle(self, message, context):
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                if active == 3:
                    three_started.set()
                try:
                    await gate.wait()
                    return AgentResult(agent=self.name, payload={"evidence": []})
                finally:
                    active -= 1

        events = EventBus()
        registry = AgentRegistry()
        registry.register(BlockingAgent())
        bus = AgentMessageBus(registry)
        context = AgentContext(run_id="parallel", workspace_id=1, project_id=1, user_id=1,
                               model_router=AgentModelRouter("test"), web_search=None, tools=None,
                               repository=None, events=events, max_evidence=12)
        requests = [asyncio.create_task(bus.request(run_id="parallel", sender="primary", recipient="echo",
                    intent="research", payload={"_task_title": f"任务 {i}", "_task_objective": f"问题 {i}"}, context=context)) for i in range(4)]
        try:
            await asyncio.wait_for(three_started.wait(), 2)
            assert not any(request.done() for request in requests)
            assert len([event for event in events.history("parallel") if event.event_type == "agent.started"]) == 3
            gate.set()
            await asyncio.wait_for(asyncio.gather(*requests), 2)
            assert peak == 3
            finished = [event.payload["task"] for event in events.history("parallel") if event.event_type == "agent.completed"]
            assert len({task["id"] for task in finished}) == 4
            assert all(task["parentId"] == "parallel:primary" and task["durationMs"] >= 0 for task in finished)
            assert {task["objective"] for task in finished} == {f"问题 {i}" for i in range(4)}
            assert all(task["summary"] == "未找到可引用证据" for task in finished)
        finally:
            gate.set()
            await bus.close()
    asyncio.run(scenario())


def test_failed_result_is_not_reported_as_completed():
    async def scenario():
        class FailedAgent(EchoAgent):
            async def handle(self, message, context):
                return AgentResult(agent=self.name, status="FAILED", error="retrieval unavailable")
        events = EventBus()
        registry = AgentRegistry()
        registry.register(FailedAgent())
        bus = AgentMessageBus(registry)
        context = AgentContext(run_id="failed", workspace_id=1, project_id=1, user_id=1,
                               model_router=AgentModelRouter("test"), web_search=None, tools=None,
                               repository=None, events=events, max_evidence=12)
        try:
            result = await bus.request(run_id="failed", sender="primary", recipient="echo", intent="test", payload={}, context=context)
            assert result.status == "FAILED"
            history = events.history("failed")
            assert history[-1].event_type == "agent.failed"
            assert history[-1].payload["task"]["error"] == "retrieval unavailable"
            assert not any(event.event_type == "agent.completed" for event in history)
        finally:
            await bus.close()
    asyncio.run(scenario())


def test_cancellation_stops_active_work_and_does_not_start_queued_work():
    async def scenario():
        cancelled = False
        invoked = 0
        stopped = 0
        ready = asyncio.Event()
        class Repository:
            def is_cancelled(self, run_id):
                return cancelled
        class BlockingAgent(EchoAgent):
            async def handle(self, message, context):
                nonlocal invoked, stopped
                invoked += 1
                if invoked == 3:
                    ready.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    stopped += 1
        events = EventBus()
        registry = AgentRegistry()
        registry.register(BlockingAgent())
        bus = AgentMessageBus(registry)
        context = AgentContext(run_id="cancelled", workspace_id=1, project_id=1, user_id=1,
                               model_router=AgentModelRouter("test"), web_search=None, tools=None,
                               repository=Repository(), events=events, max_evidence=12)
        requests = [asyncio.create_task(bus.request(run_id="cancelled", sender="primary", recipient="echo",
                    intent="test", payload={}, context=context)) for _ in range(4)]
        try:
            await asyncio.wait_for(ready.wait(), 2)
            cancelled = True
            await asyncio.wait_for(asyncio.gather(*requests), 2)
            assert invoked == stopped == 3
            terminal = [event.payload["task"] for event in events.history("cancelled") if event.event_type == "agent.cancelled"]
            assert len(terminal) == 4
        finally:
            cancelled = True
            await bus.close()
    asyncio.run(scenario())
