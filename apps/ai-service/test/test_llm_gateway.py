import json
import asyncio

import httpx
import pytest
from pydantic import BaseModel

from models.llm import HttpModelGateway, LangChainModelGateway, ModelLatencyPolicy, ModelTimeoutError, extract_model_context_window, fetch_model_context_window
from models.schemas import ModelGenerationConfig, PlanItem


@pytest.mark.asyncio
async def test_first_response_stall_cancels_then_recovers_once_under_same_deadline():
    class Value(BaseModel):
        title: str
    closed = asyncio.Event()
    calls = []
    class Stalled(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b""
        async def aclose(self):
            closed.set()
    def respond(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx.Response(200, stream=Stalled())
        assert closed.is_set()
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"title":"ok"}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        gateway = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="test",
                                   timeout_seconds=1, latency_policy=ModelLatencyPolicy(0.02, 0.03))
        value, raw = await gateway.structured([{"role": "user", "content": "test"}], Value)
    assert value.title == "ok" and calls[0] == calls[1]
    assert raw.response_stats["attemptCount"] == 2 and raw.response_stats["recoveryCount"] == 1
    assert raw.response_stats["firstResponseMs"] >= 20


@pytest.mark.asyncio
@pytest.mark.parametrize("reasoning", [False, True])
async def test_partial_response_stall_is_not_retried_or_published(reasoning):
    class Value(BaseModel):
        title: str
    calls = []
    class Partial(httpx.AsyncByteStream):
        async def __aiter__(self):
            delta = {"reasoning_content": "private"} if reasoning else {"content": '{"title":'}
            yield ("data: " + json.dumps({"choices": [{"delta": delta}]}) + "\n\n").encode()
            await asyncio.Event().wait()
    def respond(request):
        calls.append(request)
        return httpx.Response(200, stream=Partial())
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        gateway = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="test",
                                   timeout_seconds=1, latency_policy=ModelLatencyPolicy(0.02, 0.03))
        with pytest.raises(ModelTimeoutError) as caught:
            await gateway.structured([{"role": "user", "content": "test"}], Value)
    assert len(calls) == 1 and caught.value.timeout_phase == "response_idle"
    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_request_deadline_does_not_reset_when_first_response_is_retried():
    class Value(BaseModel):
        title: str
    calls = []
    class Stalled(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b""
    def respond(request):
        calls.append(request)
        return httpx.Response(200, stream=Stalled())
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        gateway = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="test",
                                   timeout_seconds=0.25, latency_policy=ModelLatencyPolicy(0.15, 0.15))
        with pytest.raises(ModelTimeoutError) as caught:
            await asyncio.wait_for(gateway.structured([{"role": "user", "content": "test"}], Value), 0.4)
    assert len(calls) == 2 and caught.value.timeout_phase == "request_budget"


@pytest.mark.asyncio
async def test_semantic_audit_uses_json_mode_and_still_requires_temporal_checks():
    from agents.decisions import AnswerAudit
    from models.llm import ModelResponseError
    seen = {}
    def respond(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"approved":true,"summary":"ok"}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        gateway = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="test", provider="siliconflow")
        with pytest.raises(ModelResponseError):
            await gateway.structured([{"role": "user", "content": "test"}], AnswerAudit)
    assert seen["response_format"] == {"type": "json_object"}


def test_siliconflow_auditor_can_use_a_small_explicit_thinking_budget():
    gateway = LangChainModelGateway(base_url="https://mock.local/v1",api_key="test",model="test",provider="siliconflow",
        generation=ModelGenerationConfig(reasoning_effort="low",thinking_budget=256))
    assert gateway._invoke_kwargs(None)["extra_body"]["thinking_budget"] == 256


@pytest.mark.asyncio
async def test_structured_stream_collects_usage_and_preserves_named_title_property():
    class TitledValue(BaseModel):
        title: str
    seen = {}
    def respond(request):
        seen.update(json.loads(request.content))
        rows = [
            {"choices": [{"delta": {"content": '{"title":'}}]},
            {"choices": [{"delta": {"content": '"ok"}'}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16}},
        ]
        return httpx.Response(200, content="".join("data: " + json.dumps(row) + "\n\n" for row in rows) + "data: [DONE]\n\n",
                              headers={"content-type": "text/event-stream"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="demo",
                                 provider="硅基流动", generation=ModelGenerationConfig(reasoning_effort="none"))
        value, result = await model.structured([{"role": "user", "content": "title"}], TitledValue)
    assert value.title == "ok"
    assert result.usage.available and result.usage.total_tokens == 16
    assert '"properties":{"title":' in seen["messages"][0]["content"]
    assert model.response_activity["content_chars"] == len('{"title":"ok"}')
    assert seen["response_format"]["type"] == "json_schema"
    assert seen["response_format"]["json_schema"]["schema"]["required"] == ["title"]
    assert seen["enable_thinking"] is False


@pytest.mark.asyncio
async def test_schema_failure_reports_field_names_without_raw_model_content():
    from models.llm import ModelResponseError
    from agents.decision_engine import public_error
    class Value(BaseModel):
        title: str
    def respond(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"private":"do-not-publish"}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="demo")
        with pytest.raises(ModelResponseError) as caught:
            await model.structured([{"role":"user", "content":"test"}], Value)
    error = public_error(caught.value, "answer_audit")
    assert "title: missing" in error["message"]
    assert "do-not-publish" not in error["message"] and "private" not in error["message"]


@pytest.mark.asyncio
async def test_audit_rule_failure_names_the_missing_question_instead_of_a_root_value_error():
    from agents.decisions import AnswerAudit
    from agents.decision_engine import public_error
    from models.llm import ModelProtocolError
    def respond(request):
        value = dict(approved=False, summary="private-summary-do-not-publish", temporal_checks=[], resolution="clarify")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(value)}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="demo")
        with pytest.raises(ModelProtocolError) as caught:
            await model.structured([{"role": "user", "content": "test"}], AnswerAudit)
    error = public_error(caught.value, "answer_audit")
    assert "clarification_question: 澄清动作需要具体问题或未确认条件" in error["message"]
    assert "value_error" not in error["message"] and "private-summary-do-not-publish" not in error["message"]


@pytest.mark.asyncio
async def test_object_rule_failure_keeps_the_schema_name_without_exposing_validator_text():
    from pydantic import model_validator
    from agents.decision_engine import public_error
    from models.llm import ModelProtocolError
    class Contract(BaseModel):
        value: bool
        @model_validator(mode="after")
        def reject(self):
            raise ValueError("private-validator-text-do-not-publish")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"message": {"content": '{"value":true}'}}]}))) as client:
        model = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="demo")
        with pytest.raises(ModelProtocolError) as caught:
            await model.structured([{"role": "user", "content": "test"}], Contract)
    message = public_error(caught.value,"answer_audit")["message"]
    assert "Contract: value_error" in message and "private-validator-text" not in message


@pytest.mark.asyncio
async def test_complete_structured_json_does_not_wait_for_a_missing_finish_frame():
    class Value(BaseModel):
        title: str
    class HangingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"{\\"title\\":\\"ok\\"}"}}]}\n\n'
            await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=HangingStream()))) as client:
        model = HttpModelGateway(client=client, base_url="https://mock.local/v1", api_key="test", model="demo", timeout_seconds=180)
        value, result = await asyncio.wait_for(model.structured([{"role":"user", "content":"test"}], Value), timeout=4)
    assert value.title == "ok" and not result.usage.available
    assert model.response_activity["json_complete"] is True


def test_extract_model_context_window_supports_openai_compatible_catalogs():
    payload = {
        "data": [
            {"id": "other", "context_length": 8192},
            {"id": "demo-model", "top_provider": {"context_length": 131072}},
        ]
    }

    assert extract_model_context_window(payload, "demo-model") == 131072


@pytest.mark.asyncio
async def test_fetch_model_context_window_does_not_call_chat_completion():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json={"data": [{"id": "demo-model", "max_model_len": 32768}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_model_context_window(
            client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
        )

    assert result["available"] is True
    assert result["contextWindow"] == 32768
    assert paths == ["/v1/models"]


@pytest.mark.asyncio
async def test_langchain_gateway_normalizes_structured_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "req-1",
                "model": "demo-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"id":"Q1","question":"ok","source":"INTERNAL","rationale":"test"}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = LangChainModelGateway(
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
            client=client,
        )
        value, result = await gateway.structured(
            [{"role": "user", "content": "test"}],
            PlanItem,
        )

    assert value.id == "Q1"
    assert result.model == "demo-model"
    assert result.usage.total_tokens == 3


@pytest.mark.asyncio
async def test_http_gateway_sends_advanced_generation_controls():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "demo", "choices": [{"message": {"content": "ok"}}]})

    generation = ModelGenerationConfig(
        temperature=0.7,
        top_p=0.8,
        top_k=40,
        max_tokens=512,
        frequency_penalty=0.2,
        presence_penalty=0.1,
        seed=7,
        stop=["END"],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
            generation=generation,
        )
        await gateway.chat([{"role": "user", "content": "test"}])

    assert seen["temperature"] == 0.7
    assert seen["top_p"] == 0.8
    assert seen["top_k"] == 40
    assert seen["max_tokens"] == 512
    assert seen["seed"] == 7


@pytest.mark.asyncio
async def test_http_gateway_request_generation_override_reaches_provider():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "demo", "choices": [{"message": {"content": "ok"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
        ).with_generation(ModelGenerationConfig(
            temperature=1.1,
            top_p=0.6,
            top_k=17,
            max_tokens=777,
            frequency_penalty=-0.4,
            reasoning_effort="high",
        ))
        await gateway.chat([{"role": "user", "content": "test"}])

    assert seen["temperature"] == 1.1
    assert seen["top_p"] == 0.6
    assert seen["top_k"] == 17
    assert seen["max_tokens"] == 777
    assert seen["frequency_penalty"] == -0.4
    assert seen["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_http_gateway_moves_late_system_messages_to_provider_prefix():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "demo", "choices": [{"message": {"content": "ok"}}]})

    messages = [
        {"role": "system", "content": "base instructions"},
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "system", "content": "attachment context"},
        {"role": "user", "content": "follow-up"},
    ]

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
        )
        await gateway.chat(messages)

    assert [message["role"] for message in seen["messages"]] == ["system", "user", "assistant", "user"]
    assert "当前日期：" in seen["messages"][0]["content"]
    assert seen["messages"][0]["content"].endswith("base instructions\n\nattachment context")
    assert messages[3]["role"] == "system"


@pytest.mark.asyncio
async def test_http_gateway_structured_output_keeps_all_system_messages_at_front():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "demo",
                "choices": [{"message": {"content": '{"id":"Q1","question":"ok","source":"INTERNAL","rationale":"test"}'}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
        )
        value, result = await gateway.structured(
            [
                {"role": "user", "content": "question"},
                {"role": "system", "content": "context added by runtime"},
            ],
            PlanItem,
        )

    assert [message["role"] for message in seen["messages"]] == ["system", "user"]
    assert "你必须只返回一个合法 JSON 对象" in seen["messages"][0]["content"]
    assert "context added by runtime" in seen["messages"][0]["content"]
    assert value.id == "Q1" and result.content.startswith('{"id":"Q1"')
    assert seen["stream"] is True
    assert seen["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize(
    "effort, budget, enabled",
    [("none", None, False), ("low", 1024, True), ("medium", 4096, True), ("high", 16384, True)],
)
def test_siliconflow_gateway_maps_reasoning_effort_to_thinking_budget(effort, budget, enabled):
    gateway = LangChainModelGateway(
        base_url="https://mock.local/v1",
        api_key="test-key",
        model="demo-model",
        provider="siliconflow",
        generation=ModelGenerationConfig(reasoning_effort=effort),
    )

    kwargs = gateway._invoke_kwargs(None)

    assert kwargs["extra_body"]["enable_thinking"] is enabled
    if budget is None:
        assert "thinking_budget" not in kwargs["extra_body"]
    else:
        assert kwargs["extra_body"]["thinking_budget"] == budget
    if effort == "high":
        assert kwargs["reasoning_effort"] == "high"
    else:
        assert "reasoning_effort" not in kwargs


@pytest.mark.parametrize(
    "effort, budget, enabled",
    [("none", None, False), ("low", 1024, True), ("medium", 4096, True), ("high", 16384, True)],
)
@pytest.mark.asyncio
async def test_http_siliconflow_gateway_maps_reasoning_effort_to_thinking_budget(effort, budget, enabled):
    async with httpx.AsyncClient() as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
            provider="siliconflow",
            generation=ModelGenerationConfig(reasoning_effort=effort),
        )

        payload = gateway._build_payload(
            [{"role": "user", "content": "test"}],
            temperature=None,
            stream=False,
        )

    assert payload["enable_thinking"] is enabled
    if budget is None:
        assert "thinking_budget" not in payload
    else:
        assert payload["thinking_budget"] == budget
    if effort == "high":
        assert payload["reasoning_effort"] == "high"
    else:
        assert "reasoning_effort" not in payload


@pytest.mark.asyncio
async def test_http_gateway_streams_openai_compatible_sse_deltas():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        body = (
            'data: {"choices":[{"delta":{"content":"第一段"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"第二段"}}]}\n\n'
            'data: {"usage":{"prompt_tokens":3,"completion_tokens":4,"total_tokens":7}}\n\n'
            'data: [DONE]\n\n'
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
        )
        chunks = [chunk async for chunk in gateway.stream([{"role": "user", "content": "test"}])]

    assert seen["stream"] is True
    assert seen["stream_options"]["include_usage"] is True
    assert [chunk.delta for chunk in chunks if chunk.delta] == ["第一段", "第二段"]
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.total_tokens == 7
    assert chunks[-1].usage.available is True


@pytest.mark.asyncio
async def test_http_gateway_streams_reasoning_content_as_thinking():
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            'data: {"choices":[{"delta":{"reasoning_content":"先分析证据"}}]}\n\n'
            'data: {"choices":[{"delta":{"reasoning_content":"再组织结论"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"最终回答"}}]}\n\n'
            'data: {"usage":{"prompt_tokens":2,"completion_tokens":3,"total_tokens":5}}\n\n'
            'data: [DONE]\n\n'
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = HttpModelGateway(
            client=client,
            base_url="https://mock.local/v1",
            api_key="test-key",
            model="demo-model",
        )
        chunks = [chunk async for chunk in gateway.stream([{"role": "user", "content": "test"}])]

    assert ["".join(c.thinking for c in chunks if c.thinking)] == ["先分析证据再组织结论"]
    assert [c.delta for c in chunks if c.delta] == ["最终回答"]


@pytest.mark.asyncio
async def test_finished_sse_without_done_does_not_wait_for_model_timeout():
    import asyncio
    class OpenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"finished"},"finish_reason":"stop"}]}\n\n'
            await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=OpenStream()))) as client:
        gateway = HttpModelGateway(client=client, base_url="https://model.test/v1", api_key="test", model="test", timeout_seconds=120)
        async def read():
            return [chunk async for chunk in gateway.stream([{"role":"user", "content":"test"}])]
        chunks = await asyncio.wait_for(read(), 3)
        assert "".join(chunk.delta for chunk in chunks) == "finished"
