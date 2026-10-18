import asyncio
import json
import time

import httpx
import pytest
from pydantic import BaseModel

from agents.decision_engine import AgentExecutionError, DecisionEngine, public_error
from agents.decisions import AnswerAudit
from models.llm import HttpModelGateway, ModelLatencyPolicy, ModelTimeoutError
from models.schemas import Evidence
from test_semantic_agent import (
    ScriptedModel,
    decision,
    intent,
    need,
    records,
    request,
    runtime_for,
)


class Value(BaseModel):
    title: str


class DelayedResponse(httpx.AsyncByteStream):
    def __init__(self, pieces, interval=0.08, *, reasoning=False, endless=False):
        self.pieces = pieces
        self.interval = interval
        self.reasoning = reasoning
        self.endless = endless
        self.closed = asyncio.Event()

    async def __aiter__(self):
        for index, piece in enumerate(self.pieces):
            await asyncio.sleep(self.interval)
            choice = {
                "delta": {"reasoning_content" if self.reasoning else "content": piece}
            }
            if index == len(self.pieces) - 1 and not self.endless:
                choice["finish_reason"] = "stop"
            yield ("data: " + json.dumps({"choices": [choice]}) + "\n\n").encode()
        if self.endless:
            while True:
                await asyncio.sleep(self.interval)
                delta = {"reasoning_content" if self.reasoning else "content": "next"}
                yield (
                    "data: " + json.dumps({"choices": [{"delta": delta}]}) + "\n\n"
                ).encode()

    async def aclose(self):
        self.closed.set()


@pytest.mark.asyncio
async def test_slow_active_json_can_finish_in_one_fixed_grace_without_restarting_request():
    calls = []
    body = DelayedResponse(['{"title":', '"slow', ' but valid"}'], interval=0.2)

    def respond(req):
        calls.append(req)
        return httpx.Response(200, stream=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
            timeout_seconds=0.5,
            latency_policy=ModelLatencyPolicy(0.4, 0.4, completion_grace_seconds=1),
        )
        parsed, raw = await asyncio.wait_for(gateway.structured([], Value), 3)
    assert parsed.title == "slow but valid" and len(calls) == 1
    assert raw.latency_ms >= 500 and body.closed.is_set()
    assert gateway.response_activity["response_budget_seconds"] == pytest.approx(1.5)
    assert gateway.response_activity["completion_grace_eligible"]
    assert not raw.usage.available


@pytest.mark.asyncio
async def test_continuous_unfinished_json_cannot_extend_the_fixed_deadline_repeatedly():
    calls = []
    body = DelayedResponse(['{"title":"'], interval=0.03, endless=True)

    def respond(req):
        calls.append(req)
        return httpx.Response(200, stream=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
            timeout_seconds=0.15,
            latency_policy=ModelLatencyPolicy(0.1, 0.1, completion_grace_seconds=0.2),
        )
        started = time.monotonic()
        with pytest.raises(ModelTimeoutError) as caught:
            await asyncio.wait_for(gateway.structured([], Value), 1.5)
    assert caught.value.timeout_phase == "request_budget"
    assert 0.3 <= time.monotonic() - started < 1.5
    assert len(calls) == 1 and body.closed.is_set()
    assert caught.value.response_stats["contentChars"] > 0
    assert caught.value.response_stats["budgetSeconds"] == pytest.approx(0.35)
    error = public_error(caught.value, "decision")
    assert error["code"] == "MODEL_RESPONSE_BUDGET" and "已接收" in error["message"]
    assert '{"title"' not in error["message"] and "检查服务连接" not in error["remedy"]


@pytest.mark.asyncio
async def test_private_reasoning_alone_does_not_qualify_for_completion_grace():
    body = DelayedResponse(
        ["private-do-not-publish"], interval=0.03, reasoning=True, endless=True
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=body))
    ) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
            timeout_seconds=0.15,
            latency_policy=ModelLatencyPolicy(0.1, 0.1, completion_grace_seconds=0.5),
        )
        with pytest.raises(ModelTimeoutError) as caught:
            await gateway.structured([], Value)
    assert caught.value.timeout_phase == "request_budget"
    assert caught.value.response_stats["budgetSeconds"] == pytest.approx(0.15)
    assert (
        not gateway.response_activity.get("completion_grace_eligible")
        and body.closed.is_set()
    )
    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_complete_json_is_not_discarded_when_usage_wait_crosses_deadline():
    class PendingUsage(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.05)
            yield b'data: {"choices":[{"delta":{"content":"{\\"title\\":\\"complete\\"}"}}]}\n\n'
            await asyncio.Event().wait()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, stream=PendingUsage())
        )
    ) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
            timeout_seconds=0.3,
            latency_policy=ModelLatencyPolicy(0.25, 0.5),
        )
        parsed, raw = await gateway.structured([], Value)
    assert parsed.title == "complete" and not raw.usage.available


@pytest.mark.asyncio
async def test_completion_grace_does_not_relax_first_response_or_idle_timeouts():
    class Stalled(httpx.AsyncByteStream):
        def __init__(self, partial):
            self.partial = partial

        async def __aiter__(self):
            if self.partial:
                yield b'data: {"choices":[{"delta":{"content":"{\\"title\\":"}}]}\n\n'
            await asyncio.Event().wait()

    for partial in (False, True):
        calls = []

        def respond(req):
            calls.append(req)
            return httpx.Response(200, stream=Stalled(partial))

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            gateway = HttpModelGateway(
                client=client,
                base_url="https://mock.local/v1",
                api_key="test",
                model="demo",
                timeout_seconds=0.5,
                latency_policy=ModelLatencyPolicy(
                    0.03, 0.03, completion_grace_seconds=0.5
                ),
            )
            with pytest.raises(ModelTimeoutError) as caught:
                await gateway.structured([], Value)
        assert caught.value.timeout_phase == (
            "response_idle" if partial else "first_response"
        )
        assert len(calls) == (1 if partial else 2)


@pytest.mark.asyncio
async def test_research_only_grace_respects_configuration_and_preserves_selected_model():
    async with httpx.AsyncClient() as client:
        selected = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
        )
        runtime = runtime_for(selected)
        req = request().model_copy(update={"agent_message_id": None})
        engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
        assert engine.protocol_model().request_budget_seconds == 300
        assert engine.protocol_model(audit=True).request_budget_seconds == 180
        engine.stage = "answer_revision"
        assert engine.protocol_model().request_budget_seconds == 180
        engine.stage = "decision"
        req.config.decision_timeout_seconds = 550
        assert engine.protocol_model().request_budget_seconds == 600
        req.config.decision_timeout_seconds = 240
        req.config.research_completion_grace_seconds = 0
        assert engine.protocol_model().request_budget_seconds == 240
        req.agent_message_id = "message"
        req.config.research_completion_grace_seconds = 120
        assert engine.protocol_model().request_budget_seconds == 90
        assert selected.timeout_seconds == 60 and selected.latency_policy is None


@pytest.mark.asyncio
async def test_run_deadline_still_cancels_a_response_that_qualified_for_grace():
    body = DelayedResponse(['{"resolved_goal":"'], interval=0.03, endless=True)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=body))
    ) as client:
        selected = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
        )
        runtime = runtime_for(selected)
        req = request(
            decision_timeout_seconds=0.1,
            research_timeout_seconds=0.12,
            research_completion_grace_seconds=0.5,
        ).model_copy(update={"agent_message_id": None})
        engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
        with pytest.raises(AgentExecutionError) as caught:
            await asyncio.wait_for(engine.run_loop(), 1.5)
    assert caught.value.details["code"] == "RUN_TIME_BUDGET"
    assert engine.model_attempts == 1 and body.closed.is_set()
    assert not records(runtime, kind="message.delta")


@pytest.mark.asyncio
async def test_progress_shows_active_completion_budget_while_response_keeps_arriving():
    text = json.dumps(decision(answer="2"))
    pieces = [text[:25], text[25:50], text[50:75], text[75:]]
    body = DelayedResponse(pieces, interval=0.085)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=body))
    ) as client:
        selected = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test",
            model="demo",
        )
        runtime = runtime_for(selected)
        req = request(
            decision_timeout_seconds=0.2, research_completion_grace_seconds=0.6
        ).model_copy(update={"goal": "1+1=?", "agent_message_id": None})
        engine = DecisionEngine(runtime, req, await runtime.accept(req), [])
        engine.model_progress_interval = 0.001
        assert (await engine.run_loop()).answer == "2"
    progress = records(runtime, kind="node.updated")
    assert any(
        e.payload.get("timeoutMs") == 800 and e.payload.get("baseTimeoutMs") == 200
        for e in progress
    )
    assert any("完成宽限" in e.payload.get("detail", "") for e in progress)


@pytest.mark.asyncio
async def test_single_research_body_is_audited_and_saved_as_a_cited_report():
    content = "样本数300，正确276，含税总成本139000元。"
    answer = (
        "## 测量结果\n\n样本数300，正确276。[E1]\n\n## 成本\n\n含税总成本139000元。[E1]"
    )

    async def search(**kwargs):
        return [
            Evidence(
                id="candidate", chunk_id=1, content=content, source_name="试点测量.md"
            )
        ]

    source_need = need("measured", basis="material")
    model = ScriptedModel(
        [
            decision(
                "execute",
                needs=[source_need],
                tools=[intent(key="measured", query="试点测量与成本")],
            ),
            decision(
                answer=answer,
                needs=[{"id": "measured", "status": "covered", "evidence_ids": ["E1"]}],
                claims=[
                    dict(
                        statement=content,
                        basis="material",
                        need_ids=["measured"],
                        supports=[dict(evidence_id="E1", quote=content)],
                    )
                ],
            ),
        ]
    )
    runtime = runtime_for(model, search)
    await runtime.execute(request().model_copy(update={"agent_message_id": None}))
    saved = runtime.repository.get("test")
    assert saved.status == "COMPLETED" and saved.review_result["approved"]
    assert saved.report["evidence_ids"] == ["E1"]
    assert (
        sum(section["content"] == answer for section in saved.report["sections"]) == 1
    )
    audits = [messages for schema, messages in model.requests if schema is AnswerAudit]
    assert (
        len(audits) == 1
        and answer in json.loads(audits[0][-1]["content"].split("\n", 1)[1])["answer"]
    )
    assert [e.payload["delta"] for e in records(runtime, kind="message.delta")] == [
        answer
    ]
