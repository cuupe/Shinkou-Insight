import json

import httpx
import pytest

from agents.runtime import _compact_chat_context
from models.llm import HttpModelGateway, ModelStreamChunk, MockModelGateway, ModelResponseError
from models.output_guard import FinalChannelFilter, GenerationGuard, GenerationAborted
from models.schemas import ChatMessage, ExecuteRunRequest, ResearchConfig, Evidence, ModelGenerationConfig
from tools.calculator import calculate
from test_agent_runtime import make_runtime

def request(goal, history=(), **config):
    return ExecuteRunRequest(run_id="regression", agent_message_id="answer-current", workspace_id=1, project_id=1,
        goal=goal, context_messages=[ChatMessage.model_validate(m) for m in history],
        config=ResearchConfig(multi_agent_mode="OFF", reflection_enabled=False, **config))

HISTORY = [
    {"role": "user", "content": "三十万加二十八万四千七百五十六等于多少"},
    {"role": "assistant", "content": "584756"},
    {"role": "user", "content": "以上两个数字分别作为 x 和 y。"},
    {"role": "assistant", "content": "x=300000, y=284756"},
]

@pytest.mark.parametrize("expression", ["__import__('os').system('whoami')", "x.__class__", "2**100000000", "[1]*1000", "1/0", "x+2"])
def test_calculator_rejects_executable_or_unbounded_input(expression):
    with pytest.raises((ValueError, SyntaxError, ZeroDivisionError)):
        calculate(expression)


def test_calculator_preserves_multi_letter_variable_tokens():
    result = calculate("first_floor + second_floor + fourth_floor", {
        "first_floor": "1307", "second_floor": "3179", "fourth_floor": "6874",
    })
    assert result["result"] == "11360"
    assert result["expression"] == "first_floor + second_floor + fourth_floor"
    assert calculate("2 * unit_price", {"unit_price": "37"})["result"] == "74"
    with pytest.raises(SyntaxError):
        calculate("2unit_price", {"unit_price": "37"})

def test_compaction_keeps_system_values_and_current_turn():
    messages = [{"role": "system", "content": "变量 x=300000 y=284756；不要猜值。"},
                *[{"role": "user" if n % 2 == 0 else "assistant", "content": "早期说明" * 200} for n in range(30)],
                {"role": "user", "content": "现在计算最后那个表达式"}]
    compacted, metrics = _compact_chat_context(messages, max_tokens=1500)
    assert "x=300000" in compacted[0]["content"]
    assert compacted[-1]["content"] == messages[-1]["content"]
    assert metrics["finalTokenEstimate"] <= 1500

def sse(*items):
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        text="".join("data: " + json.dumps(item, ensure_ascii=False) + "\n\n" for item in items) + "data: [DONE]\n\n")

def test_private_delimiters_never_leak_at_any_chunk_boundary():
    text = "<think>PRIVATE</think>最终答案<analysis>HIDDEN</analysis>。"
    for cut in range(1, len(text)):
        channel = FinalChannelFilter()
        assert channel.feed(text[:cut]) + channel.feed(text[cut:]) + channel.feed("", final=True) == "最终答案。"


def test_json_field_and_quote_repetition_is_not_mistaken_for_runaway_generation():
    text = json.dumps({"needs": [{"id": "hotel-floor-pricing", "description": "base and extra pricing per floor", "status": "covered"}] * 8})
    guard = GenerationGuard(structured=True)
    guard.feed(text)
    with pytest.raises(GenerationAborted):
        GenerationGuard().feed("0" * 200)
    with pytest.raises(GenerationAborted):
        GenerationGuard(max_chars=10, structured=True).feed(text)

@pytest.mark.asyncio
async def test_incomplete_stream_is_not_accepted_as_completed_answer():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200,
            text='data: {"choices":[{"delta":{"content":"半截答案"}}]}\n\n'))) as client:
        model = HttpModelGateway(client=client, base_url="https://model.test/v1", api_key="test", model="test")
        with pytest.raises(ModelResponseError, match="提前结束"):
            _ = [chunk async for chunk in model.stream([{"role": "user", "content": "test"}])]
