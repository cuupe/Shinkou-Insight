import pytest

from agents.runtime import AgentRuntime
from core.events import EventBus
from core.repository import InMemoryRunRepository
from models.llm import MockModelGateway
from models.schemas import ExecuteRunRequest, ResearchConfig
from rag.retriever import InMemoryRetriever
from tools.knowledge import KnowledgeTool
from tools.registry import ToolRegistry, ToolSpec
from tools.web import DisabledWebSearch


class EmptyRetriever:
    async def retrieve(self, **kwargs):
        return []


def make_runtime():
    events = EventBus()
    repository = InMemoryRunRepository(events)
    retriever = InMemoryRetriever([
        {"workspace_id": 1, "project_id": 1, "chunk_id": 1002, "content": "Production database uses PostgreSQL with a connection pool.", "page_number": 3, "source_name": "architecture.md"},
    ])
    knowledge = KnowledgeTool(retriever)
    tools = ToolRegistry()
    tools.register(ToolSpec(name="search_knowledge", permission="READ"), knowledge.search_knowledge)
    return AgentRuntime(model=MockModelGateway(), retriever=retriever, web_search=DisabledWebSearch(), tools=tools, repository=repository, events=events), repository


@pytest.mark.asyncio
async def test_graph_completes_with_citations():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(run_id="run-1", workspace_id=1, project_id=1, goal="What database does production use?", config=ResearchConfig())
    await runtime.execute(request)
    run = repository.get("run-1")
    assert run is not None
    assert run.status == "COMPLETED"
    assert run.report is not None
    assert run.evidence
    assert any(event.event_type == "run.completed" for event in repository.list_events("run-1"))


@pytest.mark.asyncio
async def test_cancelled_run_does_not_continue():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(run_id="run-2", workspace_id=1, project_id=1, goal="PostgreSQL", config=ResearchConfig())
    await runtime.accept(request)
    assert await runtime.cancel("run-2")
    await runtime.execute(request)
    assert repository.get("run-2").status == "CANCELLED"


@pytest.mark.asyncio
async def test_graph_limits_missing_evidence_research_rounds():
    events = EventBus()
    repository = InMemoryRunRepository(events)
    retriever = EmptyRetriever()
    tools = ToolRegistry()
    tools.register(ToolSpec(name="search_knowledge", permission="READ"), KnowledgeTool(retriever).search_knowledge)
    runtime = AgentRuntime(model=MockModelGateway(), retriever=retriever, web_search=DisabledWebSearch(), tools=tools, repository=repository, events=events)
    request = ExecuteRunRequest(run_id="run-3", workspace_id=1, project_id=1, goal="未知问题", config=ResearchConfig(max_research_rounds=2))
    await runtime.execute(request)
    assert repository.get("run-3").status == "COMPLETED"
    assert any(event.event_type == "node.started" and event.payload.get("node") == "REWRITE_QUERY" for event in repository.list_events("run-3"))
