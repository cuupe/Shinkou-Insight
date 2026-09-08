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
