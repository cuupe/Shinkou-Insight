import asyncio
from unittest.mock import AsyncMock

import pytest

from embeddings.providers import HashEmbeddingProvider
from models.schemas import Evidence, ExecuteRunRequest, ResearchConfig
from rag.milvus_store import MilvusKnowledgeStore
from rag.reranker import LexicalReranker, retain_relevant_items
from rag.retriever import InMemoryRetriever
from test_agent_runtime import ReflectingModelGateway, make_runtime
from tools.knowledge import KnowledgeTool
from tools.registry import ToolRegistry, ToolSpec

QUESTION = "谁获得了2029年诺贝尔交通工程奖"
PASSAGE = (
    "报道引用了一位名叫‘艾伦·莫里斯博士’的专家，称其获得过2029年诺贝尔交通工程奖。"
    "但现实中的诺贝尔奖并不存在‘交通工程奖’这一奖项。文中相关项目、机构和专家均为虚构信息。"
)
ROW = (17, 12, "test.txt", None, None, PASSAGE, 0.8)


def recall_store(monkeypatch, *, timeout=0.05):
    store = MilvusKnowledgeStore("unused", "unused", HashEmbeddingProvider(dimension=8),
                                 retrieval_timeout_seconds=timeout)
    store.pool, store.client = object(), object()
    monkeypatch.setattr(store, "_search_vectors", lambda *_args: [{"id": 17, "score": 0.9}])
    monkeypatch.setattr(store, "_fetch_rows_by_ids", AsyncMock(return_value=[ROW]))
    monkeypatch.setattr(store, "_fetch_keyword_rows", AsyncMock(return_value=[ROW]))
    return store


async def retrieve(store, **kwargs):
    return await store.retrieve(workspace_id=7, project_id=8, question=QUESTION, top_k=1, **kwargs)


@pytest.mark.asyncio
async def test_slow_embedding_keeps_keyword_evidence_before_outer_tool_deadline(monkeypatch):
    store = recall_store(monkeypatch)
    cancelled = asyncio.Event()

    async def slow_embedding(_question):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(store.embedding, "embed_query", slow_embedding)
    items = await asyncio.wait_for(retrieve(store), timeout=0.5)
    assert cancelled.is_set()
    assert items[0].asset_id == 12
    assert "艾伦·莫里斯" in items[0].content
    assert items[0].vector_score is None
    assert items[0].keyword_score == 0.8


@pytest.mark.asyncio
async def test_failed_vector_keeps_keyword_and_vector_only_still_reports_error(monkeypatch):
    store = recall_store(monkeypatch)
    monkeypatch.setattr(store.embedding, "embed_query", AsyncMock(side_effect=RuntimeError("provider unavailable")))
    assert (await retrieve(store))[0].chunk_id == 17
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await retrieve(store, retrieval_mode="VECTOR")


@pytest.mark.asyncio
async def test_keyword_mode_does_not_depend_on_embedding_dimension(monkeypatch):
    store = recall_store(monkeypatch)
    other_embedding = HashEmbeddingProvider(dimension=16)
    monkeypatch.setattr(other_embedding, "embed_query", AsyncMock(side_effect=AssertionError("must not embed")))
    assert (await retrieve(store, retrieval_mode="KEYWORD", embedding=other_embedding))[0].asset_id == 12


@pytest.mark.asyncio
async def test_slow_keyword_keeps_vector_evidence(monkeypatch):
    store = recall_store(monkeypatch)

    async def slow_keyword(*_args, **_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(store, "_fetch_keyword_rows", slow_keyword)
    items = await asyncio.wait_for(retrieve(store), timeout=0.5)
    assert items[0].vector_score == 0.9
    assert items[0].keyword_score is None


@pytest.mark.asyncio
async def test_healthy_hybrid_retains_both_channel_scores(monkeypatch):
    store = recall_store(monkeypatch)
    items = await retrieve(store)
    assert len(items) == 1
    assert items[0].vector_score == 0.9
    assert items[0].keyword_score == 0.8


@pytest.mark.asyncio
async def test_failed_channel_and_empty_fallback_is_not_a_successful_empty_search(monkeypatch):
    store = recall_store(monkeypatch)
    monkeypatch.setattr(store.embedding, "embed_query", AsyncMock(side_effect=RuntimeError("embedding failed")))
    store._fetch_keyword_rows.return_value = []
    with pytest.raises(RuntimeError, match="embedding failed"):
        await retrieve(store)


@pytest.mark.asyncio
async def test_cancelling_retrieval_cancels_both_channels(monkeypatch):
    store = recall_store(monkeypatch, timeout=10)
    started = [asyncio.Event(), asyncio.Event()]
    stopped = [asyncio.Event(), asyncio.Event()]

    async def blocked(index):
        started[index].set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped[index].set()

    monkeypatch.setattr(store.embedding, "embed_query", lambda *_args: blocked(0))
    monkeypatch.setattr(store, "_fetch_keyword_rows", lambda *_args, **_kwargs: blocked(1))
    task = asyncio.create_task(retrieve(store))
    await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started)), timeout=0.5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(event.is_set() for event in stopped)


@pytest.mark.asyncio
async def test_explicit_filename_keeps_semantic_neighbors_from_other_files_out(monkeypatch):
    store = recall_store(monkeypatch)
    wrong_row = (18, 13, "斗破苍穹.txt", None, None, "萧炎答应为海波东炼制复灵紫丹。", 0.95)
    monkeypatch.setattr(store, "_search_vectors", lambda *_args: [
        {"id": 18, "score": 0.99}, {"id": 17, "score": 0.40},
    ])
    monkeypatch.setattr(store, "_fetch_rows_by_ids", AsyncMock(return_value=[wrong_row, ROW]))
    monkeypatch.setattr(store, "_fetch_keyword_rows", AsyncMock(return_value=[ROW]))
    items = await store.retrieve(
        workspace_id=7,
        project_id=8,
        question="test.txt 的主要内容是什么？",
        top_k=5,
    )

    assert items
    assert [item.asset_name for item in items] == ["test.txt"]


@pytest.mark.asyncio
async def test_in_memory_retriever_treats_an_explicit_filename_as_a_source_filter():
    retriever = InMemoryRetriever([
        {
            "workspace_id": 7, "project_id": 8, "asset_id": 12,
            "asset_name": "test.txt", "chunk_id": "test-1",
            "content": "北辰市零重力地铁项目被明确说明为虚构信息。",
        },
        {
            "workspace_id": 7, "project_id": 8, "asset_id": 13,
            "asset_name": "斗破苍穹.txt", "chunk_id": "novel-1",
            "content": "萧炎答应为海波东炼制复灵紫丹。",
        },
    ])

    items = await retriever.retrieve(
        workspace_id=7,
        project_id=8,
        question="test.txt 的主要内容是什么？",
        top_k=5,
    )

    assert [item.asset_name for item in items] == ["test.txt"]


@pytest.mark.asyncio
async def test_hybrid_retriever_abstains_when_only_weak_vector_neighbors_match(monkeypatch):
    store = recall_store(monkeypatch)
    irrelevant = (18, 13, "斗破苍穹.txt", None, None, "萧炎在中州寻找药材，与海波东同行。", 0.0)
    monkeypatch.setattr(store, "_search_vectors", lambda *_args: [{"id": 18, "score": 0.14}])
    monkeypatch.setattr(store, "_fetch_rows_by_ids", AsyncMock(return_value=[irrelevant]))
    monkeypatch.setattr(store, "_fetch_keyword_rows", AsyncMock(return_value=[]))

    items = await store.retrieve(
        workspace_id=7,
        project_id=8,
        question="世界卫生组织总部在哪个城市？",
        top_k=5,
        use_reranker=True,
    )

    assert items == []


@pytest.mark.asyncio
async def test_hybrid_retriever_keeps_strong_knowledge_match_after_relevance_gate(monkeypatch):
    store = recall_store(monkeypatch)
    relevant = (
        18, 13, "斗破苍穹.txt", None, None,
        "萧炎为了报答海波东的救命之恩，答应给他炼制复灵紫丹。", 0.8,
    )
    monkeypatch.setattr(store, "_search_vectors", lambda *_args: [{"id": 18, "score": 0.9}])
    monkeypatch.setattr(store, "_fetch_rows_by_ids", AsyncMock(return_value=[relevant]))
    monkeypatch.setattr(store, "_fetch_keyword_rows", AsyncMock(return_value=[relevant]))

    items = await store.retrieve(
        workspace_id=7,
        project_id=8,
        question="萧炎为了报答海波东的救命之恩，答应给他炼制什么丹药？",
        top_k=5,
        use_reranker=True,
    )

    assert len(items) == 1
    assert items[0].rerank_score is not None
    assert items[0].rerank_score >= 0.15
    assert "复灵紫丹" in items[0].content


@pytest.mark.asyncio
async def test_hybrid_retriever_drops_english_function_word_match_from_vocabulary(monkeypatch):
    store = recall_store(monkeypatch)
    irrelevant = (
        18, 13, "記憶.xlsx", 1, "单词&词组",
        "If you describe something as exclusive, you mean that it is limited to people "
        "who have a lot of money or who belong to a high social class. An intuitive sense "
        "can help; cite it as an example and search for the source if you cannot find it.",
        0.14,
    )
    monkeypatch.setattr(store, "_search_vectors", lambda *_args: [{"id": 18, "score": 0.9}])
    monkeypatch.setattr(store, "_fetch_rows_by_ids", AsyncMock(return_value=[irrelevant]))
    monkeypatch.setattr(store, "_fetch_keyword_rows", AsyncMock(return_value=[irrelevant]))

    items = await store.retrieve(
        workspace_id=7,
        project_id=8,
        question=(
            "WHO headquarters location official website. Check this project knowledge base first; "
            "if absent, search the official WHO site and cite it. If you cannot find an official "
            "source, say so."
        ),
        top_k=5,
        use_reranker=True,
    )

    assert items == []


@pytest.mark.asyncio
async def test_relevance_filter_keeps_lexically_relevant_english_evidence():
    item = Evidence(
        id="E1",
        chunk_id=19,
        source_name="headquarters.md",
        asset_name="headquarters.md",
        content="The WHO headquarters is located in Geneva, Switzerland.",
        fusion_score=0.01,
    )

    ranked = await LexicalReranker().rerank(
        "Where is the WHO headquarters located?", [item]
    )

    assert len(retain_relevant_items("Where is the WHO headquarters located?", ranked)) == 1
    assert "Geneva" in ranked[0].content


@pytest.mark.asyncio
async def test_in_memory_retriever_abstains_on_unrelated_semantic_fallback():
    retriever = InMemoryRetriever([
        {
            "workspace_id": 7, "project_id": 8, "asset_id": 13,
            "asset_name": "斗破苍穹.txt", "chunk_id": "novel-1",
            "content": "萧炎在中州寻找药材，与海波东同行。",
        },
    ])

    items = await retriever.retrieve(
        workspace_id=7,
        project_id=8,
        question="世界卫生组织总部在哪个城市？",
        top_k=5,
        use_reranker=True,
    )

    assert items == []


@pytest.mark.asyncio
async def test_chat_receives_source_and_fiction_qualification_when_vector_fails(monkeypatch):
    store = recall_store(monkeypatch)
    monkeypatch.setattr(store.embedding, "embed_query", AsyncMock(side_effect=RuntimeError("offline")))
    model = ReflectingModelGateway()
    runtime, repo = make_runtime(model)
    runtime.tools = ToolRegistry()
    runtime.tools.register(ToolSpec(name="search_knowledge", timeout_seconds=0.5), KnowledgeTool(store).search_knowledge)
    try:
        await runtime.execute(ExecuteRunRequest(
            run_id="recall-regression", agent_message_id="recall-answer", workspace_id=7, project_id=8,
            goal=QUESTION, config=ResearchConfig(top_k=1, multi_agent_mode="OFF", reflection_enabled=False),
        ))
        run = repo.get("recall-regression")
        assert run.status == "COMPLETED", run.error_message
        assert model.chat_calls == 1
        prompt = "\n".join(message["content"] for message in model.chat_messages[0])
        assert "艾伦·莫里斯" in prompt
        assert "均为虚构信息" in prompt
        assert "test.txt" in prompt
        added = [event for event in repo.list_events(run.run_id) if event.event_type == "evidence.added"]
        assert len(added[0].payload["items"]) == 1
        assert added[0].payload["items"][0]["asset_id"] == 12
    finally:
        await runtime.close()
