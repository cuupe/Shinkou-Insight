import asyncio
import json

import pytest

from agents.decisions import AgentDecision, AnswerAudit, AnswerRevision
from agents.runtime import AgentRuntime
from core.events import EventBus
from core.repository import InMemoryRunRepository
from models.llm import ModelAuthError, ModelResponseError
from models.schemas import (
    Evidence,
    ExecuteRunRequest,
    ModelChatResult,
    ResearchConfig,
    TokenUsage,
)
from tools.registry import ToolRegistry, ToolSpec
from tools.web import DisabledWebSearch

BASE = (
    "乌索哈罗他中央酒店的第一层收费1270元，第二层收费3111元，第三层及以上收费6730元。"
)
EXTRA = "乌索哈罗他中央酒店第一层一个人附加费用37元，第二层附加费用68元/人，第三层及以上附加费用144元/人。"
QUESTION = "有三个人要去乌索哈罗他中央酒店住宿，一个人在第一层，一个人在第二层，还有一个人在第四层，至少需要多少钱"


def need(key="price", **kwargs):
    return {
        "id": key,
        "description": key,
        "source": "internal",
        "status": "missing",
        **kwargs,
    }


def decision(action="answer", **kwargs):
    return {
        "resolved_goal": QUESTION,
        "summary": "需要核对费用组成",
        "rationale": "按证据缺口选择动作",
        "action": action,
        **kwargs,
    }


def intent(tool="search_knowledge", key="price", **kwargs):
    return dict(tool=tool, purpose="核对基础房费", need_ids=[key], **kwargs)


class ScriptedModel:
    model = "scripted-semantic-model"

    def __init__(self, steps, audits=None):
        self.steps = list(steps)
        self.requests = []
        self.audits = list(
            audits or [dict(approved=True, summary="费用组成与计算结果均有原文支持")]
        )

    async def structured(self, messages, schema, **kwargs):
        self.requests.append((schema, messages))
        if schema is AnswerAudit:
            value = self.audits.pop(0)
            value.setdefault("temporal_checks", [])
        else:
            assert schema in {AgentDecision, AnswerRevision}
            value = self.steps.pop(0)
            if isinstance(value, Exception):
                raise value
            if callable(value):
                value = value(messages)
        return schema.model_validate(value), ModelChatResult(
            content=json.dumps(value, ensure_ascii=False),
            model=self.model,
            usage=TokenUsage(
                input_tokens=10, output_tokens=10, total_tokens=20, available=True
            ),
        )


def runtime_for(model, search=None, **kwargs):
    events = EventBus()
    repository = InMemoryRunRepository(events)
    tools = ToolRegistry()
    if search:
        tools.register(ToolSpec(name="search_knowledge", permission="READ"), search)
    return AgentRuntime(
        model=model,
        retriever=None,
        tools=tools,
        events=events,
        repository=repository,
        web_search=kwargs.pop("web_search", DisabledWebSearch()),
        **kwargs,
    )


def request(run_id="test", **kwargs):
    return ExecuteRunRequest(
        run_id=run_id,
        workspace_id=1,
        project_id=1,
        goal=QUESTION,
        agent_message_id="message",
        config=ResearchConfig(**kwargs),
    )


def records(runtime, run_id="test", kind=None):
    return [
        e
        for e in runtime.repository.list_events(run_id)
        if kind is None or e.event_type == kind
    ]


@pytest.mark.asyncio
async def test_hotel_two_files_fill_base_fee_gap_then_calculate_once():
    queries = []

    async def search(**args):
        queries.append(args)
        text = EXTRA if len(queries) == 1 else BASE
        return [
            Evidence(
                id="E1",
                chunk_id=len(queries),
                asset_id=len(queries),
                content=text,
                source_name="fix_2.txt" if len(queries) == 1 else "fix_1.txt",
            )
        ]

    missing = [need("base"), need("extra"), need("total", source="any")]
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=missing,
                tools=[intent(key="extra", query="乌索哈罗他中央酒店 分层住宿价格")],
            ),
            decision(
                "execute",
                summary="已读到附加费，尚缺基础房费，不能把249元当作总价",
                needs=[need("extra", status="covered", evidence_ids=["E1"])],
                assessments=[
                    dict(
                        evidence_id="E1",
                        relevant=True,
                        reason="给出了附加费而非完整住宿总价",
                    )
                ],
                tools=[
                    intent(
                        key="base",
                        query="乌索哈罗他中央酒店 基础房费 第一层 第二层 第三层及以上",
                    )
                ],
            ),
            decision(
                "execute",
                needs=[need("base", status="covered", evidence_ids=["E2"])],
                assessments=[
                    dict(evidence_id="E2", relevant=True, reason="同一家酒店的基础收费")
                ],
                tools=[
                    intent(
                        "calculator",
                        key="total",
                        expression="1270+3111+6730+37+68+144",
                        supports=[
                            dict(evidence_id="E1", quote=EXTRA),
                            dict(evidence_id="E2", quote=BASE),
                        ],
                    )
                ],
            ),
            decision(
                needs=[need("total", source="any", status="covered")],
                answer="三人至少需要 **11360 元**。基础费用11111元，附加费用249元。[E1][E2]",
                claims=[
                    dict(
                        statement="总价11360元",
                        need_ids=["base", "extra", "total"],
                        supports=[
                            dict(evidence_id="E1", quote=EXTRA),
                            dict(evidence_id="E2", quote=BASE),
                            dict(evidence_id="call:test:tool:3", quote="11360"),
                        ],
                    )
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request(allow_web_search=True))
    run = runtime.repository.get("test")
    assert run.status == "COMPLETED"
    assert "11360" in run.report["answer"]
    assert (
        len(queries) == 2
        and queries[0]["workspace_id"] == 1
        and queries[0]["project_id"] == 1
    )
    starts = records(runtime, kind="tool.started")
    assert [e.payload["tool"] for e in starts] == [
        "search_knowledge",
        "search_knowledge",
        "calculator",
    ]
    assert len(records(runtime, kind="tool.completed")) == 3
    assert len({e.payload["callId"] for e in starts}) == 3
    assert [e.id for e in run.evidence] == ["E1", "E2"]
    assert (
        len(
            {
                e.payload["decision"]["id"]
                for e in records(runtime, kind="decision.updated")
            }
        )
        == 4
    )
    assert len(model.requests) == 5
    assert run.token_count == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "goal",
    [
        "写一个包含最新、现任和总统的虚构故事",
        "改写上面的内容，不要搜网页",
        "今天几号？",
        "你好",
    ],
)
async def test_model_can_answer_without_tools_regardless_of_keywords(goal):
    async def never(**kwargs):
        raise AssertionError("not needed")

    model = ScriptedModel([decision(answer="依据当前请求直接完成", resolved_goal=goal)])
    runtime = runtime_for(model, never)
    await runtime.execute(request().model_copy(update={"goal": goal}))
    assert runtime.repository.get("test").status == "COMPLETED"
    assert not records(runtime, kind="tool.started")
    assert len(model.requests) == 1


@pytest.mark.asyncio
async def test_basic_math_claim_without_a_document_can_answer_in_one_decision():
    model = ScriptedModel(
        [decision(answer="1+1=2", claims=[dict(statement="1 + 1 = 2")])]
    )
    runtime = runtime_for(model)
    await runtime.execute(request().model_copy(update={"goal": "1+1=？"}))
    assert runtime.repository.get("test").report["answer"] == "1+1=2"
    assert len(model.requests) == 1
    assert not records(runtime, kind="node.failed")


@pytest.mark.asyncio
async def test_model_wait_progress_has_elapsed_time_and_a_finite_deadline():
    from agents.decision_engine import DecisionEngine

    class SlowModel(ScriptedModel):
        async def structured(self, *args, **kwargs):
            await asyncio.sleep(0.32)
            return await super().structured(*args, **kwargs)

    runtime = runtime_for(SlowModel([decision(answer="2")]))
    req = request().model_copy(update={"goal": "1+1=？"})
    run = await runtime.accept(req)
    engine = DecisionEngine(runtime, req, run, [])
    engine.model_progress_interval = 0.01
    await engine.run_loop()
    progress = records(runtime, kind="node.updated")
    assert progress and "已等待" in progress[0].payload["detail"]
    assert progress[0].payload["elapsedMs"] > 0
    assert progress[0].payload["timeoutMs"] == 180000
    assert progress[0].payload["callId"] == "test:decision:1"


@pytest.mark.asyncio
async def test_chat_protocol_has_a_bounded_budget_without_mutating_selected_model():
    import httpx
    from models.llm import HttpModelGateway

    seen = []

    def respond(http_request):
        seen.append(http_request.extensions["timeout"]["read"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(decision(answer="2"))}}]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="test",
            timeout_seconds=60,
        )
        runtime = runtime_for(model)
        await runtime.execute(request().model_copy(update={"goal": "1+1=？"}))
        assert seen == [90]
        assert model.timeout_seconds == 60
        assert runtime.repository.get("test").report["answer"] == "2"


@pytest.mark.asyncio
async def test_semantic_audit_has_a_separate_small_reasoning_budget():
    import httpx
    from agents.decision_engine import DecisionEngine
    from models.llm import HttpModelGateway

    async with httpx.AsyncClient() as client:
        original = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
        )
        runtime = runtime_for(original)
        req = request()
        engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
        assert engine.protocol_model().generation.reasoning_effort == "none"
        assert engine.protocol_model(audit=True).generation.reasoning_effort == "low"
        assert engine.protocol_model(audit=True).generation.thinking_budget == 256
        req.config.audit_reasoning_effort = "low"
        assert engine.protocol_model(audit=True).generation.reasoning_effort == "low"
        assert original.generation.reasoning_effort == "high"


@pytest.mark.asyncio
async def test_run_budget_cancels_the_model_and_stops_further_requests():
    from agents.decision_engine import DecisionEngine, AgentExecutionError

    cancelled = asyncio.Event()

    class SlowModel(ScriptedModel):
        async def structured(self, *args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    runtime = runtime_for(SlowModel([]))
    req = request(chat_timeout_seconds=0.02)
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    with pytest.raises(AgentExecutionError) as caught:
        await engine.run_loop()
    assert caught.value.details["code"] == "RUN_TIME_BUDGET"
    assert cancelled.is_set() and engine.model_attempts == 1


@pytest.mark.asyncio
async def test_protocol_recovery_is_observable_and_does_not_claim_complete_usage():
    from agents.decision_engine import DecisionEngine

    model = ScriptedModel([])
    runtime = runtime_for(model)
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])

    async def recovered():
        return AgentDecision.model_validate(decision(answer="2")), ModelChatResult(
            content="{}", response_stats={"recoveryCount": 1}
        )

    await engine.await_model(
        recovered(), model, node="DECISION", call_id="test", title="判断"
    )
    assert not engine.usage_complete


@pytest.mark.asyncio
async def test_auditor_can_return_a_verified_correction_without_two_more_model_calls():
    async def search(**kwargs):
        return [Evidence(id="E1", chunk_id=1, content=BASE, source_name="fix_1.txt")]

    correction = dict(
        summary="依据原文修正金额",
        answer="第一层基础收费1270元。[E1]",
        claims=[
            dict(
                statement="第一层基础收费1270元",
                basis="material",
                need_ids=["price"],
                supports=[dict(evidence_id="E1", quote=BASE)],
            )
        ],
    )
    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="第一层收费")]),
            decision(
                answer="第一层基础收费9999元。[E1]",
                needs=[need(status="covered", evidence_ids=["E1"])],
                claims=[
                    dict(
                        statement="第一层收费1270元",
                        basis="material",
                        need_ids=["price"],
                        supports=[dict(evidence_id="E1", quote=BASE)],
                    )
                ],
            ),
        ],
        audits=[
            dict(
                approved=True,
                summary="已纠正正文金额，修正后全文与原文一致",
                correction=correction,
            )
        ],
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request().model_copy(update={"goal": "第一层基础收费多少？"}))
    assert runtime.repository.get("test").status == "COMPLETED"
    assert "1270元" in runtime.repository.get("test").report["answer"]
    assert [s for s, _ in model.requests] == [AgentDecision, AgentDecision, AnswerAudit]


@pytest.mark.asyncio
async def test_audit_correction_cannot_introduce_a_nonexistent_source():
    from agents.decision_engine import DecisionEngine

    invalid = dict(
        summary="错误引用",
        answer="事实。[E999]",
        claims=[
            dict(
                statement="事实",
                basis="world",
                supports=[dict(evidence_id="E999", quote="无原文")],
            )
        ],
    )
    model = ScriptedModel(
        [], audits=[dict(approved=True, summary="错误修正应被阻止", correction=invalid)]
    )
    runtime = runtime_for(model)
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    issues = await engine.audit(
        AgentDecision.model_validate(decision(answer="待核验", review_required=True))
    )
    assert (
        issues and engine.audited_decision is None and not engine.audit_result.approved
    )
    assert not engine.needs


@pytest.mark.asyncio
async def test_web_publication_filter_uses_model_parameters_not_query_keywords():
    from agents.decision_engine import DecisionEngine
    from agents.decisions import ToolIntent

    class Web:
        async def search_semantic(self, *args, **kwargs):
            return [
                Evidence(
                    id=f"E{i}",
                    chunk_id=i,
                    source_name="新闻",
                    source_type="web",
                    content="正文",
                    content_kind="fulltext",
                    url=f"https://example.org/{i}",
                    published_at=published,
                )
                for i, published in enumerate(["2026-09-05", "2026-09-15", None], 1)
            ]

    runtime = runtime_for(ScriptedModel([]), web_search=Web())
    req = request(allow_web_search=True)
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    ordinary = ToolIntent.model_validate(
        intent(
            "search_web",
            query="没有时间词的任务",
            published_from="2026-09-13",
            published_to="2026-10-13",
        )
    )
    assert [e.published_at for e in await engine.execute_tool(ordinary)] == [
        "2026-09-15"
    ]
    unrestricted = ordinary.model_copy(
        update=dict(query="最新新闻", published_from=None, published_to=None)
    )
    assert len(await engine.execute_tool(unrestricted)) == 3


@pytest.mark.asyncio
async def test_contextual_history_is_not_forced_into_the_parent_event_period():
    from agents.decision_engine import DecisionEngine
    from core.clock import current_date

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    today = current_date().isoformat()
    claim = dict(
        statement="上半年销量为100辆",
        basis="world",
        need_ids=["news"],
        event_date_from="2026-01-01",
        event_date_to="2026-06-30",
        supports=[dict(evidence_id="E1", quote="2026年上半年销量为100辆")],
    )
    engine.evidence["E1"] = Evidence(
        id="E1",
        chunk_id=1,
        source_name="本轮报道",
        source_type="web",
        content_kind="fulltext",
        content="2026年上半年销量为100辆",
        url="https://example.org/report",
        retrieved_at=today,
        published_at=today,
    )
    draft = AgentDecision.model_validate(
        decision(
            answer="另附历史背景：2026年上半年销量为100辆。[E1]",
            needs=[
                need(
                    "news",
                    source="web",
                    basis="world",
                    temporal="current",
                    date_from="2026-09-13",
                    date_to=today,
                    status="covered",
                    evidence_ids=["E1"],
                )
            ],
            claims=[claim],
        )
    )
    engine.apply_decision(draft)
    assert not engine.final_issues(draft)
    check = dict(
        need_id="news",
        statement=claim["statement"],
        event_date_from="2026-01-01",
        event_date_to="2026-06-30",
        within_period=False,
        reason="正文明确作背景而非近期事件",
        disposition="background",
        answer_excerpt=draft.answer,
    )
    assert engine.check_temporal_audit(
        draft,
        AnswerAudit(approved=True, summary="历史用途明确", temporal_checks=[check]),
    ).approved
    check["answer_excerpt"] = "不存在的背景说明"
    assert not engine.check_temporal_audit(
        draft,
        AnswerAudit(approved=True, summary="无效定位应阻止", temporal_checks=[check]),
    ).approved
    check.update(disposition="event", answer_excerpt=draft.answer)
    assert not engine.check_temporal_audit(
        draft,
        AnswerAudit(approved=True, summary="作为新事件应阻止", temporal_checks=[check]),
    ).approved


@pytest.mark.asyncio
async def test_small_need_update_preserves_original_semantic_description_and_dates():
    from agents.decision_engine import DecisionEngine

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    engine.apply_decision(
        AgentDecision.model_validate(
            decision(
                answer="查询",
                needs=[
                    need(
                        "news",
                        description="指定区间事件",
                        source="web",
                        basis="world",
                        temporal="current",
                        date_from="2026-09-13",
                        date_to="2026-10-13",
                    )
                ],
            )
        )
    )
    engine.apply_decision(
        AgentDecision.model_validate(
            decision(
                answer="完成",
                needs=[dict(id="news", status="covered", evidence_ids=["E1"])],
            )
        )
    )
    updated = engine.needs["news"]
    assert (
        updated.description == "指定区间事件"
        and updated.basis == "world"
        and updated.source == "web"
    )
    assert updated.date_from == "2026-09-13" and updated.temporal == "current"


@pytest.mark.asyncio
async def test_optional_rationale_does_not_need_a_duplicate_model_explanation():
    draft = decision(answer="2")
    draft.pop("rationale")
    runtime = runtime_for(ScriptedModel([draft]))
    await runtime.execute(request().model_copy(update={"goal": "1+1=?"}))
    assert runtime.repository.get("test").status == "COMPLETED"
    assert (
        records(runtime, kind="decision.updated")[-1].payload["decision"]["rationale"]
        == draft["summary"]
    )


@pytest.mark.asyncio
async def test_period_audit_must_cover_answer_facts_even_if_planner_omits_claim_links():
    from agents.decision_engine import DecisionEngine

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    draft = AgentDecision.model_validate(
        decision(
            answer="最近发生了一件事。",
            needs=[
                need(
                    "news",
                    source="web",
                    basis="world",
                    temporal="current",
                    date_from="2026-09-13",
                    date_to="2026-10-13",
                    status="covered",
                )
            ],
        )
    )
    engine.apply_decision(draft)
    audit = engine.check_temporal_audit(
        draft,
        AnswerAudit(approved=True, summary="不能仅凭总评放行", temporal_checks=[]),
    )
    assert not audit.approved and "正文逐项日期复核" in audit.issues[0]


@pytest.mark.asyncio
async def test_exact_duplicates_reuse_without_spending_budget_and_stop_no_progress():
    calls = 0

    async def search(**kwargs):
        nonlocal calls
        calls += 1
        return []

    steps = [
        decision("execute", needs=[need()], tools=[intent(query="乌索哈罗他中央酒店")])
        for _ in range(2)
    ]
    steps.append(
        decision(
            answer="缺少收费资料，不能可靠算总价", needs=[need(status="unavailable")]
        )
    )
    model = ScriptedModel(steps)
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert calls == 1 and len(records(runtime, kind="tool.reused")) == 1
    last_decision_request = [
        messages for schema, messages in model.requests if schema is AgentDecision
    ][-1]
    last_state = json.loads(last_decision_request[-1]["content"].split("\n", 1)[1])
    assert last_state["finalOnly"] and last_state["stopReason"] == "no_progress"
    assert runtime.repository.get("test").status == "COMPLETED"


@pytest.mark.asyncio
async def test_changed_queries_with_identical_evidence_are_detected_as_no_gain():
    async def search(**kwargs):
        return [Evidence(id="E1", chunk_id=4, content=EXTRA, source_name="fix_2.txt")]

    steps = [
        decision("execute", needs=[need()], tools=[intent(query=q)])
        for q in ["住宿收费", "房间费用", "价格查询"]
    ]
    steps.append(decision(answer="只有附加费，不足以计算住宿总价"))
    runtime = runtime_for(ScriptedModel(steps), search)
    await runtime.execute(request())
    assert [
        e.payload["newEvidenceCount"] for e in records(runtime, kind="tool.completed")
    ] == [1, 0, 0]
    assert (
        records(runtime, kind="run.completed")[0].payload["decisionMetrics"][
            "stopReason"
        ]
        == "no_progress"
    )


@pytest.mark.asyncio
async def test_budget_exhaustion_synthesizes_instead_of_throwing_generation_failure():
    async def search(**kwargs):
        return []

    def finish(messages):
        state = json.loads(messages[-1]["content"].split("\n", 1)[1])
        assert state["finalOnly"] and state["remainingToolCalls"] == 0
        return decision(answer="本轮未找到可核验收费，无法给出可靠总价")

    model = ScriptedModel(
        [decision("execute", needs=[need()], tools=[intent(query="基础房费")]), finish]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request(tool_max_calls=1))
    assert runtime.repository.get("test").status == "COMPLETED"
    assert not records(runtime, kind="run.failed")


@pytest.mark.asyncio
async def test_web_permission_is_enforced_even_if_model_requests_it():
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[need(source="web", temporal="current")],
                tools=[intent("search_web", query="现任人员")],
            ),
            decision(answer="本轮没有联网权限，请提供可核验来源"),
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(request(allow_web_search=False))
    assert not records(runtime, kind="tool.started")
    assert (
        records(runtime, kind="tool.blocked")[0].payload["error"]["code"]
        == "TOOL_POLICY"
    )


@pytest.mark.asyncio
async def test_tool_source_must_match_missing_need():
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[need()],
                tools=[intent("search_web", query="虚构酒店")],
            ),
            decision(answer="请补充本地收费资料"),
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(request(allow_web_search=True))
    assert not records(runtime, kind="tool.started")
    assert records(runtime, kind="tool.blocked")


@pytest.mark.asyncio
async def test_search_failure_is_not_an_empty_result_or_success():
    async def search(**kwargs):
        raise asyncio.TimeoutError()

    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="基础房费")]),
            decision(answer="知识库请求超时，尚不能核实总价"),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    failure = records(runtime, kind="tool.failed")[0].payload
    assert failure["status"] == "error"
    assert failure["error"]["code"] == "TIMEOUT"
    assert not records(runtime, kind="tool.completed")


@pytest.mark.asyncio
async def test_invalid_calculator_inputs_are_blocked_without_execution():
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[need(source="any")],
                tools=[
                    intent(
                        "calculator",
                        expression="1270+999",
                        supports=[dict(evidence_id="conversation", quote="1270")],
                    )
                ],
            ),
            decision(answer="缺少999的来源"),
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(request().model_copy(update={"goal": "已知1270元"}))
    assert not records(runtime, kind="tool.started")
    assert "999" in records(runtime, kind="tool.blocked")[0].payload["detail"]
    assert "原文支持" in records(runtime, kind="tool.blocked")[0].payload["detail"]


@pytest.mark.asyncio
async def test_invalid_schema_repair_is_bounded_and_explains_failure():
    model = ScriptedModel(
        [
            ModelResponseError("broken-secret-response"),
            ModelResponseError("broken-secret-response"),
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(request())
    error = records(runtime, kind="run.failed")[0].payload["error"]
    assert error["code"] == "DECISION_SCHEMA" and error["stage"] == "decision"
    assert len(model.requests) == 2
    assert "secret" not in json.dumps(error)


@pytest.mark.asyncio
async def test_model_auth_failure_has_actionable_code_not_generic_failed():
    runtime = runtime_for(ScriptedModel([ModelAuthError("private-key")]))
    await runtime.execute(request())
    error = records(runtime, kind="run.failed")[0].payload["error"]
    assert error["code"] == "MODEL_AUTH" and "凭证" in error["remedy"]
    assert "private-key" not in json.dumps(error)


def test_provider_timeout_keeps_its_typed_reason_even_with_transport_cause():
    import httpx
    from models.llm import ModelTimeoutError
    from agents.decision_engine import public_error

    error = ModelTimeoutError("provider read timeout")
    error.__cause__ = httpx.ReadTimeout("read")
    details = public_error(error, "decision")
    assert details["code"] == "TIMEOUT" and details["retryable"]


@pytest.mark.asyncio
async def test_source_quotes_cannot_be_invented_and_bad_answer_never_streams():
    async def search(**kwargs):
        return [Evidence(id="E1", chunk_id=1, content=EXTRA, source_name="fix_2.txt")]

    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="收费")]),
            decision(
                needs=[need(status="covered", evidence_ids=["E1"])],
                assessments=[dict(evidence_id="E1", relevant=True, reason="附加费")],
                answer="最低总价9999元",
                claims=[
                    dict(
                        statement="9999元",
                        supports=[dict(evidence_id="E1", quote="房费9999元")],
                    )
                ],
            ),
            decision(
                answer="资料只有附加费，不能推断总价",
                needs=[need(status="unavailable")],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert "9999" not in "".join(
        e.payload["delta"] for e in records(runtime, kind="message.delta")
    )


@pytest.mark.asyncio
async def test_research_uses_same_decisions_and_produces_report_contract():
    runtime = runtime_for(ScriptedModel([decision(answer="尚缺项目费用资料")]))
    await runtime.execute(request().model_copy(update={"agent_message_id": None}))
    run = runtime.repository.get("test")
    assert (
        run.status == "COMPLETED"
        and run.report["sections"][0]["content"] == "尚缺项目费用资料"
    )
    assert records(runtime, kind="decision.updated")


@pytest.mark.asyncio
async def test_cancellation_interrupts_pending_model_call():
    entered = asyncio.Event()

    class WaitingModel:
        async def structured(self, *args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

    runtime = runtime_for(WaitingModel())
    task = asyncio.create_task(runtime.execute(request()))
    await asyncio.wait_for(entered.wait(), 1)
    await runtime.cancel("test")
    await asyncio.wait_for(task, 2)
    assert runtime.repository.get("test").status == "CANCELLED"


@pytest.mark.asyncio
async def test_parallel_independent_calls_get_distinct_ids_and_shared_budget():
    async def search(**kwargs):
        await asyncio.sleep(0.01)
        return []

    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[need("a"), need("b")],
                parallel_tools=True,
                tools=[intent(key="a", query="资料A"), intent(key="b", query="资料B")],
            ),
            decision(answer="需要补充资料"),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request(tool_max_calls=1))
    assert len(records(runtime, kind="tool.started")) == 1
    assert (
        len(
            {
                e.payload["callId"]
                for e in records(runtime, kind="tool.started")
                + records(runtime, kind="tool.blocked")
            }
        )
        == 2
    )


@pytest.mark.asyncio
async def test_stale_news_cannot_support_current_role_even_when_model_marks_it_current():
    class Web:
        async def search(self, query, top_k=5):
            return [
                Evidence(
                    id="W1",
                    chunk_id="w1",
                    source_name="旧任命新闻",
                    url="https://example.org/old",
                    content="示例甲担任首相。",
                    content_kind="fulltext",
                    source_type="web",
                    published_at="2025-02-01",
                )
            ]

    requirement = need(
        source="web",
        temporal="current",
        time_scope="as_of",
        date_from="2026-01-01",
        date_to="2026-10-12",
    )
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[requirement],
                tools=[intent("search_web", query="截至2026-10-12的现任首相")],
            ),
            decision(
                needs=[{**requirement, "status": "covered", "evidence_ids": ["E1"]}],
                assessments=[
                    dict(
                        evidence_id="E1",
                        relevant=True,
                        supports_current=True,
                        reason="模型错误地认可旧新闻",
                    )
                ],
                answer="现任首相是示例甲。",
                claims=[
                    dict(
                        statement="现任首相示例甲",
                        need_ids=["price"],
                        supports=[dict(evidence_id="E1", quote="示例甲担任首相。")],
                    )
                ],
            ),
            decision(
                needs=[{**requirement, "status": "unavailable"}],
                answer="旧任命报道不足以核实当前身份。",
            ),
        ]
    )
    runtime = runtime_for(model, web_search=Web())
    await runtime.execute(request(allow_web_search=True))
    assert "示例甲" not in runtime.repository.get("test").report["answer"]


@pytest.mark.asyncio
async def test_semantic_historical_query_preserves_its_year_without_rewriting():
    queries = []

    class Web:
        async def search(self, query, top_k=5):
            queries.append(query)
            return [
                Evidence(
                    id="W1",
                    chunk_id="w1",
                    source_name="历史任命公告",
                    url="https://example.org/history",
                    content="2025年2月示例甲担任职务。",
                    content_kind="fulltext",
                    source_type="web",
                    published_at="2025-02-01",
                )
            ]

    requirement = need(
        source="web",
        temporal="historical",
        date_from="2025-02-01",
        date_to="2025-02-28",
    )
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[requirement],
                tools=[intent("search_web", query="2025年2月历史任命公告")],
            ),
            decision(
                needs=[{**requirement, "status": "covered", "evidence_ids": ["E1"]}],
                assessments=[
                    dict(evidence_id="E1", relevant=True, reason="满足指定历史时间")
                ],
                answer="历史资料：2025年2月示例甲担任职务。[E1]",
                claims=[
                    dict(
                        statement="2025年2月任命",
                        need_ids=["price"],
                        supports=[
                            dict(evidence_id="E1", quote="2025年2月示例甲担任职务。")
                        ],
                    )
                ],
            ),
        ]
    )
    runtime = runtime_for(model, web_search=Web())
    await runtime.execute(request(allow_web_search=True))
    assert queries == ["2025年2月历史任命公告"]
    assert runtime.repository.get("test").status == "COMPLETED"


@pytest.mark.asyncio
async def test_semantic_auditor_detects_fee_omission_and_forces_correction():
    async def search(**kwargs):
        return [
            Evidence(
                id="candidate1", chunk_id=1, content=EXTRA, source_name="fix_2.txt"
            ),
            Evidence(
                id="candidate2", chunk_id=2, content=BASE, source_name="fix_1.txt"
            ),
        ]

    claims = [
        dict(
            statement="基础费与附加费来自两份资料",
            supports=[
                dict(evidence_id="E1", quote=EXTRA),
                dict(evidence_id="E2", quote=BASE),
            ],
        )
    ]
    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="酒店收费")]),
            decision(
                needs=[need(status="covered", evidence_ids=["E1", "E2"])],
                assessments=[
                    dict(evidence_id="E1", relevant=True, reason="附加费"),
                    dict(evidence_id="E2", relevant=True, reason="基础费"),
                ],
                answer="总价249元。[E1]",
                claims=claims,
                review_required=True,
            ),
            decision(
                needs=[need(status="covered", evidence_ids=["E1", "E2"])],
                answer="总价11360元，基础费11111元加附加费249元。[E1][E2]",
                claims=claims,
                review_required=True,
            ),
        ],
        audits=[
            dict(
                approved=False,
                summary="249元仅是附加费，漏算基础费11111元",
                issues=["应将两份文件收费相加"],
            ),
            dict(approved=True, summary="已修正为11360元，完整覆盖费用"),
        ],
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert "11360" in runtime.repository.get("test").report["answer"]
    assert len(records(runtime, kind="message.delta")) == 1
    assert [schema for schema, _ in model.requests] == [
        AgentDecision,
        AgentDecision,
        AnswerAudit,
        AnswerRevision,
        AnswerAudit,
    ]
    revision_payload = json.loads(model.requests[3][1][-1]["content"].split("\n", 1)[1])
    assert revision_payload["issues"] == ["应将两份文件收费相加"]


@pytest.mark.asyncio
async def test_followup_resolution_is_model_based_and_retains_history():
    from models.schemas import ChatMessage

    def resolve(messages):
        text = json.dumps(messages, ensure_ascii=False)
        assert "南京浦口区" in text and "现在呢" in text
        return decision(
            action="clarify",
            resolved_goal="核实南京浦口区当前天气",
            answer="缺少当前天气来源，需要联网权限或用户提供观测数据",
        )

    runtime = runtime_for(ScriptedModel([resolve]))
    await runtime.execute(
        request().model_copy(
            update={
                "goal": "现在呢",
                "context_messages": [
                    ChatMessage(role="user", content="南京浦口区天气怎么样")
                ],
            }
        )
    )
    assert (
        records(runtime, kind="decision.updated")[0].payload["decision"]["resolvedGoal"]
        == "核实南京浦口区当前天气"
    )


@pytest.mark.asyncio
async def test_current_tag_on_supplied_price_rules_does_not_require_external_web_sources():
    async def search(**kwargs):
        return [
            Evidence(id="candidate", chunk_id=1, content=BASE, source_name="fix_1.txt")
        ]

    material = need(temporal="current", basis="material")
    model = ScriptedModel(
        [
            decision("execute", needs=[material], tools=[intent(query="酒店基础收费")]),
            decision(
                needs=[{**material, "status": "covered", "evidence_ids": ["E1"]}],
                assessments=[
                    dict(evidence_id="E1", relevant=True, reason="给定资料中的规则")
                ],
                answer="按给定资料，第一层基础费1270元。[E1]",
                claims=[
                    dict(
                        statement="材料规则1270元",
                        need_ids=["price"],
                        supports=[dict(evidence_id="E1", quote="第一层收费1270元")],
                    )
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert runtime.repository.get("test").status == "COMPLETED"
    assert "1270" in runtime.repository.get("test").report["answer"]
    assert not records(runtime, kind="node.failed")


@pytest.mark.asyncio
async def test_current_world_answer_without_sources_is_audited_even_if_it_omits_claims():
    world = need(source="web", basis="world", temporal="current", status="unavailable")
    model = ScriptedModel(
        [
            decision(needs=[world], answer="现任首相是旧知识里的名字，2025年2月就任。"),
            decision(needs=[world], answer="没有取得当前来源，无法核实现任身份。"),
        ],
        audits=[
            dict(
                approved=False,
                summary="没有本轮来源，不能凭训练知识断言现任或就职日期",
                issues=["撤下没有出处的人名和日期"],
            ),
            dict(approved=True, summary="已明确无法核实，没有发布现任断言"),
        ],
    )
    runtime = runtime_for(model)
    await runtime.execute(request())
    answer = runtime.repository.get("test").report["answer"]
    assert "2025年2月" not in answer and "无法核实" in answer
    assert len(records(runtime, kind="message.delta")) == 1


@pytest.mark.asyncio
async def test_completed_calculation_plan_writes_and_reviews_without_replanning():
    async def search(**kwargs):
        return [
            Evidence(id="a", chunk_id=1, content=BASE, source_name="fix_1.txt"),
            Evidence(id="b", chunk_id=2, content=EXTRA, source_name="fix_2.txt"),
        ]

    class Model(ScriptedModel):
        async def chat(self, messages, **kwargs):
            self.requests.append(("writer", messages))
            assert "11360" in messages[-1]["content"]
            return ModelChatResult(
                content="按资料收费，三人至少11360元。[E1][E2]", model=self.model
            )

    model = Model(
        [
            decision(
                "execute",
                needs=[need(), need("total", source="any", basis="derived")],
                tools=[intent(query="酒店收费")],
            ),
            decision(
                "execute",
                needs=[need(status="covered", evidence_ids=["E1", "E2"])],
                assessments=[
                    dict(evidence_id="E1", relevant=True, reason="基础费"),
                    dict(evidence_id="E2", relevant=True, reason="附加费"),
                ],
                tools=[
                    intent(
                        "calculator",
                        key="total",
                        expression="1270+3111+6730+37+68+144",
                        supports=[
                            dict(evidence_id="E1", quote=BASE),
                            dict(evidence_id="E2", quote=EXTRA),
                        ],
                    )
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert (
        runtime.repository.get("test").report["answer"]
        == "按资料收费，三人至少11360元。[E1][E2]"
    )
    assert len([schema for schema, _ in model.requests if schema is AgentDecision]) == 2
    assert len(records(runtime, kind="tool.started")) == 2


@pytest.mark.asyncio
async def test_review_transport_failure_stops_without_another_plan_or_false_success():
    from models.llm import ModelTimeoutError

    class Model(ScriptedModel):
        async def structured(self, messages, schema, **kwargs):
            if schema is AnswerAudit:
                self.requests.append((schema, messages))
                raise ModelTimeoutError("provider timeout")
            return await super().structured(messages, schema, **kwargs)

    model = Model([decision(answer="需要复核的答复", review_required=True)])
    runtime = runtime_for(model)
    await runtime.execute(request())
    run = runtime.repository.get("test")
    assert run.status == "FAILED"
    failure = records(runtime, kind="run.failed")[0].payload["error"]
    assert failure["code"] == "TIMEOUT" and failure["stage"] == "answer_audit"
    assert len(model.requests) == 2
    assert not records(runtime, kind="message.delta")


@pytest.mark.asyncio
async def test_multi_letter_calculator_variables_keep_their_bindings_and_provenance():
    class Model(ScriptedModel):
        async def chat(self, messages, **kwargs):
            return ModelChatResult(content="合计11360元", model=self.model)

    model = Model(
        [
            decision(
                "execute",
                needs=[need(source="any", basis="derived")],
                tools=[
                    intent(
                        "calculator",
                        expression="first_floor + second_floor + fourth_floor",
                        variables={
                            "first_floor": "1307",
                            "second_floor": "3179",
                            "fourth_floor": "6874",
                        },
                        supports=[
                            dict(evidence_id="conversation", quote="1307、3179、6874")
                        ],
                    )
                ],
            ),
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(
        request().model_copy(
            update={"goal": "已知三层总价分别为1307、3179、6874，求和"}
        )
    )
    receipt = records(runtime, kind="tool.completed")[0].payload
    assert receipt["result"]["result"] == "11360"
    assert receipt["variables"]["first_floor"] == "1307"
    assert runtime.repository.get("test").status == "COMPLETED"


@pytest.mark.asyncio
async def test_derived_answer_is_audited_even_without_a_successful_calculator_call():
    model = ScriptedModel(
        [
            decision(
                answer="总费用249元",
                needs=[need(source="any", basis="derived", status="unavailable")],
            ),
            decision(answer="缺少费用资料，不能给出总价"),
        ],
        audits=[
            dict(
                approved=False,
                summary="数值没有完整出处",
                issues=["撤回没有来源的金额"],
            ),
            dict(approved=True, summary="已撤回未核实金额"),
        ],
    )
    runtime = runtime_for(model)
    await runtime.execute(request())
    assert "249" not in runtime.repository.get("test").report["answer"]
    assert len([schema for schema, _ in model.requests if schema is AnswerAudit]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("goal", "answer"),
    [
        ("1+1=?", "1+1=2"),
        ("为什么水会结冰？", "降温时水分子形成有序的晶体结构。"),
        ("解释勾股定理", "直角三角形中，两条直角边的平方和等于斜边的平方。"),
        (
            "写一句关于最新总统的虚构小说开头",
            "新总统登上月球的第一天，发现国会是一片森林。",
        ),
        ("你好", "你好，有什么需要我帮忙的？"),
        ("把这句话写得简洁一些：我们现在开始进行工作", "我们开始工作。"),
    ],
)
async def test_stable_general_need_and_claim_do_not_require_document_quotes(
    goal, answer
):
    model = ScriptedModel(
        [
            decision(
                resolved_goal=goal,
                answer=answer,
                needs=[
                    need("general", source="any", basis="general", status="covered")
                ],
                claims=[dict(statement=answer, basis="general", need_ids=["general"])],
            )
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(request().model_copy(update={"goal": goal}))
    assert runtime.repository.get("test").report["answer"] == answer
    assert len(model.requests) == 1
    assert not records(runtime, kind="tool.started")


@pytest.mark.asyncio
async def test_mixed_general_and_document_claims_have_independent_grounding():
    async def search(**kwargs):
        return [
            Evidence(id="candidate", chunk_id=1, content=BASE, source_name="fix_1.txt")
        ]

    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="第一层基础费")]),
            decision(
                needs=[need(status="covered", evidence_ids=["E1"])],
                assessments=[
                    dict(evidence_id="E1", relevant=True, reason="基础收费表")
                ],
                answer="1+1=2。资料中的第一层基础费为1270元。[E1]",
                claims=[
                    dict(statement="1+1=2", basis="general"),
                    dict(
                        statement="第一层基础费1270元",
                        basis="material",
                        need_ids=["price"],
                        supports=[dict(evidence_id="E1", quote="第一层收费1270元")],
                    ),
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(
        request().model_copy(update={"goal": "1+1是多少？另外查资料中的第一层基础费。"})
    )
    assert runtime.repository.get("test").status == "COMPLETED"
    assert "1+1=2" in runtime.repository.get("test").report["answer"]
    assert not records(runtime, kind="node.failed")
    assert len([schema for schema, _ in model.requests if schema is AnswerAudit]) == 1


@pytest.mark.asyncio
async def test_missing_material_does_not_discard_an_independent_general_answer():
    async def search(**kwargs):
        return []

    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="酒店收费")]),
            decision(
                needs=[need(status="unavailable")],
                answer="1+1=2。尚未找到酒店收费，不能确定住宿总价。",
                claims=[dict(statement="1+1=2", basis="general")],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(
        request().model_copy(update={"goal": "回答1+1，并计算酒店住宿费用"})
    )
    answer = runtime.repository.get("test").report["answer"]
    assert "1+1=2" in answer and "不能确定住宿总价" in answer
    assert not records(runtime, kind="node.failed")


@pytest.mark.asyncio
async def test_unrelated_attachment_does_not_force_citations_for_basic_math():
    from agents.decision_engine import DecisionEngine

    runtime = runtime_for(
        ScriptedModel(
            [
                decision(
                    answer="1+1=2", claims=[dict(statement="1+1=2", basis="general")]
                )
            ]
        )
    )
    req = request().model_copy(update={"goal": "1+1=?"})
    run = await runtime.accept(req)
    engine = DecisionEngine(runtime, req, run, [], attachment_text="某份无关的会议记录")
    result = await engine.run_loop()
    assert result.answer == "1+1=2"
    assert not records(runtime, kind="node.failed")


@pytest.mark.asyncio
async def test_general_label_cannot_bypass_a_linked_material_need():
    from agents.decision_engine import DecisionEngine

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    item = AgentDecision.model_validate(
        decision(
            answer="酒店总价249元",
            needs=[need(source="any", status="covered")],
            claims=[
                dict(statement="酒店总价249元", basis="general", need_ids=["price"])
            ],
        )
    )
    engine.apply_decision(item)
    assert any("原文支持" in issue for issue in engine.final_issues(item))


@pytest.mark.asyncio
async def test_partial_need_update_preserves_current_world_policy_and_source_ids():
    from agents.decision_engine import DecisionEngine

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    engine.apply_decision(
        AgentDecision.model_validate(
            decision(
                answer="等待核验",
                needs=[
                    need(
                        source="web",
                        basis="world",
                        temporal="current",
                        date_from="2026-10-01",
                        date_to="2026-10-13",
                        status="covered",
                        evidence_ids=["E1"],
                    )
                ],
            )
        )
    )
    engine.apply_decision(
        AgentDecision.model_validate(
            decision(
                answer="说明缺口",
                needs=[dict(id="price", description="现任身份", status="unavailable")],
            )
        )
    )
    saved = engine.needs["price"]
    assert (
        saved.source == "web" and saved.basis == "world" and saved.temporal == "current"
    )
    assert saved.date_from == "2026-10-01" and saved.date_to == "2026-10-13"
    assert saved.evidence_ids == ["E1"] and saved.status == "unavailable"


@pytest.mark.asyncio
async def test_as_of_status_does_not_require_publication_on_the_query_day():
    from datetime import timedelta
    from agents.decision_engine import DecisionEngine
    from agents.decisions import EvidenceNeed, SourceAssessment
    from core.clock import current_date

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    query_date = current_date()
    today = query_date.isoformat()
    recent_publication = (query_date - timedelta(days=1)).isoformat()
    engine.evidence["E1"] = Evidence(
        id="E1",
        chunk_id="web:role",
        source_name="当前官方名单",
        source_type="web",
        content="当前首相：示例甲",
        url="https://example.org/current",
        content_kind="fulltext",
        retrieved_at=today,
        published_at=recent_publication,
    )
    engine.assessments["E1"] = SourceAssessment(
        evidence_id="E1",
        relevant=True,
        supports_current=True,
        reason="本轮读取的官方现任名单，正文明确当前任职状态",
    )
    status = EvidenceNeed(
        id="pm",
        description="截至今天的现任首相",
        basis="world",
        source="web",
        temporal="current",
        time_scope="as_of",
        date_from=today,
        date_to=today,
    )
    assert engine.valid_current_sources(status, ["E1"]) == [engine.evidence["E1"]]
    engine.evidence["E1"].published_at = (query_date - timedelta(days=30)).isoformat()
    assert engine.valid_current_sources(status, ["E1"]) == [engine.evidence["E1"]]
    engine.evidence["E1"].published_at = (query_date - timedelta(days=31)).isoformat()
    assert engine.valid_current_sources(status, ["E1"]) == []
    engine.evidence["E1"].published_at = recent_publication
    from agents.decisions import FactSupport

    assert engine.support_text(FactSupport(evidence_id="E1", quote="当前官方名单"))
    # Publication dates do not decide event dates; the mandatory temporal
    # audit checks the actual event interval independently.
    period = status.model_copy(update={"time_scope": "period"})
    assert engine.valid_current_sources(period, ["E1"]) == [engine.evidence["E1"]]
    engine.evidence["E1"].published_at = None
    assert engine.valid_current_sources(status, ["E1"])
    assert engine.valid_current_sources(period, ["E1"]) == [engine.evidence["E1"]]
    engine.assessments["E1"].supports_current = False
    # Optional planner flags do not replace the independent semantic audit.
    assert engine.valid_current_sources(status, ["E1"]) == [engine.evidence["E1"]]
    engine.evidence["E1"].published_at = today
    assert engine.valid_current_sources(period, ["E1"]) == [engine.evidence["E1"]]
    tomorrow = (query_date + timedelta(days=1)).isoformat()
    forecast = period.model_copy(update={"date_from": tomorrow, "date_to": tomorrow})
    assert engine.valid_current_sources(forecast, ["E1"]) == [engine.evidence["E1"]]


@pytest.mark.asyncio
async def test_cached_old_body_is_not_restamped_as_read_today():
    from agents.decision_engine import DecisionEngine
    from agents.decisions import ToolIntent

    class Web:
        async def search_semantic(self, *args, **kwargs):
            return [
                Evidence(
                    id="E1",
                    chunk_id="old",
                    source_name="旧缓存",
                    content="旧正文",
                    source_type="web",
                    content_kind="fulltext",
                    url="https://example.org/old",
                    retrieved_at="2025-02-01",
                )
            ]

    runtime = runtime_for(ScriptedModel([]), web_search=Web())
    req = request(allow_web_search=True)
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    result = await engine.execute_tool(
        ToolIntent.model_validate(intent("search_web", query="现任状态"))
    )
    assert result[0].retrieved_at == "2025-02-01"


@pytest.mark.asyncio
async def test_fresh_article_about_old_event_cannot_be_reported_as_a_new_event():
    from agents.decision_engine import DecisionEngine
    from core.clock import current_date

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    today = current_date().isoformat()
    body = "该事件发生在2026年1月至3月。"
    engine.evidence["E1"] = Evidence(
        id="E1",
        chunk_id="review",
        source_name="近期发布的回顾",
        source_type="web",
        content=body,
        url="https://example.org/review",
        content_kind="fulltext",
        retrieved_at=today,
        published_at=today,
    )
    draft = AgentDecision.model_validate(
        decision(
            answer="近期发生了该事件。[E1]",
            needs=[
                need(
                    source="web",
                    basis="world",
                    temporal="current",
                    time_scope="period",
                    date_from="2026-09-01",
                    date_to=today,
                    status="covered",
                    evidence_ids=["E1"],
                )
            ],
            assessments=[dict(evidence_id="E1", relevant=True, reason="回顾旧事")],
            claims=[
                dict(
                    statement="该事件近期发生",
                    need_ids=["price"],
                    basis="world",
                    event_date_from="2026-01-01",
                    event_date_to="2026-03-31",
                    supports=[dict(evidence_id="E1", quote=body)],
                )
            ],
        )
    )
    engine.apply_decision(draft)
    assert engine.valid_current_sources(engine.needs["price"], ["E1"])
    assert not engine.final_issues(draft)
    draft.claims[0].event_date_from = None
    draft.claims[0].event_date_to = None
    assert not engine.final_issues(draft)
    check = dict(
        need_id="price",
        statement=draft.claims[0].statement,
        event_date_from="2026-01-01",
        event_date_to="2026-03-31",
        within_period=False,
        reason="文章近期发布，但事件发生于年初",
    )
    audit = engine.check_temporal_audit(
        draft,
        AnswerAudit(approved=True, summary="必须复核实际时间", temporal_checks=[check]),
    )
    assert not audit.approved and "发生时间未通过复核" in audit.issues[0]
    check.update(event_date_from=today, event_date_to=today, within_period=True)
    assert engine.check_temporal_audit(
        draft,
        AnswerAudit(
            approved=True, summary="实际事件发生在范围内", temporal_checks=[check]
        ),
    ).approved


@pytest.mark.asyncio
async def test_missing_optional_source_flags_do_not_reject_a_valid_literal_quote():
    async def search(**kwargs):
        return [
            Evidence(id="candidate", chunk_id=1, source_name="fix_1.txt", content=BASE)
        ]

    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="第一层基础收费")]),
            decision(
                needs=[need(status="covered", evidence_ids=["E1"])],
                answer="第一层基础收费为1270元。[E1]",
                claims=[
                    dict(
                        statement="第一层基础收费1270元",
                        basis="material",
                        need_ids=["price"],
                        supports=[dict(evidence_id="E1", quote=BASE)],
                    )
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(
        request().model_copy(update={"goal": "根据资料，第一层基础收费是多少？"})
    )
    run = runtime.repository.get("test")
    assert run.status == "COMPLETED" and "1270" in run.report["answer"]
    assert [e.id for e in run.evidence] == ["E1"]
    assert [s for s, _ in model.requests] == [AgentDecision, AgentDecision, AnswerAudit]


@pytest.mark.asyncio
async def test_clock_quote_uses_the_exact_context_supplied_before_model_wait(
    monkeypatch,
):
    from agents.decision_engine import DecisionEngine
    from agents.decisions import FactSupport

    supplied = '<runtime_time trust="server">当前时间：2026-10-13T23:59:58+08:00</runtime_time>'
    monkeypatch.setattr("agents.decision_engine.time_context", lambda: supplied)
    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    assert engine.snapshot()["clock"] == supplied
    monkeypatch.setattr(
        "agents.decision_engine.time_context",
        lambda: "当前时间：2026-10-14T00:00:20+08:00",
    )
    assert (
        engine.support_text(
            FactSupport(evidence_id="clock", quote="2026-10-13T23:59:58+08:00")
        )
        == supplied
    )
    assert (
        engine.support_text(FactSupport(evidence_id="clock", quote="2025-01-01"))
        is None
    )


@pytest.mark.asyncio
async def test_user_context_claim_is_supported_without_project_retrieval():
    from models.schemas import ChatMessage

    model = ScriptedModel(
        [
            decision(
                answer="你说你住在南京。",
                needs=[
                    need(
                        "city", source="conversation", basis="context", status="covered"
                    )
                ],
                claims=[
                    dict(
                        statement="你住在南京",
                        basis="context",
                        need_ids=["city"],
                        supports=[dict(evidence_id="conversation", quote="我住在南京")],
                    )
                ],
            )
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(
        request().model_copy(
            update={
                "goal": "我刚才说住在哪里？",
                "context_messages": [ChatMessage(role="user", content="我住在南京")],
            }
        )
    )
    assert runtime.repository.get("test").status == "COMPLETED"
    assert not records(runtime, kind="tool.started")


@pytest.mark.asyncio
async def test_grounded_claim_still_checks_the_actual_answer_semantically():
    async def search(**kwargs):
        return [
            Evidence(id="candidate", chunk_id=1, content=BASE, source_name="fix_1.txt")
        ]

    claim = dict(
        statement="第一层基础费1270元",
        supports=[dict(evidence_id="E1", quote="第一层收费1270元")],
    )
    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="第一层基础费")]),
            decision(
                needs=[need(status="covered", evidence_ids=["E1"])],
                assessments=[dict(evidence_id="E1", relevant=True, reason="基础费")],
                answer="第一层基础费9999元。[E1]",
                claims=[claim],
            ),
            decision(answer="第一层基础费1270元。[E1]", claims=[claim]),
        ],
        audits=[
            dict(
                approved=False,
                summary="正文金额与原文和claims不一致",
                issues=["把正文9999元修正为1270元"],
            ),
            dict(approved=True, summary="正文与来源一致"),
        ],
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert runtime.repository.get("test").report["answer"] == "第一层基础费1270元。[E1]"
    assert "9999" not in "".join(
        e.payload["delta"] for e in records(runtime, kind="message.delta")
    )


@pytest.mark.asyncio
async def test_repeated_validation_failure_is_not_reported_as_missing_knowledge():
    bad = decision(
        answer="1+1=2",
        claims=[
            dict(statement="1+1=2", supports=[dict(evidence_id="E404", quote="2")])
        ],
    )
    runtime = runtime_for(ScriptedModel([bad, bad]))
    await runtime.execute(request().model_copy(update={"goal": "1+1=?"}))
    assert runtime.repository.get("test").status == "FAILED"
    failure = records(runtime, kind="run.failed")[0].payload["error"]
    assert (
        failure["code"] == "ANSWER_VALIDATION"
        and failure["stage"] == "answer_validation"
    )
    assert "E404" in failure["message"] and "补充资料" not in failure["remedy"]
    assert not records(runtime, kind="message.delta")


@pytest.mark.asyncio
async def test_conflicting_source_facts_are_not_resolved_by_arbitrarily_choosing_one():
    async def search(**kwargs):
        return [
            Evidence(
                id="a", chunk_id=1, content="第一层收费1270元。", source_name="收费表A"
            ),
            Evidence(
                id="b", chunk_id=2, content="第一层收费1500元。", source_name="收费表B"
            ),
        ]

    model = ScriptedModel(
        [
            decision("execute", needs=[need()], tools=[intent(query="第一层收费")]),
            decision(
                needs=[need(status="covered", evidence_ids=["E1", "E2"])],
                assessments=[
                    dict(evidence_id=key, relevant=True, reason="同一收费项目")
                    for key in ["E1", "E2"]
                ],
                answer="收费1270元。[E1]",
                claims=[
                    dict(
                        statement="收费1270元",
                        supports=[dict(evidence_id="E1", quote="收费1270元")],
                    )
                ],
            ),
            decision(
                needs=[need(status="unavailable")],
                answer="两份收费表有冲突：1270元与1500元，缺少生效日期，暂不能确定适用价格。[E1][E2]",
                claims=[
                    dict(
                        statement="两份表分别为1270与1500",
                        basis="material",
                        supports=[
                            dict(evidence_id="E1", quote="第一层收费1270元。"),
                            dict(evidence_id="E2", quote="第一层收费1500元。"),
                        ],
                    )
                ],
            ),
        ],
        audits=[
            dict(
                approved=False,
                summary="不同资料冲突且缺少适用条件",
                issues=["说明两份价格冲突，不能选择其中一份作为确定结果"],
            ),
            dict(approved=True, summary="已准确说明冲突和缺失条件"),
        ],
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert "有冲突" in runtime.repository.get("test").report["answer"]


@pytest.mark.asyncio
async def test_ambiguous_pricing_from_completed_calculation_becomes_a_clarification_not_failure():
    async def search(**kwargs):
        return [
            Evidence(id="a", chunk_id=1, content=BASE, source_name="fix_1.txt"),
            Evidence(id="b", chunk_id=2, content=EXTRA, source_name="fix_2.txt"),
        ]

    class Model(ScriptedModel):
        async def chat(self, messages, **kwargs):
            self.requests.append(("writer", messages))
            return ModelChatResult(
                content="四人至少11504元。[E1][E2]", model=self.model
            )

    question = "资料没有说明基础费的计费单位。第四层两人能否共用一份基础费，还是需要每人分别支付？"
    model = Model(
        [
            decision(
                "execute",
                needs=[need(), need("total", source="any", basis="derived")],
                tools=[intent(query="酒店收费")],
            ),
            decision(
                "execute",
                needs=[need(status="covered", evidence_ids=["E1", "E2"])],
                assessments=[
                    dict(evidence_id=key, relevant=True, reason="收费规则")
                    for key in ["E1", "E2"]
                ],
                tools=[
                    intent(
                        "calculator",
                        key="total",
                        expression="1270+3111+6730+37+68+144*2",
                        supports=[
                            dict(evidence_id="E1", quote=BASE),
                            dict(evidence_id="E2", quote=EXTRA),
                            dict(evidence_id="conversation", quote="两个人"),
                        ],
                    )
                ],
            ),
        ],
        audits=[
            dict(
                approved=False,
                summary="第四层两人共用基础费的规则尚未明确",
                issues=["不能宣称唯一最低价"],
                resolution="clarify",
                clarification_question=question,
            )
        ],
    )
    runtime = runtime_for(model, search)
    await runtime.execute(
        request().model_copy(
            update={
                "goal": "有四个人住宿，一层一个人，二层一个人，第四层两个人，至少多少钱？"
            }
        )
    )
    run = runtime.repository.get("test")
    assert run.status == "COMPLETED" and run.report["answer"] == question
    assert not records(runtime, kind="run.failed")
    assert len([schema for schema, _ in model.requests if schema == "writer"]) == 1
    final = records(runtime, kind="decision.updated")[-1].payload["decision"]
    assert final["action"] == "clarify" and final["stopReason"] == "clarification"
    previous = records(runtime, kind="decision.updated")[-2].payload["decision"]
    assert (
        final["id"] != previous["id"] and final["sequence"] == previous["sequence"] + 1
    )
    assert (
        previous["action"] == "execute" and previous["tools"][0]["tool"] == "calculator"
    )
    assert final["needs"][-1]["status"] == "missing"
    assert "11504" not in "".join(
        e.payload["delta"] for e in records(runtime, kind="message.delta")
    )


@pytest.mark.asyncio
async def test_terminal_answer_with_ambiguous_conditions_uses_semantic_clarification():
    question = "你希望按单利还是复利计算？当前条件不足以确定唯一结果。"
    model = ScriptedModel(
        [
            decision(
                answer="利息确定为100元",
                needs=[need(source="any", basis="derived", status="covered")],
            )
        ],
        audits=[
            dict(
                approved=False,
                summary="计息规则缺失",
                issues=["需要确认单利或复利"],
                resolution="clarify",
                clarification_question=question,
            )
        ],
    )
    runtime = runtime_for(model)
    await runtime.execute(
        request().model_copy(update={"goal": "按给定本金和利率计算第二年利息"})
    )
    assert runtime.repository.get("test").status == "COMPLETED"
    assert runtime.repository.get("test").report["answer"] == question
    assert len(model.requests) == 2 and not records(runtime, kind="run.failed")


@pytest.mark.asyncio
async def test_explicit_conditional_results_can_complete_with_an_unresolved_unique_total():
    async def search(**kwargs):
        return [
            Evidence(id="a", chunk_id=1, content=BASE, source_name="fix_1.txt"),
            Evidence(id="b", chunk_id=2, content=EXTRA, source_name="fix_2.txt"),
        ]

    answer = "无法确定唯一最低价。若基础费按每层一份且两人可以共用，则总价11504元；若每人支付一份基础费，则18234元。请确认计费单位。[E1][E2]"
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[need(), need("unit", source="conversation", basis="context")],
                tools=[intent(query="酒店收费")],
            ),
            decision(
                needs=[need(status="covered", evidence_ids=["E1", "E2"])],
                assessments=[
                    dict(evidence_id=key, relevant=True, reason="收费原文")
                    for key in ["E1", "E2"]
                ],
                answer=answer,
                claims=[
                    dict(
                        statement="收费表给出基础费和附加费",
                        basis="material",
                        supports=[
                            dict(evidence_id="E1", quote=BASE),
                            dict(evidence_id="E2", quote=EXTRA),
                        ],
                    ),
                    dict(
                        statement="按每层基础费共用时11504元",
                        basis="derived",
                        assumptions=["基础费每层一份，第四层两人可以共用"],
                        supports=[
                            dict(evidence_id="E1", quote=BASE),
                            dict(evidence_id="E2", quote=EXTRA),
                            dict(evidence_id="conversation", quote="第四层两个人"),
                        ],
                    ),
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(
        request().model_copy(
            update={"goal": "第一层一个人，第二层一个人，第四层两个人，至少多少钱？"}
        )
    )
    assert runtime.repository.get("test").status == "COMPLETED"
    assert runtime.repository.get("test").report["answer"] == answer
    assert not records(runtime, kind="run.failed")


def test_auditor_clarification_requires_a_question_and_overrides_approval():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AnswerAudit(
            approved=False, summary="条件缺失", temporal_checks=[], resolution="clarify"
        )
    audit = AnswerAudit(
        approved=True,
        summary="需要澄清",
        temporal_checks=[],
        resolution="clarify",
        clarification_question="需要什么条件？",
    )
    assert not audit.approved and audit.correction is None


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["answer", "clarify"])
async def test_partial_prices_conditional_totals_and_limitations_can_reference_incomplete_needs(
    action,
):
    async def search(**kwargs):
        return [
            Evidence(id="a", chunk_id=1, content=BASE, source_name="fix_1.txt"),
            Evidence(id="b", chunk_id=2, content=EXTRA, source_name="fix_2.txt"),
        ]

    answer = "第一层基础费1270元。[E1] 如果基础费每人一份则18234元；如果每层共用一份则11504元。计费单位未明确，无法确定唯一最低价。请确认第四层两人能否共用基础费。"
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[need(), need("total", source="any", basis="derived")],
                tools=[intent(query="酒店计费规则")],
            ),
            decision(
                action,
                answer=answer,
                needs=[
                    need(evidence_ids=["E1", "E2"]),
                    need("total", source="any", basis="derived"),
                ],
                assessments=[
                    dict(
                        evidence_id=key,
                        relevant=True,
                        reason="已知价格，但缺少基础费计费单位",
                    )
                    for key in ["E1", "E2"]
                ],
                claims=[
                    dict(
                        statement="第一层基础费1270元",
                        kind="fact",
                        basis="material",
                        need_ids=["price"],
                        supports=[dict(evidence_id="E1", quote="第一层收费1270元")],
                    ),
                    dict(
                        statement="按每人一份基础费时18234元",
                        kind="conditional",
                        basis="derived",
                        need_ids=["total"],
                        assumptions=["基础费每人分别支付一份"],
                    ),
                    dict(
                        statement="无法确定唯一最低价",
                        kind="limitation",
                        basis="material",
                        need_ids=["price", "total"],
                    ),
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(
        request().model_copy(
            update={"goal": "第一层一个人，第二层一个人，第四层两个人，至少多少钱？"}
        )
    )
    run = runtime.repository.get("test")
    assert run.status == "COMPLETED" and run.report["answer"] == answer
    assert not records(runtime, kind="node.failed")
    assert len([schema for schema, _ in model.requests if schema is AnswerAudit]) == 1
    assert (
        records(runtime, kind="decision.updated")[-1].payload["decision"]["needs"][0][
            "status"
        ]
        == "missing"
    )


@pytest.mark.asyncio
async def test_mislabeling_current_identity_as_a_limitation_does_not_bypass_semantic_audit():
    world = need(source="web", basis="world", temporal="current", status="unavailable")
    model = ScriptedModel(
        [
            decision(
                answer="现任领导人肯定是示例甲。",
                needs=[world],
                claims=[
                    dict(
                        statement="现任领导人是示例甲",
                        kind="limitation",
                        need_ids=["price"],
                    )
                ],
            ),
            decision(
                answer="本轮未取得当前来源，无法核实现任身份。",
                needs=[world],
                claims=[
                    dict(
                        statement="无法核实现任身份",
                        kind="limitation",
                        need_ids=["price"],
                    )
                ],
            ),
        ],
        audits=[
            dict(
                approved=False,
                summary="肯定的人名不是资料缺口说明",
                issues=["撤回未核验的现任身份"],
            ),
            dict(approved=True, summary="已正确说明无法核验"),
        ],
    )
    runtime = runtime_for(model)
    await runtime.execute(request().model_copy(update={"goal": "现任领导人是谁？"}))
    assert "示例甲" not in runtime.repository.get("test").report["answer"]
    assert len([schema for schema, _ in model.requests if schema is AnswerAudit]) == 2
    assert not records(runtime, kind="run.failed")


@pytest.mark.asyncio
async def test_conditional_claim_requires_assumptions_and_still_rejects_invented_quotes():
    from agents.decision_engine import DecisionEngine

    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    draft = AgentDecision.model_validate(
        decision(
            answer="假设下为11504元",
            claims=[dict(statement="条件结果11504元", kind="conditional")],
        )
    )
    assert any("假设" in issue for issue in engine.final_issues(draft))
    draft.claims[0].assumptions = ["基础费共用"]
    from agents.decisions import FactSupport

    draft.claims[0].supports = [FactSupport(evidence_id="E404", quote="未存在的收费表")]
    assert any("无效引文" in issue for issue in engine.final_issues(draft))


@pytest.mark.asyncio
async def test_audited_assumptions_appear_before_the_result_even_if_draft_puts_them_in_a_footnote():
    draft = "四人最低11504元。\n\n注：假设第四层两人共用基础费，资料未明确这一规则。"
    model = ScriptedModel(
        [
            decision(
                answer=draft,
                needs=[need(source="any", basis="derived", status="covered")],
            )
        ],
        audits=[
            dict(
                approved=True,
                summary="在共用基础费的假设下算术正确",
                unresolved_conditions=["第四层两人能否共用一份基础费"],
            )
        ],
    )
    runtime = runtime_for(model)
    await runtime.execute(
        request().model_copy(update={"goal": "四个人住宿至少多少钱？"})
    )
    answer = runtime.repository.get("test").report["answer"]
    assert runtime.repository.get("test").status == "COMPLETED"
    assert answer.startswith("**当前资料还不能确定唯一结果。**")
    assert answer.index("两人能否共用") < answer.index("11504")
    assert (
        records(runtime, kind="decision.updated")[-1].payload["decision"]["action"]
        == "clarify"
    )
    assert not records(runtime, kind="run.failed")


@pytest.mark.asyncio
async def test_trusted_user_source_bank_carries_prices_and_counts_across_turns_without_assistant_values():
    from models.schemas import ChatMessage

    prices = "基础费1270、3111、6730元，附加费用37、68、144元/人。"

    class Model(ScriptedModel):
        async def chat(self, messages, **kwargs):
            return ModelChatResult(
                content="按基础费每人规则，四人共18234元。", model=self.model
            )

    def plan(messages):
        state = json.loads(messages[-1]["content"].split("\n", 1)[1])
        assert [item["id"] for item in state["trustedUserSources"]] == [
            "U1",
            "U2",
            "U3",
        ]
        assert all(
            "99999" not in item["content"] for item in state["trustedUserSources"]
        )
        return decision(
            "execute",
            needs=[need(source="any", basis="derived")],
            tools=[
                intent(
                    "calculator",
                    expression="(1270+37)+(3111+68)+(6730+144)*2",
                    supports=[
                        dict(evidence_id="U1", quote="第四层两个人"),
                        dict(evidence_id="U2", quote=prices),
                    ],
                )
            ],
        )

    runtime = runtime_for(Model([plan]))
    req = request().model_copy(
        update={
            "goal": "基础费按每人计算，确认四人总价",
            "context_messages": [
                ChatMessage(
                    role="user", content="第一层一个人，第二层一个人，第四层两个人"
                ),
                ChatMessage(role="assistant", content="之前错误回答99999元"),
                ChatMessage(role="user", content=prices),
            ],
        }
    )
    await runtime.execute(req)
    assert (
        runtime.repository.get("test").report["answer"]
        == "按基础费每人规则，四人共18234元。"
    )
    assert (
        records(runtime, kind="tool.completed")[0].payload["result"]["result"]
        == "18234"
    )


@pytest.mark.asyncio
async def test_calculator_feedback_identifies_missing_quantity_and_invalid_user_quote():
    from agents.decision_engine import DecisionEngine
    from agents.decisions import ToolIntent
    from models.schemas import ChatMessage

    runtime = runtime_for(ScriptedModel([]))
    req = request().model_copy(
        update={
            "goal": "按人计算",
            "context_messages": [
                ChatMessage(role="user", content="第四层两个人"),
                ChatMessage(role="user", content="基础收费6730元，附加144元/人"),
            ],
        }
    )
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    engine.apply_decision(
        AgentDecision.model_validate(
            decision(answer="待计算", needs=[need(source="any", basis="derived")])
        )
    )
    call = ToolIntent.model_validate(
        intent(
            "calculator",
            expression="(6730+144)*2",
            supports=[dict(evidence_id="U2", quote="基础收费6730元，附加144元/人")],
        )
    )
    assert "2" in engine.validate_intent(
        call
    ) and "trustedUserSources" in engine.validate_intent(call)
    from agents.decisions import FactSupport

    call.supports.append(FactSupport(evidence_id="U1", quote="第四层两个人"))
    assert engine.validate_intent(call) is None
    call.supports[-1].quote = "第四层2人"
    assert "U1『第四层2人』" in engine.validate_intent(call)


@pytest.mark.asyncio
async def test_repeated_invalid_calculator_inputs_are_not_reported_as_missing_documents():
    bad = decision(
        "execute",
        needs=[need(source="any", basis="derived")],
        tools=[
            intent(
                "calculator",
                expression="999",
                supports=[dict(evidence_id="conversation", quote="999")],
            )
        ],
    )
    runtime = runtime_for(ScriptedModel([bad, bad, bad]))
    await runtime.execute(request())
    assert runtime.repository.get("test").status == "FAILED"
    error = records(runtime, kind="run.failed")[0].payload["error"]
    assert error["code"] == "CALCULATION_INPUT" and error["stage"] == "calculator_input"
    assert not records(runtime, kind="message.delta")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", ["length", "missing_field", "incoherent_resolution", "invalid_json"]
)
async def test_irrelevant_retrieval_can_finish_with_clarification_after_one_audit_protocol_repair(
    fault,
):
    import httpx
    from models.llm import HttpModelGateway
    from models.schemas import ModelGenerationConfig

    answer = "本次检索返回的资料与试点无关，尚不足以评估效果。请补充知识库范围、检索耗时基线、真实问题样本、平台能力、成本和数据隔离方案，或确认是否先按明确假设制定方案。"
    missing = [need(f"n{index}") for index in range(1, 7)]
    steps = [
        decision(
            "execute", needs=missing, tools=[intent(key="n1", query="AI知识助手试点")]
        ),
        decision(
            "clarify",
            answer=answer,
            needs=[{**item, "status": "unavailable"} for item in missing],
            assessments=[
                dict(evidence_id=f"E{index}", relevant=False, reason="与试点无关")
                for index in range(1, 4)
            ],
        ),
    ]
    audits = []

    async def search(**kwargs):
        return [
            Evidence(
                id=str(index), chunk_id=index, content=text, source_name="无关文档"
            )
            for index, text in enumerate(
                ["汽车安全事件", "产品召回通知", "通用文化文本"], 1
            )
        ]

    def respond(http_request):
        payload = json.loads(http_request.content)
        if '"approved"' not in payload["messages"][0]["content"]:
            value, finish = steps.pop(0), "stop"
        else:
            audits.append(payload)
            value, finish = (
                dict(
                    approved=True,
                    summary="澄清准确反映本轮缺口，没有捏造试点效果",
                    temporal_checks=[],
                ),
                "stop",
            )
            if len(audits) == 1:
                value = {"approved": True, "summary": "不应发布的不完整复核"}
                if fault == "length":
                    finish = "length"
                elif fault == "incoherent_resolution":
                    value.update(
                        temporal_checks=[],
                        resolution="clarify",
                        clarification_question="",
                    )
        content = json.dumps(value, ensure_ascii=False)
        if audits and len(audits) == 1 and fault == "invalid_json":
            content = '{"approved":true,"summary":'
        frames = [
            {"choices": [{"delta": {"content": content}, "finish_reason": finish}]}
        ]
        return httpx.Response(
            200,
            content="".join("data: " + json.dumps(frame) + "\n\n" for frame in frames)
            + "data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        original = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="test",
            provider="siliconflow",
            generation=ModelGenerationConfig(max_tokens=4096),
        )
        runtime = runtime_for(original, search)
        await runtime.execute(
            request().model_copy(
                update={"goal": "评估AI知识助手试点是否可行并形成方案"}
            )
        )
    run = runtime.repository.get("test")
    assert run.status == "COMPLETED" and run.report["answer"] == answer
    assert run.evidence == [] and len(audits) == 2
    assert 1200 < audits[0]["max_tokens"] < audits[1]["max_tokens"] <= 4096
    assert original.generation.max_tokens == 4096
    assert "同一份原文和草稿" in audits[1]["messages"][-1]["content"]
    assert any(
        event.payload.get("protocolRepair")
        for event in records(runtime, kind="node.updated")
    )
    assert not records(runtime, kind="run.failed")
    assert len(records(runtime, kind="message.delta")) == 1
    assert not run.review_result[
        "approved"
    ]  # Missing facts did not become verified facts.


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["schema", "length"])
async def test_repeated_audit_protocol_failure_stops_after_one_repair_without_publishing(
    fault,
):
    from models.llm import ModelOutputLimitError, ModelProtocolError

    class Model(ScriptedModel):
        async def structured(self, messages, schema, **kwargs):
            if schema is AnswerAudit:
                self.requests.append((schema, messages))
                if fault == "length":
                    raise ModelOutputLimitError("private-provider-output")
                raise ModelProtocolError(
                    "private-provider-output", detail="temporal_checks: missing"
                )
            return await super().structured(messages, schema, **kwargs)

    model = Model(
        [
            decision(
                "clarify", answer="请提供业务样本。", needs=[need(status="unavailable")]
            )
        ]
    )
    runtime = runtime_for(model)
    await runtime.execute(request())
    assert runtime.repository.get("test").status == "FAILED"
    assert [schema for schema, _ in model.requests] == [
        AgentDecision,
        AnswerAudit,
        AnswerAudit,
    ]
    error = records(runtime, kind="run.failed")[0].payload["error"]
    assert error["stage"] == "answer_audit"
    assert error["code"] == (
        "MODEL_OUTPUT_LIMIT" if fault == "length" else "INVALID_RESPONSE"
    )
    assert "private-provider-output" not in str(error)
    assert not records(runtime, kind="message.delta")


@pytest.mark.asyncio
async def test_repaired_audit_can_still_reject_a_draft_and_request_real_clarification():
    from models.llm import ModelProtocolError

    question = "当前没有可核验的耗时基线，不能确认试点效果。请提供测量数据。"

    class Model(ScriptedModel):
        attempts = 0

        async def structured(self, messages, schema, **kwargs):
            if schema is AnswerAudit:
                self.attempts += 1
                if self.attempts == 1:
                    self.requests.append((schema, messages))
                    raise ModelProtocolError(
                        "bad schema", detail="temporal_checks: missing"
                    )
            return await super().structured(messages, schema, **kwargs)

    model = Model(
        [decision(answer="检索耗时已经降低40%。", review_required=True)],
        audits=[
            dict(
                approved=False,
                summary="把目标误写成实测结果",
                issues=["没有耗时基线"],
                resolution="clarify",
                clarification_question=question,
            )
        ],
    )
    runtime = runtime_for(model)
    await runtime.execute(request())
    run = runtime.repository.get("test")
    assert run.status == "COMPLETED" and run.report["answer"] == question
    assert not run.review_result["approved"]
    assert len(model.requests) == 3 and model.attempts == 2
    assert all(
        "已经降低40%" not in event.payload["delta"]
        for event in records(runtime, kind="message.delta")
    )


@pytest.mark.asyncio
async def test_interrupted_audit_stream_is_distinct_from_protocol_errors_and_is_not_replayed():
    import httpx
    from models.llm import HttpModelGateway

    requests = []

    def respond(http_request):
        requests.append(json.loads(http_request.content))
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    decision(
                                        answer="请确认资料。", review_required=True
                                    )
                                )
                            }
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            content='data: {"choices":[{"delta":{"content":"{\\"approved\\":"}}]}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        runtime = runtime_for(
            HttpModelGateway(
                client=client,
                base_url="https://mock.local/v1",
                api_key="test",
                model="test",
            )
        )
        await runtime.execute(request())
    assert len(requests) == 2 and runtime.repository.get("test").status == "FAILED"
    error = records(runtime, kind="run.failed")[0].payload["error"]
    assert (
        error["code"] == "MODEL_STREAM_INTERRUPTED" and error["stage"] == "answer_audit"
    )
    assert not records(runtime, kind="message.delta")


@pytest.mark.parametrize("approved", [True, False])
@pytest.mark.parametrize("explicit_question", [True, False])
@pytest.mark.parametrize("with_correction", [True, False])
def test_clarification_takes_precedence_without_publishing_a_contradictory_approval(
    approved, explicit_question, with_correction
):
    audit = AnswerAudit(
        approved=approved,
        summary="关键条件尚不明确",
        temporal_checks=[],
        resolution="clarify",
        clarification_question="请确认计费单位。" if explicit_question else "",
        unresolved_conditions=[] if explicit_question else ["基础费按人还是按层计费"],
        correction=(
            AnswerRevision(summary="不应直接发布", answer="确定总价为100元")
            if with_correction
            else None
        ),
    )
    assert not audit.approved and audit.correction is None
    assert audit.clarification_question.strip()
    if not explicit_question:
        assert "基础费按人还是按层计费" in audit.clarification_question


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["decision", "compose"])
@pytest.mark.parametrize("final_approval", [True, False])
async def test_unapproved_correction_is_a_proposal_and_requires_a_second_independent_audit(
    entry, final_approval
):
    from agents.decision_engine import DecisionEngine, AgentExecutionError

    corrected = "2 + 2 = 4。"

    class Model(ScriptedModel):
        chat_calls = 0

        async def chat(self, *args, **kwargs):
            self.chat_calls += 1
            return ModelChatResult(content="2 + 2 = 5。", model=self.model)

    model = Model(
        (
            [decision(answer="2 + 2 = 5。", review_required=True)]
            if entry == "decision"
            else []
        ),
        audits=[
            dict(
                approved=False,
                summary="原答复算术错误",
                issues=["2+2不等于5"],
                correction=dict(summary="修正算术", answer=corrected),
            ),
            dict(
                approved=final_approval,
                summary="修正稿已复核" if final_approval else "提案仍未通过独立复核",
                issues=[] if final_approval else ["提案仍未通过独立复核"],
            ),
        ],
    )
    runtime = runtime_for(model)
    req = request().model_copy(update={"goal": "2+2等于几？"})
    if entry == "decision":
        await runtime.execute(req)
        run = runtime.repository.get("test")
        assert run.status == ("COMPLETED" if final_approval else "FAILED")
        if final_approval:
            assert run.report["answer"] == corrected
        else:
            assert (
                records(runtime, kind="run.failed")[0].payload["error"]["code"]
                == "ANSWER_VALIDATION"
            )
            assert not records(runtime, kind="message.delta")
    else:
        engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
        draft = AgentDecision.model_validate(
            decision(answer="2+2=?", review_required=True)
        )
        if final_approval:
            assert (await engine.compose(draft)).answer == corrected
        else:
            with pytest.raises(AgentExecutionError) as error:
                await engine.compose(draft)
            assert error.value.details["code"] == "ANSWER_VALIDATION"
        assert model.chat_calls == 1  # Recheck the proposal without writing it again.
    assert [schema for schema, _ in model.requests].count(AnswerAudit) == 2
    assert AnswerRevision not in [schema for schema, _ in model.requests]
    audits = [
        event.payload
        for event in records(runtime, kind="node.completed")
        if event.payload.get("node") == "REFLECTION"
    ]
    assert (
        not audits[0]["approved"]
        and audits[0]["correctionProposed"]
        and not audits[0]["corrected"]
    )
    assert audits[1]["approved"] == final_approval


@pytest.mark.asyncio
async def test_unapproved_correction_with_a_fabricated_source_cannot_be_reused():
    from agents.decision_engine import DecisionEngine

    model = ScriptedModel(
        [],
        audits=[
            dict(
                approved=False,
                summary="仅提出修正稿",
                correction=dict(
                    summary="无效提案",
                    answer="事实。[E999]",
                    claims=[
                        dict(
                            statement="事实",
                            basis="world",
                            supports=[dict(evidence_id="E999", quote="没有原文")],
                        )
                    ],
                ),
            )
        ],
    )
    runtime = runtime_for(model)
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    issues = await engine.audit(
        AgentDecision.model_validate(decision(answer="原稿", review_required=True))
    )
    assert issues and not engine.audit_result.approved
    assert engine.audited_decision is None and engine.proposed_decision is None
    assert not engine.needs
