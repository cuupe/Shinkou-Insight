import json
from datetime import date

import pytest

from agents.decision_engine import DecisionEngine
from agents.decisions import AgentDecision, AnswerAudit
from models.schemas import Evidence
from models.llm import ModelTimeoutError
from test_semantic_agent import (
    ScriptedModel,
    decision,
    need,
    intent,
    records,
    request,
    runtime_for,
)

DATES = (
    "给定起止日期为2026-08-31至2026-10-11，首尾日计入，上限6周；没有提供实际执行记录。"
)


def report(*ids, context=()):
    return dict(
        title="输入条件说明",
        executive_summary="仅根据给定输入计算，实际执行尚未核验。",
        sections=[
            dict(heading="周期", content="按给定日期计算，不作为实际执行证明。[U1]")
        ],
        evidence_ids=list(ids),
        context_source_ids=list(context),
    )


@pytest.mark.asyncio
async def test_known_user_and_project_ids_are_partitioned_from_document_citations():
    runtime = runtime_for(ScriptedModel([]))
    req = request().model_copy(update={"goal": DATES})
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    engine.evidence["E1"] = Evidence(
        id="E1", chunk_id=1, content="原始测量", source_name="测量.md"
    )
    draft = AgentDecision.model_validate(
        decision(
            answer="仅按输入条件计算。", report=report("E1", "U1", "project.id", "U1")
        )
    )
    assert engine.final_issues(draft) == []
    assert draft.report.evidence_ids == ["E1"]
    assert draft.report.context_source_ids == ["U1", "project.id"]
    # Repeated validation must not lose or duplicate sources.
    assert engine.final_issues(draft) == []
    assert draft.report.context_source_ids == ["U1", "project.id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["evidence_ids", "context_source_ids"])
async def test_unknown_user_ids_are_never_accepted_as_registered_input_sources(field):
    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    body = report()
    body[field] = ["U999"]
    draft = AgentDecision.model_validate(
        decision(answer="不能伪造输入编号", report=body)
    )
    assert any("U999" in issue for issue in engine.final_issues(draft))
    assert engine.report_context_sources(draft) == []


@pytest.mark.asyncio
async def test_conditional_date_comparison_can_use_user_input_without_claiming_measured_acceptance():
    assert (date(2026, 10, 11) - date(2026, 8, 31)).days + 1 == 42
    answer = "按用户给定起止日并计入首尾，区间为42天即6周，满足给定的6周上限；是否实际按该日期执行尚未核验。[U1]"
    draft = decision(
        answer=answer,
        report=report("U1"),
        needs=[
            need(
                "input-period",
                source="internal",
                basis="context",
                status="covered",
                evidence_ids=["U1"],
            )
        ],
        claims=[
            dict(
                statement=answer,
                kind="conditional",
                basis="derived",
                need_ids=["input-period"],
                assumptions=["日期是输入条件；起止日都计入；实际执行未得到证明"],
                supports=[dict(evidence_id="U1", quote=DATES)],
            )
        ],
    )
    model = ScriptedModel(
        [draft],
        audits=[dict(approved=True, summary="条件计算正确，没有宣称独立验收通过")],
    )
    runtime = runtime_for(model)
    await runtime.execute(
        request().model_copy(update={"goal": DATES, "agent_message_id": None})
    )
    saved = runtime.repository.get("test")
    assert saved.status == "COMPLETED"
    assert not records(runtime, kind="tool.started")
    assert saved.report["evidence_ids"] == []
    assert saved.report["context_source_ids"] == ["U1"]
    assert saved.report["context_sources"][0]["kind"] == "user_input"
    assert saved.report["context_sources"][0]["quotes"] == [DATES]
    assert any(
        "不计入知识库引用数量" in section["content"]
        for section in saved.report["sections"]
    )
    audit_request = next(
        messages for schema, messages in model.requests if schema is AnswerAudit
    )
    state = json.loads(audit_request[-1]["content"].split("\n", 1)[1])
    assert state["report"]["evidence_ids"] == [] and state["report"][
        "context_source_ids"
    ] == ["U1"]
    assert {source["id"] for source in state["trustedUserSources"]} == {"U1"}


@pytest.mark.asyncio
async def test_user_inputs_cannot_prove_current_external_world_facts():
    text = "示例甲仍然在任。"
    runtime = runtime_for(ScriptedModel([]))
    req = request().model_copy(update={"goal": text})
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    draft = AgentDecision.model_validate(
        decision(
            answer=text,
            needs=[
                need(
                    "office",
                    source="web",
                    basis="world",
                    temporal="current",
                    status="covered",
                    evidence_ids=["U1"],
                )
            ],
            claims=[
                dict(
                    statement=text,
                    basis="world",
                    need_ids=["office"],
                    supports=[dict(evidence_id="U1", quote=text)],
                )
            ],
        )
    )
    engine.apply_decision(draft)
    assert any("时效支持" in issue for issue in engine.final_issues(draft))


@pytest.mark.asyncio
@pytest.mark.parametrize("search_mode", ["empty", "error", "irrelevant"])
async def test_repeated_rejection_after_empty_search_becomes_missing_material_not_false_acceptance(
    search_mode,
):
    async def search(**kwargs):
        if search_mode == "error":
            raise ModelTimeoutError("provider timeout")
        if search_mode == "irrelevant":
            return [
                Evidence(
                    id="x", chunk_id=1, content="汽车召回记录", source_name="不相关.md"
                )
            ]
        return []

    missing = need("actual-period", source="internal", basis="material")
    proposal = dict(
        summary="仅给定输入，但仍需核验",
        answer="按输入日期形式上符合6周，实际执行尚未核验。",
    )
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[missing],
                tools=[intent(key="actual-period", query="星桥试点执行周期测量记录")],
            ),
            decision(
                answer="试点周期已经达标。",
                needs=[{**missing, "status": "unavailable"}],
            ),
        ],
        audits=[
            dict(
                approved=False,
                summary="实际执行缺少依据",
                issues=["没有实际执行记录"],
                correction=proposal,
            ),
            dict(
                approved=False,
                summary="仍缺实际执行证据",
                issues=["周期只有输入，不能判定验收通过；U1不能冒充知识库来源"],
            ),
        ],
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request().model_copy(update={"goal": DATES}))
    saved = runtime.repository.get("test")
    assert [schema for schema, _ in model.requests].count(AnswerAudit) == 2
    if search_mode == "empty":
        assert saved.status == "COMPLETED" and not saved.review_result["approved"]
        assert "本轮已完成 1 次项目知识库检索" in saved.report["answer"]
        assert "请先在当前项目的“知识库”上传对应资料" in saved.report["answer"]
        assert (
            "周期已经达标" not in saved.report["answer"]
            and "[U1]" not in saved.report["answer"]
        )
        assert not records(runtime, kind="run.failed")
        completion = records(runtime, kind="run.completed")[0].payload
        assert completion["decisionMetrics"]["stopReason"] == "clarification"
        assert not completion["reviewResult"]["approved"]
    else:
        assert saved.status == "FAILED"
        assert not records(runtime, kind="message.delta")
        if search_mode == "error":
            assert records(runtime, kind="tool.failed")


@pytest.mark.asyncio
async def test_no_search_cannot_turn_an_unsupported_answer_into_empty_library_clarification():
    runtime = runtime_for(ScriptedModel([]))
    req = request()
    engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
    draft = AgentDecision.model_validate(
        decision(answer="未经支持的结论", needs=[need(status="unavailable")])
    )
    engine.apply_decision(draft)
    assert await engine.clarify_empty_retrieval(draft) is None


@pytest.mark.asyncio
async def test_protocol_failure_after_empty_search_is_not_hidden_by_missing_material_fallback():
    from models.llm import ModelProtocolError

    class Model(ScriptedModel):
        async def structured(self, messages, schema, **kwargs):
            if schema is AnswerAudit:
                raise ModelProtocolError(
                    "bad output", detail="temporal_checks: missing"
                )
            return await super().structured(messages, schema, **kwargs)

    async def search(**kwargs):
        return []

    model = Model(
        [
            decision("execute", needs=[need()], tools=[intent(query="内部依据")]),
            decision(answer="尚未取得资料", needs=[need(status="unavailable")]),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request())
    assert runtime.repository.get("test").status == "FAILED"
    assert (
        records(runtime, kind="run.failed")[0].payload["error"]["code"]
        == "INVALID_RESPONSE"
    )
    assert not records(runtime, kind="message.delta")
