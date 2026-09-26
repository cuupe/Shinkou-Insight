import asyncio
from datetime import date

import pytest

from agents.runtime import (
    AgentRuntime,
    _aggregate_usage,
    _augment_web_search_query,
    _chat_retrieval_limit,
    _compact_chat_context,
    _evidence_excerpt,
    _fast_chat_generation,
    _is_fast_chat_request,
    _materialize_multimodal_messages,
    _normalize_model_markdown,
    _select_chat_context,
    _select_chat_strategy,
    _should_enable_multi_agent,
    _should_search_graph,
    _should_search_knowledge,
    _should_search_web,
)
from core.events import EventBus
from core.repository import InMemoryRunRepository
from graph.store import GraphEdge, GraphNode
from models.llm import MockModelGateway, ModelStreamChunk
from models.schemas import ChatMessage, Evidence, ExecuteRunRequest, ModelChatResult, ReflectionResult, ResearchConfig, TokenUsage
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


class RecordingGraphStore:
    def __init__(self):
        self.queries = []

    async def search(self, *, workspace_id, project_id, query, limit):
        self.queries.append((workspace_id, project_id, query, limit))
        nodes = [
            GraphNode(
                key="entity:postgresql",
                name="PostgreSQL",
                node_type="TECHNOLOGY",
                workspace_id=workspace_id,
                project_id=project_id,
                properties={"asset_id": "77", "chunk_id": "1001", "page_number": 2},
            ),
            GraphNode(
                key="entity:redis",
                name="Redis",
                node_type="TECHNOLOGY",
                workspace_id=workspace_id,
                project_id=project_id,
                properties={"asset_id": "77", "chunk_id": "1001", "page_number": 2},
            ),
        ]
        edges = [
            GraphEdge(
                source=nodes[0].key,
                target=nodes[1].key,
                relation="CACHE_FOR",
                workspace_id=workspace_id,
                project_id=project_id,
                properties={"asset_id": "77", "chunk_id": "1001", "page_number": 2},
            ),
        ]
        return nodes[:limit], edges[:limit]


def test_latest_web_search_preserves_topic_without_inventing_years():
    query = _augment_web_search_query("ZUN latest work")
    assert query == "ZUN latest work"
    assert _augment_web_search_query("2024年人工智能进展") == "2024年人工智能进展"


def test_model_markdown_unescapes_provider_artifacts_but_keeps_code():
    value = "\\#标题\\n\\n\\*\\*重点\\*\\*\\n\\n```text\n\\#keep\n```"

    normalized = _normalize_model_markdown(value)

    assert normalized.startswith("# 标题\n\n**重点**")
    assert "```text\n\\#keep\n```" in normalized


def test_aggregate_usage_keeps_the_model_used_by_the_run():
    result = _aggregate_usage([
        ModelChatResult(content="draft", model="model-a", usage=TokenUsage(input_tokens=4, output_tokens=2, total_tokens=6)),
        ModelChatResult(content="review", model="model-a", usage=TokenUsage(input_tokens=3, output_tokens=1, total_tokens=4)),
    ])

    assert result.total_tokens == 10
    assert result.model == "model-a"


def test_unrelated_chat_context_is_filtered_without_a_model_call():
    selected, stats = _select_chat_context(
        [
            {"role": "user", "content": "项目使用 PostgreSQL，连接池上限是 20。"},
            {"role": "assistant", "content": "数据库配置位于服务环境变量中。"},
        ],
        "乎古哀是什么时代的人？",
    )

    assert selected == []
    assert stats == {"providedContextMessages": 2, "selectedContextMessages": 0, "filteredMessages": 2}


def test_related_chat_context_keeps_the_user_assistant_pair():
    selected, stats = _select_chat_context(
        [
            {"role": "user", "content": "项目使用 PostgreSQL，连接池上限是 20。"},
            {"role": "assistant", "content": "数据库配置位于服务环境变量中。"},
        ],
        "这个项目的 PostgreSQL 连接池怎么配置？",
    )

    assert len(selected) == 2
    assert stats["filteredMessages"] == 0


def test_follow_up_chat_context_keeps_recent_messages():
    selected, stats = _select_chat_context(
        [
            {"role": "user", "content": "第一个话题是 PostgreSQL。"},
            {"role": "assistant", "content": "第一个话题已回答。"},
            {"role": "user", "content": "第二个话题是部署。"},
            {"role": "assistant", "content": "第二个话题已回答。"},
        ],
        "继续解释刚才的问题。",
    )

    assert selected == [
        {"role": "user", "content": "第一个话题是 PostgreSQL。"},
        {"role": "assistant", "content": "第一个话题已回答。"},
        {"role": "user", "content": "第二个话题是部署。"},
        {"role": "assistant", "content": "第二个话题已回答。"},
    ]
    assert stats["filteredMessages"] == 0


def test_implicit_answer_format_follow_up_keeps_recent_messages():
    selected, stats = _select_chat_context(
        [
            {"role": "user", "content": "3.548×6.224−5.47+sin(0.3)×6−2"},
            {"role": "assistant", "content": "上一次已经计算出结果，请按步骤说明。"},
        ],
        "\u6309\u7167\u6807\u51c6\u7684\u6570\u5b66\u89e3\u7b54\u65b9\u5f0f\u89e3\u7b54",
    )

    assert selected == [
        {"role": "user", "content": "3.548×6.224−5.47+sin(0.3)×6−2"},
        {"role": "assistant", "content": "上一次已经计算出结果，请按步骤说明。"},
    ]
    assert stats["filteredMessages"] == 0


def test_image_follow_up_keeps_attachment_context_and_short_instruction():
    selected, stats = _select_chat_context(
        [
            {
                "role": "user",
                "content": "请解答图片中的题目",
                "attachments": [
                    {
                        "attachmentId": 57,
                        "fileName": "problem.png",
                        "mimeType": "image/png",
                        "storageKey": "workspaces/1/problem.png",
                    }
                ],
            },
            {"role": "assistant", "content": "我先识别题目内容。"},
        ],
        "给出详细过程",
    )

    assert selected[0]["attachments"][0]["storageKey"] == "workspaces/1/problem.png"
    assert stats["selectedContextMessages"] == 2


class MemoryAttachmentStorage:
    async def get(self, key):
        assert key == "workspaces/1/problem.png"
        return b"image-bytes"


@pytest.mark.asyncio
async def test_historical_image_is_materialized_as_a_provider_image_block():
    messages = await _materialize_multimodal_messages(
        [
            {
                "role": "user",
                "content": "请继续分析这张图",
                "attachments": [
                    {
                        "mimeType": "image/png",
                        "storageKey": "workspaces/1/problem.png",
                    }
                ],
            }
        ],
        MemoryAttachmentStorage(),
    )

    assert messages[0]["content"][0] == {"type": "text", "text": "请继续分析这张图"}
    assert messages[0]["content"][1]["type"] == "image_url"
    assert messages[0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_chat_answer_format_follow_up_includes_previous_problem_in_prompt():
    model = ReflectingModelGateway()
    runtime, _repository = make_runtime(model)
    request = ExecuteRunRequest(
        run_id="chat-context-format-follow-up-1",
        workspace_id=1,
        project_id=1,
        goal="\u6309\u7167\u6807\u51c6\u7684\u6570\u5b66\u89e3\u7b54\u65b9\u5f0f\u89e3\u7b54",
        agent_message_id="message-context-format-follow-up-1",
        context_messages=[
            {"role": "user", "content": "3.548×6.224−5.47+sin(0.3)×6−2"},
            {"role": "assistant", "content": "上一次已经计算出结果，请按步骤说明。"},
        ],
        config=ResearchConfig(reflection_enabled=False),
    )

    await runtime.execute(request)

    assert model.chat_calls == 1
    assert any(
        "3.548×6.224−5.47+sin(0.3)×6−2" in message["content"]
        for message in model.chat_messages[0]
    )


class ReflectingModelGateway:
    model = "reflection-test"

    def __init__(self):
        self.chat_calls = 0
        self.structured_calls = 0
        self.chat_messages = []

    async def chat(self, messages, *, temperature=None):
        self.chat_calls += 1
        self.chat_messages.append(messages)
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


def make_runtime(model=None, web_search=None, graph_store=None):
    events = EventBus()
    repository = InMemoryRunRepository(events)
    retriever = InMemoryRetriever([
        {"workspace_id": 1, "project_id": 1, "chunk_id": 1002, "asset_id": 77, "asset_name": "architecture.md", "content": "Production database uses PostgreSQL with a connection pool.", "page_number": 3, "source_name": "architecture.md"},
    ])
    knowledge = KnowledgeTool(retriever)
    tools = ToolRegistry()
    tools.register(ToolSpec(name="search_knowledge", permission="READ"), knowledge.search_knowledge)
    return AgentRuntime(model=model or MockModelGateway(), retriever=retriever, web_search=web_search or DisabledWebSearch(), tools=tools, repository=repository, events=events, graph_store=graph_store), repository


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
async def test_duplicate_execution_for_same_run_is_ignored():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="duplicate-run",
        workspace_id=1,
        project_id=1,
        goal="What database does production use?",
        config=ResearchConfig(),
    )

    await asyncio.gather(runtime.execute(request), runtime.execute(request))

    events = repository.list_events("duplicate-run")
    assert sum(event.event_type == "run.started" for event in events) == 1
    assert sum(event.event_type == "run.completed" for event in events) == 1


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
    assert evidence_events[0].payload["items"][0]["asset_id"] == 77
    assert not any(event.payload.get("node") == "PLAN" for event in repository.list_events("chat-1"))


@pytest.mark.asyncio
async def test_chat_uses_graph_source_for_relationship_questions():
    graph_store = RecordingGraphStore()
    runtime, repository = make_runtime(graph_store=graph_store)
    request = ExecuteRunRequest(
        run_id="chat-graph-1",
        workspace_id=1,
        project_id=1,
        goal="请分析 PostgreSQL 和 Redis 的依赖关系",
        agent_message_id="message-graph-1",
        config=ResearchConfig(strategy="DIRECT", reflection_enabled=False),
    )

    await runtime.execute(request)

    events = repository.list_events("chat-graph-1")
    assert graph_store.queries
    assert any(event.payload.get("tool") == "search_graph" for event in events if event.event_type == "tool.started")
    evidence_events = [event for event in events if event.event_type == "evidence.added"]
    assert evidence_events
    assert any(item["source_type"] == "graph" for item in evidence_events[0].payload["items"])


@pytest.mark.asyncio
async def test_research_run_seeds_graph_evidence_for_relationship_questions():
    graph_store = RecordingGraphStore()
    runtime, repository = make_runtime(graph_store=graph_store)
    request = ExecuteRunRequest(
        run_id="research-graph-1",
        workspace_id=1,
        project_id=1,
        goal="请研究 PostgreSQL 和 Redis 的依赖关系",
        config=ResearchConfig(max_research_rounds=1),
    )

    await runtime.execute(request)

    run = repository.get("research-graph-1")
    assert run is not None
    assert run.status == "COMPLETED"
    assert graph_store.queries
    assert any(item.source_type == "graph" for item in run.evidence)


def test_context_compression_uses_model_token_budget():
    messages = [{"role": "user", "content": "项目资料说明 PostgreSQL 的连接池配置。" * 30}]
    compacted, metrics = _compact_chat_context(
        messages,
        max_chars=100_000,
        max_tokens=80,
        model_context_window=256,
    )

    assert metrics["compressionTriggered"] == 1
    assert metrics["modelContextWindow"] == 256
    assert metrics["contextTokenBudget"] == 80
    assert metrics["finalTokenEstimate"] <= 80
    assert compacted


def test_context_compression_stays_within_budget_with_older_turns():
    messages = [
        {"role": "user", "content": "历史信息 PostgreSQL Redis 技术栈。" * 40}
        for _ in range(12)
    ]
    compacted, metrics = _compact_chat_context(
        messages,
        max_tokens=120,
        model_context_window=512,
    )

    assert metrics["compressionTriggered"] == 1
    assert metrics["finalTokenEstimate"] <= 120
    assert len(compacted) <= 8


@pytest.mark.asyncio
async def test_chat_simple_project_fact_uses_one_answer_call():
    model = ReflectingModelGateway()
    runtime, repository = make_runtime(model)
    request = ExecuteRunRequest(
        run_id="chat-fast-project-1",
        workspace_id=1,
        project_id=1,
        goal="这个项目使用什么 database？",
        agent_message_id="message-fast-project-1",
        config=ResearchConfig(reflection_enabled=True),
    )

    await runtime.execute(request)

    assert model.chat_calls == 1
    assert model.structured_calls == 0
    evidence_events = [
        event for event in repository.list_events("chat-fast-project-1")
        if event.event_type == "evidence.added"
    ]
    assert evidence_events
    assert len(evidence_events[0].payload["items"]) == 1


@pytest.mark.asyncio
async def test_chat_does_not_forward_unrelated_history_to_the_answer_model():
    model = ReflectingModelGateway()
    runtime, repository = make_runtime(model)
    request = ExecuteRunRequest(
        run_id="chat-context-filter-1",
        workspace_id=1,
        project_id=1,
        goal="乎古哀是什么时代的人？",
        agent_message_id="message-context-filter-1",
        context_messages=[
            ChatMessage(role="user", content="项目使用 PostgreSQL，连接池上限是 20。"),
            ChatMessage(role="assistant", content="数据库配置位于服务环境变量中。"),
        ],
        config=ResearchConfig(reflection_enabled=True),
    )

    await runtime.execute(request)

    assert model.chat_calls == 1
    assert all("PostgreSQL" not in message["content"] for message in model.chat_messages[0])
    completion = next(
        event for event in repository.list_events("chat-context-filter-1") if event.event_type == "run.completed"
    )
    assert completion.payload["contextCompression"]["filteredMessages"] == 2


def test_chat_knowledge_search_is_on_demand():
    assert not _should_search_knowledge("1+1=?")
    assert not _should_search_knowledge("请直接解释什么是递归")
    assert _should_search_knowledge("这个项目使用什么数据库？")
    assert _should_search_knowledge("请搜索项目的部署方式")
    assert _should_search_graph("请分析 PostgreSQL 和 Redis 的依赖关系")


def test_chat_retrieval_limit_honors_requested_value_for_routine_questions():
    assert _chat_retrieval_limit("这个项目使用什么数据库？", requested=8, maximum=12) == 8
    assert _chat_retrieval_limit("请全面比较项目的部署方案", requested=8, maximum=12) == 8
    assert _chat_retrieval_limit("普通项目问题", requested=2, maximum=12) == 2


def test_narrow_evidence_excerpt_keeps_the_query_hit():
    content = "无关内容。" * 200 + "乎古哀(ac.41414-ac.41332)" + "后续无关内容。" * 200
    excerpt = _evidence_excerpt(content, "乎古哀是什么时代的人", 120)
    assert "乎古哀" in excerpt
    assert len(excerpt) <= 122


def test_chat_strategy_router_matches_request_shape():
    direct = ExecuteRunRequest(run_id="strategy-direct", workspace_id=1, project_id=1, goal="1+1=?")
    project = ExecuteRunRequest(run_id="strategy-project", workspace_id=1, project_id=1, goal="这个项目使用什么数据库？")
    broad = ExecuteRunRequest(run_id="strategy-plan", workspace_id=1, project_id=1, goal="请全面比较项目的部署方案并给出迁移建议")
    research = ExecuteRunRequest(run_id="strategy-research", workspace_id=1, project_id=1, goal="整理一下近三年人工智能的发展和先进技术")
    simple_with_web_enabled = ExecuteRunRequest(
        run_id="strategy-simple-web-enabled",
        workspace_id=1,
        project_id=1,
        goal="这题怎么做",
        config=ResearchConfig(allow_web_search=True),
    )
    forced = ExecuteRunRequest(run_id="strategy-forced", workspace_id=1, project_id=1, goal="简单回答", config=ResearchConfig(strategy="REFLECTION"))

    assert _select_chat_strategy(direct) == "DIRECT"
    assert _select_chat_strategy(project) == "DIRECT"
    assert _select_chat_strategy(simple_with_web_enabled) == "DIRECT"
    assert _select_chat_strategy(broad) == "PLAN_AND_SOLVE"
    assert _select_chat_strategy(research) == "PLAN_AND_SOLVE"
    assert _should_search_web(research.goal) is True
    assert _select_chat_strategy(forced) == "REFLECTION"


def test_fast_chat_disables_expensive_reasoning_for_simple_direct_questions():
    request = ExecuteRunRequest(
        run_id="fast-chat",
        workspace_id=1,
        project_id=1,
        goal="What is recursion?",
    )

    assert _is_fast_chat_request(request, request.goal, "DIRECT") is True
    generation = _fast_chat_generation(request, MockModelGateway())
    assert generation.reasoning_effort == "none"
    assert generation.max_tokens == 1_536

    project_lookup = request.model_copy(update={"goal": "What database does this project use?"})
    assert _is_fast_chat_request(project_lookup, project_lookup.goal, "DIRECT") is False


def test_multi_agent_gate_only_opens_for_complex_or_explicit_requests():
    simple = ExecuteRunRequest(run_id="multi-simple", workspace_id=1, project_id=1, goal="请解释什么是递归")
    broad = ExecuteRunRequest(
        run_id="multi-broad",
        workspace_id=1,
        project_id=1,
        goal="请全面比较项目的部署方案并给出迁移建议",
    )
    explicit = ExecuteRunRequest(
        run_id="multi-explicit",
        workspace_id=1,
        project_id=1,
        goal="请让多个子智能体分别调研并汇总结果",
    )
    forced = ExecuteRunRequest(
        run_id="multi-forced",
        workspace_id=1,
        project_id=1,
        goal="简单回答",
        config=ResearchConfig(multi_agent_mode="ON"),
    )

    assert _should_enable_multi_agent(simple) == (False, "当前问题适合单智能体快速处理")
    assert _should_enable_multi_agent(broad)[0] is True
    assert _should_enable_multi_agent(explicit)[0] is True
    assert _should_enable_multi_agent(forced)[0] is True


@pytest.mark.asyncio
async def test_chat_multi_agent_path_coordinates_child_agents():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="chat-multi-agent-1",
        workspace_id=1,
        project_id=1,
        goal="请全面比较项目的部署方案并给出迁移建议",
        agent_message_id="message-multi-agent-1",
        config=ResearchConfig(multi_agent_mode="ON", reflection_enabled=False),
    )

    await runtime.execute(request)

    run = repository.get("chat-multi-agent-1")
    assert run is not None
    assert run.status == "COMPLETED"
    events = repository.list_events("chat-multi-agent-1")
    child_agents = {
        str(event.payload.get("agent"))
        for event in events
        if event.event_type == "agent.started"
    }
    assert {"planner", "internal_researcher", "evidence_analyst", "finding_analyst", "report_writer", "report_reviewer"}.issubset(child_agents)
    coordination = [
        event for event in events
        if event.event_type == "node.completed" and event.payload.get("node") == "MULTI_AGENT"
    ]
    assert coordination and coordination[-1].payload.get("fallback") is not True
    completion = next(event for event in events if event.event_type == "run.completed")
    assert completion.payload["multiAgent"]["enabled"] is True


@pytest.mark.asyncio
async def test_chat_skips_project_search_for_direct_prompt():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="chat-direct-1",
        workspace_id=1,
        project_id=1,
        goal="1+1=?",
        agent_message_id="message-direct-1",
        config=ResearchConfig(allow_web_search=True, reflection_enabled=False),
    )

    await runtime.execute(request)

    events = repository.list_events("chat-direct-1")
    assert not any(
        event.event_type == "tool.started" and event.payload.get("tool") == "search_knowledge"
        for event in events
    )
    assert not any(
        event.event_type in {"node.started", "node.completed"}
        and event.payload.get("node") == "SEARCH"
        for event in events
    )


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
    assert any(
        str(event.payload.get("modelFeedback") or "").strip()
        for event in plan_steps
    )


@pytest.mark.asyncio
async def test_plan_and_solve_honors_enabled_web_search_for_current_questions():
    web_search = RecordingWebSearch()
    runtime, repository = make_runtime(web_search=web_search)
    request = ExecuteRunRequest(
        run_id="chat-plan-web-1",
        workspace_id=1,
        project_id=1,
        goal="梳理当前光伏产业的情况并给出报告",
        agent_message_id="message-plan-web-1",
        config=ResearchConfig(strategy="PLAN_AND_SOLVE", allow_web_search=True, reflection_enabled=False),
    )

    await runtime.execute(request)

    assert web_search.queries == ["当前光伏产业的情况并给出报告"]
    events = repository.list_events(request.run_id)
    assert any(
        event.event_type == "node.started" and event.payload.get("node") == "SEARCH_WEB"
        for event in events
    )
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
    assert web_search.queries[0] == "ZUN 最新作品"
    web_event = next(
        event for event in repository.list_events("chat-web-follow-up-1")
        if event.event_type == "tool.started" and event.payload.get("tool") == "web_search"
    )
    assert web_event.payload["query"] == web_search.queries[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["empty", "snippet", "irrelevant", "stale", "failed"])
async def test_web_summary_degrades_to_a_reviewable_draft_when_evidence_fails(mode):
    class Search:
        async def search(self, query, top_k=5):
            if mode == "empty":
                return []
            if mode == "failed":
                raise RuntimeError("offline")
            return [Evidence(
                id="W1", chunk_id="w1", source_name="人工智能进展",
                content="房地产的房价报告" if mode == "irrelevant" else "人工智能最新评测结果",
                source_type="web", url="https://example.org/report",
                content_kind="search_snippet" if mode == "snippet" else "fulltext",
                published_at="2020-01-01" if mode == "stale" else date.today().isoformat(),
            )]

    model = ReflectingModelGateway()
    runtime, repository = make_runtime(model, web_search=Search())
    request = ExecuteRunRequest(
        run_id=f"grounding-{mode}", workspace_id=1, project_id=1,
        goal="当前最新的人工智能相关的进展", agent_message_id="grounding-message",
        config=ResearchConfig(strategy="DIRECT", allow_web_search=True, multi_agent_enabled=False, reflection_enabled=True),
    )
    await runtime.execute(request)
    run = repository.get(request.run_id)
    assert run.status == "COMPLETED"
    assert "不能给出可核验的总结" not in run.report["answer"]
    assert model.chat_calls == 1
    assert model.structured_calls == 0
    assert any(
        "外部联网检索本轮没有取得" in message["content"]
        for batch in model.chat_messages
        for message in batch
    )
    deltas = [event.payload["delta"] for event in repository.list_events(request.run_id) if event.event_type == "message.delta"]
    assert "".join(deltas) == run.report["answer"]


@pytest.mark.asyncio
async def test_good_web_evidence_still_reaches_summary_with_dates_and_grounding_rules():
    class Search:
        async def search(self, query, top_k=5):
            return [Evidence(id="W1", chunk_id="w1", source_name="人工智能评测",
                             content="人工智能评测结果只覆盖公开的测试集，模型的实际表现仍需针对具体任务验证。",
                             source_type="web", url="https://example.org/report", content_kind="fulltext",
                             published_at=date.today().isoformat())]
    class Model(MockModelGateway):
        async def chat(self, messages, **kwargs):
            self.messages = messages
            return ModelChatResult(content="人工智能评测仅覆盖公开测试集。[W1]")
    model = Model()
    runtime, repository = make_runtime(model, web_search=Search())
    request = ExecuteRunRequest(run_id="grounding-success", workspace_id=1, project_id=1,
                                goal="最新人工智能进展", agent_message_id="good-message",
                                config=ResearchConfig(strategy="DIRECT", allow_web_search=True, multi_agent_enabled=False, reflection_enabled=False))
    await runtime.execute(request)
    assert repository.get(request.run_id).report["answer"].endswith("[W1]")
    context = "\n".join(message["content"] for message in model.messages)
    assert "网页发布日期不等于事件发生日" in context
    assert "页面发布日期：" + date.today().isoformat() in context


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
