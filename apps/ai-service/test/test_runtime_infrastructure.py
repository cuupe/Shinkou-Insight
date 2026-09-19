import asyncio

import pytest

from agents.reviewer import apply_review_guards
from core.cache import CacheService
from core.events import EventBus
from core.repository import InMemoryRunRepository, RunRecord
from core.task_queue import ResearchTaskQueue
from models.schemas import ExecuteRunRequest, Evidence, ReviewResult
from rag.cached import CachedRetriever
from tools.cached_web import CachedWebSearch


@pytest.mark.asyncio
async def test_memory_cache_deduplicates_concurrent_factories():
    cache = await CacheService.create(enabled=True, backend="memory", namespace="test-cache", max_entries=10)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"value": 7}

    values = await asyncio.gather(
        *(cache.get_or_set("demo", {"id": 1}, factory, ttl_seconds=30) for _ in range(5))
    )
    assert calls == 1
    assert all(value[0] == {"value": 7} for value in values)
    assert (await cache.stats())["hitRate"] > 0
    await cache.close()


@pytest.mark.asyncio
async def test_memory_task_queue_executes_and_reports_completion():
    queue = await ResearchTaskQueue.create(enabled=True, redis_url=None, stream="test-stream", group="test-group")
    completed = asyncio.Event()

    async def handler(request):
        assert request.run_id == "queue-test"
        completed.set()

    await queue.run_worker(handler)
    await queue.enqueue(ExecuteRunRequest(run_id="queue-test", workspace_id=1, project_id=1, goal="测试任务队列"))
    await asyncio.wait_for(completed.wait(), timeout=2)
    assert (await queue.stats())["completed"] == 1
    await queue.close()


@pytest.mark.asyncio
async def test_memory_task_queue_runs_multiple_tasks_concurrently():
    queue = await ResearchTaskQueue.create(
        enabled=True,
        redis_url=None,
        stream="test-concurrent-stream",
        group="test-concurrent-group",
        concurrency=2,
    )
    entered = 0
    both_entered = asyncio.Event()
    release = asyncio.Event()

    async def handler(_request):
        nonlocal entered
        entered += 1
        if entered == 2:
            both_entered.set()
        await release.wait()

    await queue.run_worker(handler)
    await queue.enqueue(ExecuteRunRequest(run_id="queue-test-1", workspace_id=1, project_id=1, goal="任务一"))
    await queue.enqueue(ExecuteRunRequest(run_id="queue-test-2", workspace_id=1, project_id=1, goal="任务二"))
    await asyncio.wait_for(both_entered.wait(), timeout=2)
    assert (await queue.stats())["processing"] == 2

    release.set()
    for _ in range(200):
        if (await queue.stats())["completed"] == 2:
            break
        await asyncio.sleep(0.01)
    assert (await queue.stats())["completed"] == 2
    await queue.close()


@pytest.mark.asyncio
async def test_plan_updates_use_optimistic_version_and_pause_gate():
    repository = InMemoryRunRepository(EventBus())
    await repository.create(RunRecord(run_id="plan-test", workspace_id=1, project_id=1, user_id=1, goal="计划测试", config={}))
    created = await repository.set_initial_plan("plan-test", {"summary": "初始", "steps": []})
    updated = await repository.update_plan(
        "plan-test",
        mode="APPEND",
        expected_version=created.plan_version,
        steps=[{"id": "S1", "objective": "核对资料", "action": "SEARCH_INTERNAL", "query": "资料"}],
    )
    assert updated.plan_version == 2
    with pytest.raises(ValueError, match="version conflict"):
        await repository.update_plan("plan-test", mode="APPEND", expected_version=1, steps=[])
    await repository.update_plan("plan-test", mode="PAUSE", expected_version=2)
    assert repository.get("plan-test").paused is True
    await repository.update_plan("plan-test", mode="RESUME", expected_version=2)
    assert repository.get("plan-test").paused is False


def test_review_guards_block_unsupported_numbers():
    review = apply_review_guards(
        ReviewResult(approved=True),
        {"title": "结论", "executive_summary": "项目成本为 99 万元", "evidence_ids": ["E1"]},
        [{"id": "E1", "content": "项目成本为 10 万元", "source_type": "internal"}],
    )
    assert review.approved is False
    assert review.risk_level == "BLOCKED"
    assert review.numeric_consistency < 1


@pytest.mark.asyncio
async def test_retrieval_and_web_cache_serialize_pydantic_evidence():
    cache = await CacheService.create(enabled=True, backend="memory", namespace="test-typed-cache", max_entries=10)

    class Retriever:
        calls = 0

        async def retrieve(self, **_kwargs):
            self.calls += 1
            return [Evidence(id="E1", chunk_id="c1", content="缓存证据", source_name="测试资料")]

    class Web:
        calls = 0

        async def search(self, _query, top_k=5):
            self.calls += 1
            return [Evidence(id="W1", chunk_id="w1", content="网页证据", source_name="网页", source_type="web", url="https://example.org/article", content_kind="fulltext")]

    retriever = Retriever()
    web = Web()
    cached_retriever = CachedRetriever(retriever, cache, ttl_seconds=30)
    cached_web = CachedWebSearch(web, cache, ttl_seconds=30)
    assert (await cached_retriever.retrieve(workspace_id=1, project_id=1, question="q", top_k=1))[0].id == "E1"
    assert (await cached_retriever.retrieve(workspace_id=1, project_id=1, question="q", top_k=1))[0].id == "E1"
    assert retriever.calls == 1
    assert (await cached_web.search("网页证据", 1))[0].id == "W1"
    assert (await cached_web.search("网页证据", 1))[0].id == "W1"
    assert web.calls == 1
    await cache.close()
