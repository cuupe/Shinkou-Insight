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
