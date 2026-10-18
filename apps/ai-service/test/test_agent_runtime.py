import asyncio
from datetime import date, datetime

import pytest

from agents.runtime import (
    AgentRuntime,
    _aggregate_usage,
    _compact_chat_context,
    _materialize_multimodal_messages,
    _normalize_model_markdown,
    _select_chat_context,
)

from core.events import EventBus
from core.repository import InMemoryRunRepository
from graph.store import GraphEdge, GraphNode
from models.llm import MockModelGateway, ModelStreamChunk
from models.schemas import (
    ChatMessage,
    Evidence,
    ExecuteRunRequest,
    ModelChatResult,
    ModelGenerationConfig,
    ReflectionResult,
    ResearchConfig,
    TokenUsage,
)
from rag.retriever import InMemoryRetriever
from tools.knowledge import KnowledgeTool
from tools.registry import ToolRegistry, ToolSpec
from tools.web import DisabledWebSearch


@pytest.fixture
def temporal_clock(monkeypatch):
    from core import clock

    now = datetime(2026, 10, 12, 15, 0, tzinfo=clock.resolve_timezone("Asia/Shanghai"))
    monkeypatch.setattr(clock, "current_time", lambda: now)
    monkeypatch.setattr(clock, "timezone_name", lambda: "Asia/Shanghai")
    return now


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


def test_model_markdown_unescapes_provider_artifacts_but_keeps_code():
    value = "\\#标题\\n\\n\\*\\*重点\\*\\*\\n\\n```text\n\\#keep\n```"

    normalized = _normalize_model_markdown(value)

    assert normalized.startswith("# 标题\n\n**重点**")
    assert "```text\n\\#keep\n```" in normalized


def test_aggregate_usage_keeps_the_model_used_by_the_run():
    result = _aggregate_usage(
        [
            ModelChatResult(
                content="draft",
                model="model-a",
                usage=TokenUsage(input_tokens=4, output_tokens=2, total_tokens=6),
            ),
            ModelChatResult(
                content="review",
                model="model-a",
                usage=TokenUsage(input_tokens=3, output_tokens=1, total_tokens=4),
            ),
        ]
    )

    assert result.total_tokens == 10
    assert result.model == "model-a"


def test_context_is_not_discarded_by_keyword_mismatch():
    selected, stats = _select_chat_context(
        [
            {"role": "user", "content": "项目使用 PostgreSQL，连接池上限是 20。"},
            {"role": "assistant", "content": "数据库配置位于服务环境变量中。"},
        ],
        "乎古哀是什么时代的人？",
    )

    assert len(selected) == 2
    assert stats == {
        "providedContextMessages": 2,
        "selectedContextMessages": 2,
        "filteredMessages": 0,
    }


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
    assert messages[0]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
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
        content = (
            "初稿：缺少依据"
            if self.chat_calls == 1
            else "修正版：已补充依据并保留不确定性"
        )
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
        yield ModelStreamChunk(
            delta="第二段",
            usage=TokenUsage(input_tokens=3, output_tokens=4, total_tokens=7),
        )


class StreamingWithoutUsageGateway(MockModelGateway):
    async def stream(self, messages, *, temperature=None):
        yield ModelStreamChunk(delta="没有 usage 的回答")


def make_runtime(model=None, web_search=None, graph_store=None):
    events = EventBus()
    repository = InMemoryRunRepository(events)
    retriever = InMemoryRetriever(
        [
            {
                "workspace_id": 1,
                "project_id": 1,
                "chunk_id": 1002,
                "asset_id": 77,
                "asset_name": "architecture.md",
                "content": "Production database uses PostgreSQL with a connection pool.",
                "page_number": 3,
                "source_name": "architecture.md",
            },
        ]
    )
    knowledge = KnowledgeTool(retriever)
    tools = ToolRegistry()
    tools.register(
        ToolSpec(name="search_knowledge", permission="READ"), knowledge.search_knowledge
    )
    return (
        AgentRuntime(
            model=model or MockModelGateway(),
            retriever=retriever,
            web_search=web_search or DisabledWebSearch(),
            tools=tools,
            repository=repository,
            events=events,
            graph_store=graph_store,
        ),
        repository,
    )


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


def test_context_compression_uses_model_token_budget():
    messages = [
        {"role": "user", "content": "项目资料说明 PostgreSQL 的连接池配置。" * 30}
    ]
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
async def test_cancelled_run_does_not_continue():
    runtime, repository = make_runtime()
    request = ExecuteRunRequest(
        run_id="run-2",
        workspace_id=1,
        project_id=1,
        goal="PostgreSQL",
        config=ResearchConfig(),
    )
    await runtime.accept(request)
    assert await runtime.cancel("run-2")
    await runtime.execute(request)
    assert repository.get("run-2").status == "CANCELLED"
