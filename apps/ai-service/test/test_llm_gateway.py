import json

import httpx
import pytest

from models.llm import HttpModelGateway, LangChainModelGateway, extract_model_context_window, fetch_model_context_window
from models.schemas import ModelGenerationConfig, PlanItem


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
    assert seen["messages"][0]["content"] == "base instructions\n\nattachment context"
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
        await gateway.structured(
            [
                {"role": "user", "content": "question"},
                {"role": "system", "content": "context added by runtime"},
            ],
            PlanItem,
        )

    assert [message["role"] for message in seen["messages"]] == ["system", "user"]
    assert seen["messages"][0]["content"].startswith("你必须只返回一个合法 JSON 对象")
    assert "context added by runtime" in seen["messages"][0]["content"]


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
