import json

import httpx
import pytest

from models.llm import HttpModelGateway, LangChainModelGateway
from models.schemas import ModelGenerationConfig, PlanItem


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
