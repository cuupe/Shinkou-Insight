from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from core import clock
from core.cache import CacheService
from models.llm import _normalize_provider_messages, _to_langchain_messages
from models.schemas import Evidence
from prompts.agent_prompts import planner_prompt, reflection_prompt
from tools.cached_web import CachedWebSearch
from tools.search_quality import (
    freshness_window,
    is_current_status_query,
    rank_web_evidence,
    temporal_search_query,
    unsupported_event_dates,
)
from tools.source_content import hydrate_web_evidence


@pytest.fixture
def fixed_clock(monkeypatch):
    now = datetime(2026, 10, 12, 15, 0, tzinfo=clock.resolve_timezone("Asia/Shanghai"))
    monkeypatch.setattr(clock, "current_time", lambda: now)
    monkeypatch.setattr(clock, "timezone_name", lambda: "Asia/Shanghai")
    return now


def office_source(**overrides):
    return Evidence.model_validate(
        {
            "id": "W1",
            "chunk_id": "w1",
            "source_name": "Current United States President",
            "content": "The current President of the United States is Example Person. The administration serves the public.",
            "url": "https://www.whitehouse.gov/administration/president-example/",
            "source_type": "web",
            "content_kind": "fulltext",
            **overrides,
        }
    )


def test_clock_uses_shanghai_date_across_utc_midnight():
    utc = datetime(2026, 10, 11, 17, 30, tzinfo=timezone.utc)
    assert utc.astimezone(clock.resolve_timezone("Asia/Shanghai")).date() == date(
        2026, 10, 12
    )


def test_all_prompt_paths_refresh_time_without_sources_or_a_prior_system(
    fixed_clock, monkeypatch
):
    for messages in (
        planner_prompt("现任美国总统是谁"),
        reflection_prompt("现任日本首相是谁", "未核验的旧回答", []),
        _normalize_provider_messages([{"role": "user", "content": "今天几号"}]),
    ):
        assert "当前日期：2026-10-12" in messages[0]["content"]
        assert "Asia/Shanghai" in messages[0]["content"]
    old = planner_prompt("今天几号")
    monkeypatch.setattr(clock, "current_time", lambda: fixed_clock + timedelta(days=1))
    refreshed = _normalize_provider_messages(old)
    assert "当前日期：2026-10-13" in refreshed[0]["content"]
    assert "当前日期：2026-10-12" not in refreshed[0]["content"]
    assert refreshed[0]["content"].count('<runtime_time trust="server">') == 1
    assert "当前日期：2026-10-13" in _to_langchain_messages(old)[0].content
    assert "当前日期：2026-10-12" in old[0]["content"]  # Caller state is unchanged.


@pytest.mark.parametrize(
    "goal",
    [
        "现任美国总统和日本首相是谁",
        "美国总统是谁",
        "Who is the prime minister of Japan?",
    ],
)
def test_current_office_queries_cannot_search_a_model_guessed_old_year(
    goal, fixed_clock
):
    query = temporal_search_query("日本首相 美国总统 2025年2月", goal)
    assert "2025" not in query
    assert is_current_status_query(query)
    assert freshness_window(query)[1] == date(2026, 10, 12)


def test_explicit_historical_dates_are_preserved(fixed_clock):
    assert not is_current_status_query("2025年2月现任日本首相是谁")
    assert not is_current_status_query("小说中现任国王是谁")
    query = temporal_search_query("日本首相 2026年", "2025年2月日本首相是谁")
    assert "2025年2月" in query and "2026" not in query
    assert freshness_window(query) == (date(2025, 2, 1), date(2025, 2, 28))
    assert "2025" not in temporal_search_query(
        "人工智能进展 2025", "今天人工智能最新进展"
    )


def test_undated_live_official_profiles_pass_but_archives_and_fresh_reads_of_old_news_do_not(
    fixed_clock,
):
    live = office_source(retrieved_at=fixed_clock.isoformat())
    query = "现任美国总统是谁"
    assert rank_web_evidence(query, [live], 5, require_body=True)
    rejected = [
        office_source(),
        office_source(retrieved_at=(fixed_clock - timedelta(days=2)).isoformat()),
        office_source(retrieved_at=(fixed_clock + timedelta(days=1)).isoformat()),
        office_source(retrieved_at=fixed_clock.isoformat(), published_at="2027-01-01"),
        office_source(
            retrieved_at=fixed_clock.isoformat(),
            url="https://www.whitehouse.gov/archive/president-example/",
        ),
        office_source(
            retrieved_at=fixed_clock.isoformat(),
            url="https://www.whitehouse.gov/news/old-article/",
        ),
        office_source(
            retrieved_at=fixed_clock.isoformat(),
            url="https://www.whitehouse.gov/president.pdf",
        ),
        office_source(
            retrieved_at=fixed_clock.isoformat(),
            source_name="Former United States President",
        ),
        office_source(
            retrieved_at=fixed_clock.isoformat(),
            published_at="2025-01-20",
            url="https://news.example.org/old-story",
        ),
    ]
    assert rank_web_evidence(query, rejected, 5, require_body=True) == []


def test_combined_office_question_retains_sources_that_cover_one_country(fixed_clock):
    japan = office_source(
        id="W2",
        content="日本现任首相由国会指名，现任内閣総理大臣为某某。",
        source_name="日本首相现任介绍",
        url="https://www.kantei.go.jp/current/",
        retrieved_at=fixed_clock.isoformat(),
    )
    rows = [office_source(retrieved_at=fixed_clock.isoformat()), japan]
    assert {
        item.id
        for item in rank_web_evidence(
            "现任美国总统和日本首相是谁", rows, 5, require_body=True
        )
    } == {"W1", "W2"}


def test_event_dates_require_body_support_not_publication_or_fetch_dates(fixed_clock):
    source = office_source(
        published_at="2025-02-01",
        retrieved_at=fixed_clock.isoformat(),
        content="The current president took office on January 20, 2025.",
    )
    assert unsupported_event_dates("于2025年1月20日就职。[W1]", [source]) == []
    assert unsupported_event_dates("于2025年2月就职。[W1]", [source]) == ["2025年2月"]
    assert unsupported_event_dates("Took office in February 2025.[W1]", [source]) == [
        "February 2025"
    ]
    assert unsupported_event_dates("截至2026-10-12，无法核验。", []) == []


def test_a_matching_office_title_from_another_country_does_not_answer_the_question(
    fixed_clock,
):
    source = office_source(
        content="The current Prime Minister of Canada is Example Person.",
        source_name="Canada current Prime Minister",
        published_at="2026-10-12",
        url="https://news.example.org/canada",
    )
    assert rank_web_evidence("现任日本首相是谁", [source], 5, require_body=True) == []


@pytest.mark.asyncio
async def test_hydration_records_when_an_undated_official_profile_was_actually_read(
    fixed_clock,
):
    body = (
        "The current President of the United States is Example Person. This administration serves the public and explains its responsibilities. "
        * 4
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                text=f"<main><h1>Current President</h1><p>{body}</p></main>",
                headers={"content-type": "text/html"},
                request=request,
            )
        )
    ) as client:
        result = await hydrate_web_evidence(
            client, [office_source(content_kind="search_snippet")], "现任美国总统是谁"
        )
    assert len(result) == 1
    assert result[0].retrieved_at == fixed_clock.isoformat()
    assert result[0].published_at is None


@pytest.mark.asyncio
async def test_current_office_cache_is_refetched_when_the_day_changes(
    fixed_clock, monkeypatch
):
    calls = []

    class Provider:
        async def search(self, query, top_k=5):
            calls.append(query)
            return [office_source(retrieved_at=clock.current_time().isoformat())]

    cache = await CacheService.create(backend="memory", namespace="clock-regression")
    try:
        search = CachedWebSearch(Provider(), cache, ttl_seconds=86400)
        assert await search.search("现任美国总统是谁", 1)
        assert await search.search("现任美国总统是谁", 1)
        assert len(calls) == 1
        monkeypatch.setattr(
            clock, "current_time", lambda: fixed_clock + timedelta(days=1)
        )
        assert await search.search("现任美国总统是谁", 1)
        assert len(calls) == 2
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_health_exposes_the_same_clock_used_by_models(fixed_clock):
    from api.routes.system import health

    response = await health()
    assert response.current_date == "2026-10-12"
    assert response.current_time.startswith("2026-10-12T15:00:00+08:00")
    assert response.time_zone == "Asia/Shanghai"
