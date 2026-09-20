from datetime import date

import pytest

from agents.analyst import EvidenceAnalystAgent
from agents.contracts import AgentContext, AgentMessage
from agents.model_router import AgentModelRouter
from agents.web_researcher import WebResearcherAgent
from core.events import EventBus
from evaluation.agent_eval import (
    evaluate_agent_run,
    evaluate_complexity,
    evaluate_resource_quality,
)
from models.llm import MockModelGateway
from models.schemas import Evidence


def web_evidence(index: str = "W1", content: str = "PostgreSQL production database details") -> Evidence:
    return Evidence(
        id=index,
        chunk_id=index,
        source_name="official database documentation",
        content=content,
        source_type="web",
        url="https://example.org/database",
        content_kind="fulltext",
        published_at=date.today().isoformat(),
    )


def context(events: EventBus) -> AgentContext:
    return AgentContext(
        run_id="eval-run",
        workspace_id=1,
        project_id=1,
        user_id=1,
        model_router=AgentModelRouter(MockModelGateway()),
        web_search=None,
        tools=None,
        repository=None,
        events=events,
        max_evidence=12,
    )


@pytest.mark.asyncio
async def test_evidence_analyst_does_not_stop_on_irrelevant_hits():
    events = EventBus()
    result = await EvidenceAnalystAgent().handle(
        AgentMessage(
            message_id="m1",
            run_id="eval-run",
            sender="coordinator",
            recipient="evidence_analyst",
            intent="evidence.evaluate",
            payload={
                "goal": "What database does production use?",
                "evidence": [
                    Evidence(
                        id="E1",
                        chunk_id="E1",
                        source_name="unrelated marketing page",
                        content="The company launched a new hiring campaign.",
                    ).model_dump()
                ],
                "allow_web_search": True,
                "current_round": 0,
                "max_rounds": 3,
            },
            trace_id="t1",
        ),
        context(events),
    )
    assert result.payload["evaluation"]["next_action"] == "NEED_WEB"
    assert result.payload["evaluation"]["sufficient"] is False


@pytest.mark.asyncio
async def test_web_researcher_uses_focused_query_for_provider():
    class Search:
        def __init__(self):
            self.queries = []

        async def search(self, query, top_k=5):
            self.queries.append(query)
            return []

    search = Search()
    events = EventBus()
    agent_context = context(events)
    agent_context.web_search = search
    await WebResearcherAgent().handle(
        AgentMessage(
            message_id="m2",
            run_id="eval-run",
            sender="coordinator",
            recipient="web_researcher",
            intent="evidence.retrieve.web",
            payload={
                "goal": "梳理一下当前光伏产业的情况，整理一个报告给我，内容要全面",
                "search_query": "梳理一下当前光伏产业的情况，整理一个报告给我，内容要全面",
                "allow_web_search": True,
                "evidence": [],
            },
            trace_id="t2",
        ),
        agent_context,
    )
    assert len(search.queries) == 1
    assert "光伏产业" in search.queries[0]
    assert "整理一个报告" not in search.queries[0]


def test_complex_evaluation_requires_multiple_steps_and_synthesis():
    failed = evaluate_complexity(
        [{"id": "S1", "action": "SEARCH_INTERNAL", "query": "project"}],
        [{"event_type": "agent.started", "payload": {"agent": "planner"}}],
        complex_request=True,
    )
    passed = evaluate_complexity(
        [
            {"id": "S1", "action": "SEARCH_INTERNAL", "query": "project"},
            {"id": "S2", "action": "SEARCH_WEB", "query": "market"},
            {"id": "S3", "action": "SYNTHESIZE", "query": ""},
        ],
        [
            {"event_type": "agent.started", "payload": {"agent": "planner"}},
            {"event_type": "agent.started", "payload": {"agent": "internal_researcher"}},
        ],
        complex_request=True,
    )
    assert failed.passed is False
    assert passed.passed is True


def test_agent_evaluation_covers_tools_sources_answer_and_complexity():
    evidence = [web_evidence()]
    report = {"evidence_ids": ["W1"], "sections": [{"evidence_ids": ["W1"]}]}
    evaluation = evaluate_agent_run(
        goal="PostgreSQL production database",
        events=[
            {"event_type": "tool.started", "payload": {"tool": "search_knowledge"}},
            {"event_type": "agent.started", "payload": {"agent": "planner"}},
            {"event_type": "agent.started", "payload": {"agent": "researcher"}},
        ],
        evidence=evidence,
        answer=report,
        plan=[
            {"id": "S1", "action": "SEARCH_INTERNAL"},
            {"id": "S2", "action": "SEARCH_WEB"},
            {"id": "S3", "action": "SYNTHESIZE"},
        ],
        valid_evidence_ids={"W1"},
        expected_evidence_ids={"W1"},
        expected_tools={"search_knowledge"},
        requires_external=True,
        complex_request=True,
    )
    assert evaluation.passed is True
    assert {item.name for item in evaluation.dimensions} == {
        "tool_usage",
        "resource_quality",
        "answer_grounding",
        "complex_problem_solving",
    }
