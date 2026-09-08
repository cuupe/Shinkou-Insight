import pytest

from mcp_server import MCPContext, create_mcp_server
from tools.mcp_bridge import MCPBridgeError, MCPToolBridge
from tools.registry import ToolRegistry, ToolSpec


def test_mcp_bridge_rejects_non_allowlisted_tools():
    bridge = MCPToolBridge("http://localhost:1/mcp", allowed_tools={"search_knowledge"})
    with pytest.raises(MCPBridgeError):
        import asyncio
        asyncio.run(bridge.call("delete_everything", {}))


def test_mcp_server_requires_optional_dependency_only_when_enabled():
    context = MCPContext(retriever=object(), graph_store=object())
    try:
        server = create_mcp_server(context)
    except RuntimeError as exc:
        assert "mcp" in str(exc).lower()
    else:
        assert server is not None


@pytest.mark.asyncio
async def test_tool_registry_keeps_redacted_audit_history():
    registry = ToolRegistry()

    async def handler(**kwargs):
        return {"ok": True}

    registry.register(ToolSpec(name="demo", permission="READ"), handler)
    await registry.execute("demo", run_id="run-1", input_data={"apiKey": "do-not-store"})
    record = registry.history("run-1")[0]
    assert record["status"] == "SUCCEEDED"
    assert record["input_data"]["apiKey"] == "[REDACTED]"
