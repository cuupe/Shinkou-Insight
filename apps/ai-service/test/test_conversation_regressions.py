import json

import httpx
import pytest

from agents.runtime import _compact_chat_context, _web_search_query
from models.llm import HttpModelGateway, ModelStreamChunk, MockModelGateway, ModelResponseError
from models.output_guard import FinalChannelFilter
from models.schemas import ChatMessage, ExecuteRunRequest, ResearchConfig, Evidence, ModelGenerationConfig
from tools.calculator import calculate, conversation_facts
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


@pytest.mark.asyncio
@pytest.mark.parametrize("goal,expected", [
    ("相减呢", "15244"),
    ("计算 x² + 4x - 3y³ + 2y² + xy - 3011245", "-69268819969311821"),
])
async def test_user_arithmetic_examples_use_exact_calculator(goal, expected):
    runtime, repo = make_runtime()
    history = [*HISTORY, *[{"role": "user", "content": f"补充第 {n} 条信息"} for n in range(15)]]
    try:
        await runtime.execute(request(goal, history))
        run = repo.get("regression")
        assert run.status == "COMPLETED", run.error_message
        assert expected in run.report["answer"]
        assert any(e.payload.get("tool") == "calculator" for e in repo.list_events("regression"))
    finally:
        await runtime.close()


def test_explicit_user_facts_win_over_assistant_guesses_and_support_updates():
    facts = conversation_facts([*HISTORY, {"role": "assistant", "content": "x=0, y=0"},
                                {"role": "user", "content": "x=400000"}])
    assert facts["variables"] == {"x": "400000", "y": "284756"}


def test_chinese_variable_references_do_not_require_spaces():
    facts = conversation_facts([HISTORY[0], {"role": "user", "content": "将以上数字表示为x和y。"},
                               {"role": "user", "content": "现在令x=-5"}])
    assert facts["variables"] == {"x": "-5", "y": "284756"}


@pytest.mark.parametrize("expression", ["__import__('os').system('whoami')", "x.__class__", "2**100000000", "[1]*1000", "1/0", "x+2"])
def test_calculator_rejects_executable_or_unbounded_input(expression):
    with pytest.raises((ValueError, SyntaxError, ZeroDivisionError)):
        calculate(expression)


def test_compaction_keeps_system_values_and_current_turn():
    messages = [{"role": "system", "content": "变量 x=300000 y=284756；不要猜值。"},
                *[{"role": "user" if n % 2 == 0 else "assistant", "content": "早期说明" * 200} for n in range(30)],
                {"role": "user", "content": "现在计算最后那个表达式"}]
    compacted, metrics = _compact_chat_context(messages, max_tokens=1500)
    assert "x=300000" in compacted[0]["content"]
    assert compacted[-1]["content"] == messages[-1]["content"]
    assert metrics["finalTokenEstimate"] <= 1500


def test_weather_followups_resolve_through_tool_capability_question():
    req = request("现在呢？", [{"role": "user", "content": "现在南京浦口区天气怎么样？"},
                           {"role": "assistant", "content": "当前未获得可验证数据。"},
                           {"role": "user", "content": "你不是可以联网的吗？"}])
    assert _web_search_query(req) == "现在南京浦口区天气怎么样？"


def sse(*items):
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        text="".join("data: " + json.dumps(item, ensure_ascii=False) + "\n\n" for item in items) + "data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_http_tools_are_visible_executed_and_returned_with_matching_id():
    requests = []
    class Web:
        async def search(self, query, top_k=5):
            return [Evidence(id="weather-1", chunk_id="weather-1", source_type="web", source_name="南京浦口区天气", url="https://weather.test/pukou",
                content="现在南京浦口区天气怎么样？南京浦口区天气观测：晴。", content_kind="fulltext")]
    def handle(req):
        payload = json.loads(req.content)
        requests.append(payload)
        if len(requests) == 1:
            return sse({"choices": [{"delta": {"reasoning_content": "PRIVATE_REASONING", "tool_calls": [
                {"index": 0, "id": "call-weather", "function": {"name": "search_", "arguments": '{"query":'}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "web", "arguments": '"南京浦口区天气"}'}}]}}]})
        assert payload["messages"][-1]["role"] == "tool"
        assert payload["messages"][-1]["tool_call_id"] == "call-weather"
        assert "weather.test/pukou" in payload["messages"][-1]["content"]
        return sse({"choices": [{"delta": {"content": "南京浦口区天气：晴。[weather-1]"}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        model = HttpModelGateway(client=client, base_url="https://model.test/v1", api_key="test", model="test")
        runtime, repo = make_runtime(model, web_search=Web())
        try:
            await runtime.execute(request("现在呢？", [{"role": "user", "content": "现在南京浦口区天气怎么样？"}], allow_web_search=True))
            run = repo.get("regression")
            assert run.status == "COMPLETED", run.error_message
            assert "晴" in run.report["answer"]
            assert len(requests) == 2
            assert "search_web" in [tool["function"]["name"] for tool in requests[0]["tools"]]
            assert "现在南京浦口区天气怎么样" in str(requests[0]["messages"])
            events = repo.list_events("regression")
            assert "PRIVATE_REASONING" not in str([e.payload for e in events])
            assert any(e.event_type == "model.tool_result" and e.payload["returnedAs"] == "tool" for e in events)
            assert any(e.event_type == "model.requested" and "call-weather" in e.payload["toolResultIds"] for e in events)
        finally:
            await runtime.close()


@pytest.mark.asyncio
async def test_disabled_web_tool_is_neither_advertised_nor_executed():
    class Web:
        async def search(self, *args, **kwargs):
            pytest.fail("disabled tool executed")
    class Caller(MockModelGateway):
        supports_tools = True
        def __init__(self): self.calls = 0
        async def stream(self, messages, **kwargs):
            self.calls += 1
            assert all(item["function"]["name"] != "search_web" for item in kwargs["tools"])
            if self.calls == 1:
                yield ModelStreamChunk(tool_calls=[{"id": "forbidden", "type": "function", "function": {"name": "search_web", "arguments": '{"query":"weather"}'}}])
            else:
                assert "未启用" in messages[-1]["content"]
                yield ModelStreamChunk(delta="本轮联网工具未开启。")
    runtime, repo = make_runtime(Caller(), web_search=Web())
    try:
        await runtime.execute(request("你好", allow_web_search=False))
        assert repo.get("regression").status == "COMPLETED"
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_repetition_recovery_uses_current_turn_and_stops_after_one_retry():
    class Repeater(MockModelGateway):
        generation = ModelGenerationConfig()
        def __init__(self): self.messages = []
        def with_generation(self, _): return self
        async def stream(self, messages, **kwargs):
            self.messages.append(messages)
            yield ModelStreamChunk(delta="0" * 200)
    model = Repeater()
    runtime, repo = make_runtime(model)
    try:
        await runtime.execute(request("请回答当前问题", HISTORY))
        assert repo.get("regression").status == "FAILED"
        assert len(model.messages) == 2
        assert all([m for m in msgs if m["role"] == "user"][-1]["content"] == "请回答当前问题" for msgs in model.messages)
        assert not any("000000" in str(e.payload) for e in repo.list_events("regression"))
    finally:
        await runtime.close()


def test_private_delimiters_never_leak_at_any_chunk_boundary():
    text = "<think>PRIVATE</think>最终答案<analysis>HIDDEN</analysis>。"
    for cut in range(1, len(text)):
        channel = FinalChannelFilter()
        assert channel.feed(text[:cut]) + channel.feed(text[cut:]) + channel.feed("", final=True) == "最终答案。"


@pytest.mark.asyncio
async def test_repeated_native_call_reuses_result_and_terminates():
    class Caller(MockModelGateway):
        supports_tools = True
        calls = 0
        async def stream(self, messages, **kwargs):
            self.calls += 1
            yield ModelStreamChunk(tool_calls=[{"id": f"call-{self.calls}", "type": "function",
                "function": {"name": "calculator", "arguments": '{"expression":"12*14"}'}}])
    model = Caller()
    runtime, repo = make_runtime(model)
    try:
        await runtime.execute(request("核对一个结果", tool_max_calls=3))
        assert repo.get("regression").status == "FAILED"
        assert model.calls == 4
        assert sum(e.event_type == "tool.started" and e.payload.get("tool") == "calculator" for e in repo.list_events("regression")) == 1
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_fact_list_request_retrieves_before_answer_even_without_search_keyword():
    queries = []
    class Web:
        async def search(self, query, top_k=5):
            queries.append(query)
            return []
    runtime, repo = make_runtime(web_search=Web())
    try:
        await runtime.execute(request("介绍东方系列所有整数作，每个都要说到。", allow_web_search=True))
        assert queries and all("东方" in query for query in queries)
        events = repo.list_events("regression")
        assert next(i for i, e in enumerate(events) if e.event_type == "tool.started") < next(i for i, e in enumerate(events) if e.event_type == "message.delta")
        assert repo.get("regression").status == "COMPLETED"
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_incomplete_stream_is_not_accepted_as_completed_answer():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200,
            text='data: {"choices":[{"delta":{"content":"半截答案"}}]}\n\n'))) as client:
        model = HttpModelGateway(client=client, base_url="https://model.test/v1", api_key="test", model="test")
        with pytest.raises(ModelResponseError, match="提前结束"):
            _ = [chunk async for chunk in model.stream([{"role": "user", "content": "test"}])]


@pytest.mark.asyncio
async def test_repetition_retry_shares_the_original_tool_budget():
    class Caller(MockModelGateway):
        supports_tools = True
        generation = ModelGenerationConfig()
        calls = 0
        def with_generation(self, _): return self
        async def stream(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                yield ModelStreamChunk(tool_calls=[{"id": "once", "type": "function", "function": {"name": "calculator", "arguments": '{"expression":"12*14"}'}}])
            elif self.calls == 2:
                yield ModelStreamChunk(delta="0" * 200)
            else:
                assert kwargs["tool_choice"] == "none"
                assert messages[-1]["role"] == "tool"
                assert messages[-1]["tool_call_id"] == "once"
                assert "168" in messages[-1]["content"]
                yield ModelStreamChunk(delta="计算结果为 168。")
    model = Caller()
    runtime, repo = make_runtime(model)
    try:
        await runtime.execute(request("请核对结果", tool_max_calls=1))
        assert repo.get("regression").status == "COMPLETED"
        assert model.calls == 3
        assert sum(e.event_type == "model.tool_call" for e in repo.list_events("regression")) == 1
    finally:
        await runtime.close()
