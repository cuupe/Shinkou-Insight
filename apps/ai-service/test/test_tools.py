import asyncio

import pytest

from tools.registry import ToolCallError, ToolChainStep, ToolRegistry, ToolSpec
from tools.loader import load_custom_tools


@pytest.mark.asyncio
async def test_async_tool_has_handle_lifecycle_and_redacted_result():
    events = []

    async def sink(run_id, event_type, payload):
        events.append((str(run_id), event_type, payload))

    async def handler(*, value, api_key):
        await asyncio.sleep(0)
        return {"value": value, "apiKey": api_key}

    registry = ToolRegistry(event_sink=sink)
    registry.register(ToolSpec(name="demo", permission="READ"), handler)

    accepted = await registry.submit_async("demo", run_id="run-1", input_data={"value": 3, "api_key": "secret"})
    assert accepted["status"] == "QUEUED"
    result = await registry.wait_task(accepted["callId"])

    assert result["status"] == "SUCCEEDED"
    assert result["result"]["value"] == 3
    assert result["result"]["apiKey"] == "secret"
    assert [event[1] for event in events] == ["tool.queued", "tool.started", "tool.completed"]
    assert registry.history("run-1")[0]["input_data"]["api_key"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_async_tool_timeout_and_cancel_are_terminal():
    async def sleepy(*, seconds):
        await asyncio.sleep(seconds)
        return "done"

    registry = ToolRegistry()
    registry.register(ToolSpec(name="slow", permission="READ", timeout_seconds=0.02), sleepy)
    timed_out = await registry.submit_async("slow", run_id="timeout", input_data={"seconds": 0.2})
    timeout_result = await registry.wait_task(timed_out["callId"])
    assert timeout_result["status"] == "TIMEOUT"

    registry.register(ToolSpec(name="cancel", permission="READ", timeout_seconds=2), sleepy)
    cancelled = await registry.submit_async("cancel", run_id="cancel", input_data={"seconds": 2})
    await asyncio.sleep(0)
    cancel_result = await registry.cancel_task(cancelled["callId"])
    assert cancel_result["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_tool_chain_passes_explicit_outputs_and_runs_branches():
    calls = []

    async def source(*, value):
        calls.append(f"source-{value}")
        return {"value": value}

    async def branch(*, value):
        await asyncio.sleep(0)
        calls.append(f"branch-{value}")
        return value * 2

    async def combine(*, left, right):
        return left + right

    registry = ToolRegistry()
    registry.register(ToolSpec(name="source", permission="READ"), source)
    registry.register(ToolSpec(name="branch", permission="READ"), branch)
    registry.register(ToolSpec(name="combine", permission="READ"), combine)

    accepted = await registry.submit_chain(
        [
            ToolChainStep(id="source", tool="source", input_data={"value": 2}),
            ToolChainStep(id="left", tool="branch", input_data={"value": {"$from": "source.value"}}, depends_on=("source",)),
            ToolChainStep(id="right", tool="branch", input_data={"value": {"$from": "source.value"}}, depends_on=("source",)),
            ToolChainStep(
                id="combine",
                tool="combine",
                input_data={"left": {"$from": "left"}, "right": {"$from": "right"}},
                depends_on=("left", "right"),
            ),
        ],
        run_id="chain-1",
    )
    result = await registry.wait_chain(accepted["chainId"])

    assert result["status"] == "SUCCEEDED"
    assert result["results"]["combine"] == 8
    assert set(calls) == {"source-2", "branch-2"}
    assert all(step["status"] == "SUCCEEDED" for step in result["steps"])


@pytest.mark.asyncio
async def test_write_tool_requires_explicit_allow_and_confirmation():
    registry = ToolRegistry()

    async def write(**_):
        return "written"

    registry.register(ToolSpec(name="write", permission="WRITE", requires_confirmation=True), write)
    with pytest.raises(ToolCallError):
        await registry.execute("write", run_id="write-1", input_data={}, allow_writes=True)
    assert await registry.execute("write", run_id="write-1", input_data={}, allow_writes=True, confirmed=True) == "written"


@pytest.mark.asyncio
async def test_custom_python_module_is_discovered_and_registered(tmp_path):
    module = tmp_path / "weather.py"
    module.write_text(
        "from tools.custom import custom_tool\n"
        "@custom_tool('custom.echo', input_schema={'type': 'object', 'required': ['value']})\n"
        "def echo(*, value):\n"
        "    return {'value': value}\n",
        encoding="utf-8",
    )
    registry = ToolRegistry()
    report = load_custom_tools(registry, tmp_path)

    assert report.modules == ["weather.py"]
    assert report.tools == ["custom.echo"]
    assert registry.describe()[0]["source"] == "custom"
    assert await registry.execute("custom.echo", run_id="custom-1", input_data={"value": "ok"}) == {"value": "ok"}


def test_custom_module_register_hook_is_scoped_as_custom(tmp_path):
    module = tmp_path / "hook.py"
    module.write_text(
        "from tools.registry import ToolSpec\n"
        "def register_tools(registry):\n"
        "    def ping():\n"
        "        return 'pong'\n"
        "    registry.register(ToolSpec(name='custom.ping'), ping)\n",
        encoding="utf-8",
    )
    registry = ToolRegistry()
    report = load_custom_tools(registry, tmp_path)

    assert report.tools == ["custom.ping"]
    assert registry.describe()[0]["source"] == "custom"
