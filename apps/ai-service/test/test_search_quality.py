from datetime import date, timedelta

import httpx
import pytest

from core.cache import CacheService
from models.schemas import Evidence
from tools.cached_web import CachedWebSearch
from tools.multi_source_search import MultiSourceWebSearch
from tools.search_quality import canonical_url, fallback_queries, freshness_window, rank_web_evidence, topic_score
from tools.source_content import hydrate_web_evidence
from tools.web import WebSearchError, _relevant_candidates


def source(index=1, **overrides):
    return Evidence.model_validate({
        "id": f"W{index}", "chunk_id": f"w:{index}", "source_name": "人工智能研究进展",
        "content": "人工智能模型的评测报告", "source_type": "web",
        "url": f"https://research.example.org/paper/{index}", "content_kind": "search_snippet",
        **overrides,
    })


@pytest.mark.parametrize("query,text", [
    ("当前最新的人工智能相关的进展 2026 官方 release", "2026 最新房地产官方发布报告"),
    ("AI latest news", "Rainfall report"),
    ("ZUN 最新作品", "莫扎特的最新作品整理"),
    ("DeepSeek v4 模型", "DeepSeek v3 模型最新发布"),
    ("量子计算纠错技术", "计算机维修技术及相关信息"),
])
def test_generic_words_substrings_and_wrong_entities_do_not_pass(query, text):
    assert topic_score(query, text) == 0


@pytest.mark.parametrize("query,text", [
    ("当前最新的人工智能相关的进展", "Artificial intelligence model evaluation results"),
    ("ZUN 最新作品", "ZUN 宣布新作品的制作进度"),
    ("机器学习研究", "Machine learning evaluation methods"),
    ("3D Gaussian Splatting rendering", "Gaussian Splatting enables real-time rendering"),
])
def test_topic_terms_and_bilingual_anchors_are_retained(query, text):
    assert topic_score(query, text) > 0


def test_candidate_ranking_ignores_url_keyword_spam_and_reranks():
    candidates = [
        ("住房发布会", "https://example.org/人工智能/2026", "最新官方报告"),
        ("Artificial intelligence evaluation", "https://lab.example.org/report", "人工智能评测数据"),
        ("AI report", "https://lab.example.org/report?utm_source=ad#intro", "人工智能评测数据"),
    ]
    assert _relevant_candidates("人工智能 最新进展 2026 官方", candidates, 5) == [candidates[1]]
    assert canonical_url("https://example.org/a?id=2&utm_campaign=x#toc") == "https://example.org/a?id=2"
    assert canonical_url("https://example.org/a?id=1") != canonical_url("https://example.org/a?id=2")


def test_freshness_has_explicit_historical_ranges_and_no_guessed_dates():
    today = date(2026, 9, 19)
    assert freshness_window("最新人工智能", today=today) == (date(2026, 6, 22), today)
    assert freshness_window("今天人工智能", today=today) == (today, today)
    assert freshness_window("过去7天人工智能", today=today) == (date(2026, 9, 13), today)
    assert freshness_window("2024年的最新进展", today=today) == (date(2024, 1, 1), date(2024, 12, 31))
    assert freshness_window("2026年8月人工智能", today=today) == (date(2026, 8, 1), date(2026, 8, 31))
    assert freshness_window("2026-09-01 至 2026-09-08人工智能", today=today) == (date(2026, 9, 1), date(2026, 9, 8))
    assert freshness_window("人工智能原理", today=today) is None


def test_latest_sources_require_publication_dates_and_historical_queries_still_work():
    rows = [source(i, content_kind="fulltext", published_at=published) for i, published in enumerate([
        None, "2020-01-01", (date.today() + timedelta(days=10)).isoformat(), date.today().isoformat(),
    ])]
    assert [item.id for item in rank_web_evidence("人工智能最新进展", rows, 5, require_body=True)] == ["W3"]
    assert [item.id for item in rank_web_evidence("2020 人工智能进展", rows, 5, require_body=True)] == ["W1"]


def test_reposts_do_not_count_as_independent_sources_and_domains_are_diversified():
    text = "人工智能模型通过公开数据评测，其能力仍需要在具体任务上核验。" * 8
    rows = [source(1, content=text), source(2, content=text, url="https://mirror.example.org/repost"),
            source(3, content="人工智能新的推理评测覆盖工具调用、推理延迟及错误率等多个任务。"),
            source(4, content="人工智能视觉系统测试采用不同环境的图像并记录识别错误。", url="https://other.example.org/results")]
    results = rank_web_evidence("人工智能", rows, 3)
    assert [item.id for item in results] == ["W1", "W4", "W3"]


@pytest.mark.asyncio
async def test_body_cannot_be_validated_by_its_own_title_or_search_snippet():
    body = "本文讨论房地产价格与租赁市场变化。多地房屋成交量仍在调整，各地区供应结构存在明显差异。" * 8
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(
        200, text=f"<article><h1>人工智能最新进展</h1><p>{body}</p></article>", headers={"content-type": "text/html"}, request=req,
    ))) as client:
        assert await hydrate_web_evidence(client, [source(content="房地产市场变化 人工智能")], "人工智能") == []


@pytest.mark.asyncio
async def test_readable_body_is_selected_instead_of_nested_sidebar_and_footer_dates():
    body = "人工智能评测覆盖多语言任务，研究人员披露了数据集规模和评测方法。这些结果仅限于所测试的样本，不代表所有领域。" * 6
    html = f'''<html><head><meta property="article:published_time" content="{date.today().isoformat()}T02:30:00+08:00"></head>
        <article><h1>人工智能评测</h1><p>{body}</p><div class="sidebar"><div class="related"><p>AI 广告购买课程</p></div></div></article>
        <footer><time datetime="2099-01-01">未来版权日期</time></footer></html>'''
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=html, headers={"content-type": "text/html"}, request=req))) as client:
        results = await hydrate_web_evidence(client, [source()], "最新人工智能")
    assert len(results) == 1
    assert "购买课程" not in results[0].content
    assert results[0].published_at == date.today().isoformat()


@pytest.mark.asyncio
async def test_overfetch_replaces_unreadable_top_hits_and_cache_is_versioned():
    calls = []
    async def handler(req):
        index = int(req.url.path.rsplit("/", 1)[-1])
        if index < 6:
            return httpx.Response(403, request=req)
        body = "人工智能评测采用多个公开测试集，研究人员逐项报告准确率、响应时延与测试条件，结果包含已知限制并提供复现实验方法。" * 5
        return httpx.Response(200, text=f"<article><p>{body}</p></article>", headers={"content-type": "text/html"}, request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        class Provider:
            async def search(self, query, top_k=5):
                calls.append(top_k)
                return [source(i, content=f"人工智能评测研究的不同方向{i}") for i in range(1, top_k + 1)]
        provider = Provider()
        provider.client = client
        cache = await CacheService.create(backend="memory", namespace="quality-test")
        try:
            await cache.set("web-search", {"provider": "default", "query": "人工智能", "topK": 2, "contentMode": "source-fulltext-v1"}, [source(99).model_dump()], ttl_seconds=30)
            search = CachedWebSearch(provider, cache, ttl_seconds=30)
            result = await search.search("人工智能", 2)
            assert result and all(item.content_kind == "fulltext" for item in result)
            assert all(int(item.id[1:]) >= 6 for item in result)
            assert await search.search("人工智能", 2) == result
            assert calls == [10, 10]  # One translated retry, none on the cache hit.
        finally:
            await cache.close()


@pytest.mark.asyncio
async def test_all_channel_failures_are_not_reported_as_successful_empty_search():
    class Failed:
        async def search(self, query, top_k=5):
            raise WebSearchError("offline")
    async with httpx.AsyncClient() as client:
        search = MultiSourceWebSearch(client=client, general=Failed(), sources=["general"])
        with pytest.raises(WebSearchError, match="所有搜索渠道"):
            await search.search("人工智能")


@pytest.mark.asyncio
async def test_disabling_cache_does_not_bypass_evidence_validation():
    class Provider:
        async def search(self, query, top_k=5):
            return [source()]
    assert await CachedWebSearch(Provider(), None, ttl_seconds=30).search("人工智能") == []


def test_primary_publisher_outweighs_community_digest_with_equal_relevance():
    rows = [source(1, source_name="人工智能 AI 日报", url="https://juejin.cn/post/1"),
            source(2, url="https://research.example.org/newsroom/announcement")]
    assert [item.id for item in rank_web_evidence("人工智能", rows, 2)] == ["W2", "W1"]


@pytest.mark.asyncio
async def test_bounded_retry_finds_original_but_does_not_accept_query_drift():
    calls = []
    class Provider:
        async def search(self, query, top_k=5):
            calls.append(query)
            if query.startswith("当前"):
                return []
            return [source(1, content="人工智能原始实验评测", content_kind="fulltext", published_at=date.today().isoformat()),
                    source(2, content="住房销售市场变化", source_name="住房报告", content_kind="fulltext", published_at=date.today().isoformat())]
    query = "当前最新的人工智能相关的进展"
    results = await CachedWebSearch(Provider(), None, ttl_seconds=30).search(query)
    assert [item.id for item in results] == ["W1"]
    assert len(calls) == 3
    assert set(calls[1:]) == set(fallback_queries(query))
