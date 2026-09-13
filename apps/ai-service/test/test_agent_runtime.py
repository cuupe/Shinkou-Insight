from datetime import date

import pytest

from agents.runtime import AgentRuntime, _aggregate_usage, _augment_web_search_query, _chat_retrieval_limit, _select_chat_strategy, _should_search_knowledge
from core.events import EventBus
from core.repository import InMemoryRunRepository
from models.llm import ModelStreamChunk, MockModelGateway
from models.schemas import ExecuteRunRequest, ModelChatResult, ReflectionResult, ResearchConfig, TokenUsage
from rag.retriever import InMemoryRetriever
from tools.knowledge import KnowledgeTool
from tools.registry import ToolRegistry, ToolSpec
from tools.web import DisabledWebSearch


class EmptyRetriever:
    async def retrieve(self, **kwargs):
        return []


class RecordingWebSearch:
    def __init__(self):
        self.queries = []

    async def search(self, query, top_k=5):
        self.queries.append(query)
        return []


def test_latest_web_search_gets_current_release_terms():
    query = _augment_web_search_query("ZUN latest work")
    assert str(date.today().year) in query
    assert str(date.today().year - 1) in query
    assert "official" in query


def test_aggregate_usage_keeps_the_model_used_by_the_run():
    result = _aggregate_usage([
        ModelChatResult(content="draft", model="model-a", usage=TokenUsage(input_tokens=4, output_tokens=2, total_tokens=6)),
        ModelChatResult(content="review", model="model-a", usage=TokenUsage(input_tokens=3, output_tokens=1, total_tokens=4)),
    ])

    assert result.total_tokens == 10
    assert result.model == "model-a"


class ReflectingModelGateway:
    model = "reflection-test"

    def __init__(self):
        self.chat_calls = 0
        self.structured_calls = 0

    async def chat(self, messages, *, temperature=None):
        self.chat_calls += 1
        content = "初稿：缺少依据" if self.chat_calls == 1 else "修正版：已补充依据并保留不确定性"
        return ModelChatResult(
            content=content,
            model=self.model,
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )

    async def structured(self, messages, schema, *, temperature=None):
        self.structured_calls += 1
        return (
            ReflectionResult(
                approved=False,
                issues=["初稿没有明确说明依据"],
                corrections=["补充证据边界，并标记不确定性"],
                confidence=0.35,
            ),
            ModelChatResult(
                content="{}",
                model=self.model,
                usage=TokenUsage(input_tokens=8, output_tokens=4, total_tokens=12),
            ),
        )


class StreamingModelGateway(MockModelGateway):
    async def stream(self, messages, *, temperature=None):
        yield ModelStreamChunk(delta="第一段")
        yield ModelStreamChunk(delta="第二段", usage=TokenUsage(input_tokens=3, output_tokens=4, total_tokens=7))


class StreamingWithoutUsageGateway(MockModelGateway):
    async def stream(self, messages, *, temperature=None):
        yield ModelStreamChunk(delta="没有 usage 的回答")


def make_runtime(model=None, web_search=None):
    events = EventBus()
    repository = InMemoryRunRepository(events)
    retriever = InMemoryRetriever([
        {"workspace_id": 1, "project_id": 1, "chunk_id": 1002, "content": "Production database uses PostgreSQL with a connection pool.", "page_number": 3, "source_name": "architecture.md"},
    ])
    knowledge = KnowledgeTool(retriever)
    tools = ToolRegistry()
    tools.register(ToolSpec(name="search_knowledge", permission="READ"), knowledge.search_knowledge)
    return AgentRuntime(model=model or MockModelGateway(), retriever=retriever, web_search=web_search or DisabledWebSearch(), tools=tools, repository=repository, events=events), repository


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
async def test_chat_reads_sources_without_starting_research_workflow():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="chat-1",
        workspace_id=1,
        project_id=1,
        goal="What database does production use?",
        agent_message_id="message-1",
        config=ResearchConfig(),
    )
    await runtime.execute(request)
    run = repository.get("chat-1")
    assert run is not None
    assert run.status == "COMPLETED"
    assert run.token_count > 0
    evidence_events = [event for event in repository.list_events("chat-1") if event.event_type == "evidence.added"]
    assert evidence_events
    assert evidence_events[0].payload["items"][0]["source_name"] == "architecture.md"
    assert not any(event.payload.get("node") == "PLAN" for event in repository.list_events("chat-1"))


def test_chat_knowledge_search_is_on_demand():
    assert not _should_search_knowledge("1+1=?")
    assert not _should_search_knowledge("请直接解释什么是递归")
    assert _should_search_knowledge("这个项目使用什么数据库？")
    assert _should_search_knowledge("请搜索项目的部署方式")


def test_chat_retrieval_limit_keeps_routine_questions_focused():
    assert _chat_retrieval_limit("这个项目使用什么数据库？", requested=8, maximum=12) == 3
    assert _chat_retrieval_limit("请全面比较项目的部署方案", requested=8, maximum=12) == 8
    assert _chat_retrieval_limit("普通项目问题", requested=2, maximum=12) == 2


def test_chat_strategy_router_matches_request_shape():
    direct = ExecuteRunRequest(run_id="strategy-direct", workspace_id=1, project_id=1, goal="1+1=?")
    project = ExecuteRunRequest(run_id="strategy-project", workspace_id=1, project_id=1, goal="这个项目使用什么数据库？")
    broad = ExecuteRunRequest(run_id="strategy-plan", workspace_id=1, project_id=1, goal="请全面比较项目的部署方案并给出迁移建议")
    forced = ExecuteRunRequest(run_id="strategy-forced", workspace_id=1, project_id=1, goal="简单回答", config=ResearchConfig(strategy="REFLECTION"))

    assert _select_chat_strategy(direct) == "DIRECT"
    assert _select_chat_strategy(project) == "REACT"
    assert _select_chat_strategy(broad) == "PLAN_AND_SOLVE"
    assert _select_chat_strategy(forced) == "REFLECTION"


@pytest.mark.asyncio
async def test_chat_skips_project_search_for_direct_prompt():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="chat-direct-1",
        workspace_id=1,
        project_id=1,
        goal="1+1=?",
        agent_message_id="message-direct-1",
        config=ResearchConfig(reflection_enabled=False),
    )

    await runtime.execute(request)

    events = repository.list_events("chat-direct-1")
    assert not any(
        event.event_type == "tool.started" and event.payload.get("tool") == "search_knowledge"
        for event in events
    )
    search_completed = next(
        event for event in events
        if event.event_type == "node.completed" and event.payload.get("node") == "SEARCH"
    )
    assert search_completed.payload["skipped"] is True


@pytest.mark.asyncio
async def test_chat_react_path_records_bounded_actions():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="chat-react-1",
        workspace_id=1,
        project_id=1,
        goal="这个项目使用什么数据库？",
        agent_message_id="message-react-1",
        config=ResearchConfig(strategy="REACT", reflection_enabled=False),
    )

    await runtime.execute(request)

    events = repository.list_events("chat-react-1")
    search_steps = [event for event in events if event.event_type == "node.completed" and event.payload.get("node") == "SEARCH"]
    assert search_steps
    assert any(event.payload.get("strategy") == "REACT" for event in search_steps)
    assert any(event.event_type == "evidence.added" for event in events)


@pytest.mark.asyncio
async def test_chat_plan_and_solve_path_executes_plan_steps():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="chat-plan-1",
        workspace_id=1,
        project_id=1,
        goal="请比较项目的部署方案并给出建议",
        agent_message_id="message-plan-1",
        config=ResearchConfig(strategy="PLAN_AND_SOLVE", reflection_enabled=False),
    )

    await runtime.execute(request)

    events = repository.list_events("chat-plan-1")
    plan_steps = [event for event in events if event.event_type == "node.completed" and event.payload.get("node") == "PLAN"]
    assert plan_steps
    assert any(event.payload.get("strategy") == "PLAN_AND_SOLVE" for event in plan_steps)
    assert any(event.event_type == "evidence.added" for event in events)


@pytest.mark.asyncio
async def test_chat_forwards_model_deltas_to_event_bus():
    runtime, repository = make_runtime(StreamingModelGateway())
    request = ExecuteRunRequest(
        run_id="chat-stream-1",
        workspace_id=1,
        project_id=1,
        goal="请分段回答。",
        agent_message_id="message-stream-1",
        config=ResearchConfig(reflection_enabled=False),
    )

    await runtime.execute(request)

    deltas = [
        event.payload["delta"]
        for event in repository.list_events("chat-stream-1")
        if event.event_type == "message.delta"
    ]
    assert deltas == ["第一段", "第二段"]
    assert repository.get("chat-stream-1").report == {"answer": "第一段第二段"}


@pytest.mark.asyncio
async def test_chat_does_not_estimate_missing_provider_usage():
    runtime, repository = make_runtime(StreamingWithoutUsageGateway())
    request = ExecuteRunRequest(
        run_id="chat-no-usage-1",
        workspace_id=1,
        project_id=1,
        goal="直接回答",
        agent_message_id="message-no-usage-1",
        config=ResearchConfig(reflection_enabled=False),
    )

    await runtime.execute(request)

    completion = next(event for event in repository.list_events("chat-no-usage-1") if event.event_type == "run.completed")
    assert completion.payload["usage"]["available"] is False
    assert completion.payload["usage"]["total_tokens"] == 0
    usage_events = [event for event in repository.list_events("chat-no-usage-1") if event.event_type == "usage.updated"]
    assert usage_events and usage_events[-1].payload["usage"]["available"] is False


@pytest.mark.asyncio
async def test_chat_reflection_revises_once_and_aggregates_usage():
    model = ReflectingModelGateway()
    runtime, repository = make_runtime(model)
    request = ExecuteRunRequest(
        run_id="chat-reflection-1",
        workspace_id=1,
        project_id=1,
        goal="请说明生产数据库并给出依据。",
        agent_message_id="message-reflection-1",
        config=ResearchConfig(reflection_enabled=True),
    )

    await runtime.execute(request)

    run = repository.get("chat-reflection-1")
    assert run is not None
    assert run.status == "COMPLETED"
    assert run.report == {"answer": "修正版：已补充依据并保留不确定性"}
    assert model.chat_calls == 2
    assert model.structured_calls == 1
    assert run.token_count == 42
    reflection = [
        event for event in repository.list_events("chat-reflection-1")
        if event.event_type == "node.completed" and event.payload.get("node") == "REFLECTION"
    ]
    assert reflection
    assert reflection[0].payload["revised"] is True
    completion = next(event for event in repository.list_events("chat-reflection-1") if event.event_type == "run.completed")
    assert completion.payload["usage"]["total_tokens"] == 42


@pytest.mark.asyncio
async def test_chat_skips_reflection_for_simple_prompt():
    model = ReflectingModelGateway()
    runtime, repository = make_runtime(model)
    request = ExecuteRunRequest(
        run_id="chat-simple-1",
        workspace_id=1,
        project_id=1,
        goal="1+1=?",
        agent_message_id="message-simple-1",
        config=ResearchConfig(reflection_enabled=True),
    )

    await runtime.execute(request)

    assert model.chat_calls == 1
    assert model.structured_calls == 0
    reflection = [
        event for event in repository.list_events("chat-simple-1")
        if event.event_type == "node.completed" and event.payload.get("node") == "REFLECTION"
    ]
    assert reflection and reflection[0].payload["skipped"] is True
    assert "节省 token" in reflection[0].payload["detail"]


@pytest.mark.asyncio
async def test_chat_reuses_previous_question_for_permission_follow_up():
    web_search = RecordingWebSearch()
    runtime, repository = make_runtime(web_search=web_search)
    request = ExecuteRunRequest(
        run_id="chat-web-follow-up-1",
        workspace_id=1,
        project_id=1,
        goal="我现在允许你联网了，现在告诉我答案",
        agent_message_id="message-web-follow-up-1",
        context_messages=[{"role": "user", "content": "ZUN 最新作品是什么"}],
        config=ResearchConfig(allow_web_search=True, reflection_enabled=False),
    )

    await runtime.execute(request)

    assert len(web_search.queries) == 1
    assert web_search.queries[0].startswith("ZUN 最新作品是什么")
    assert str(date.today().year) in web_search.queries[0]
    web_event = next(
        event for event in repository.list_events("chat-web-follow-up-1")
        if event.event_type == "tool.started" and event.payload.get("tool") == "web_search"
    )
    assert web_event.payload["query"] == web_search.queries[0]


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
