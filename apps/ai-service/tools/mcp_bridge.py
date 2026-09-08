from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MCPBridgeError(RuntimeError):
    pass


class MCPToolBridge:
    """Small, lifecycle-safe MCP client for remote read tools.

    The bridge deliberately exposes an allow-list and serializes calls through
    one session. This prevents an LLM from discovering or invoking arbitrary
    remote write capabilities by accident.
    """

    def __init__(self, url: str, *, api_key: str | None = None, allowed_tools: set[str] | None = None, timeout_seconds: float = 15) -> None:
        self.url = url
        self.api_key = api_key
        self.allowed_tools = allowed_tools or set()
        self.timeout_seconds = timeout_seconds
        self._session: Any | None = None
        self._stream_context: Any | None = None
        self._session_context: Any | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._session is not None:
            return
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise MCPBridgeError("mcp is required when MCP_URL is configured") from exc
        headers = {"X-Internal-Api-Key": self.api_key} if self.api_key else None
        self._stream_context = streamablehttp_client(self.url, headers=headers)
        read_stream, write_stream, _ = await asyncio.wait_for(self._stream_context.__aenter__(), timeout=self.timeout_seconds)
        self._session_context = ClientSession(read_stream, write_stream)
        self._session = await asyncio.wait_for(self._session_context.__aenter__(), timeout=self.timeout_seconds)
        await asyncio.wait_for(self._session.initialize(), timeout=self.timeout_seconds)

    async def close(self) -> None:
        if self._session_context is not None:
            await self._session_context.__aexit__(None, None, None)
        if self._stream_context is not None:
            await self._stream_context.__aexit__(None, None, None)
        self._session = None
        self._session_context = None
        self._stream_context = None

    async def list_tools(self) -> list[MCPToolDefinition]:
        async with self._lock:
            await self.connect()
            result = await asyncio.wait_for(self._session.list_tools(), timeout=self.timeout_seconds)
            return [
                MCPToolDefinition(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {},
                )
                for tool in result.tools
                if not self.allowed_tools or tool.name in self.allowed_tools
            ]

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if self.allowed_tools and name not in self.allowed_tools:
            raise MCPBridgeError(f"MCP tool is not allow-listed: {name}")
        async with self._lock:
            await self.connect()
            result = await asyncio.wait_for(self._session.call_tool(name, arguments=arguments), timeout=self.timeout_seconds)
            structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
            if structured is not None:
                return structured
            texts = [getattr(block, "text", "") for block in getattr(result, "content", [])]
            payload = "\n".join(text for text in texts if text)
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload


async def register_mcp_tools(registry: Any, bridge: MCPToolBridge) -> list[MCPToolDefinition]:
    """Discover remote tools and register them as read-only local tools."""

    definitions = await bridge.list_tools()
    for definition in definitions:
        if definition.name in {spec.name for spec in registry.specs()}:
            continue

        async def handler(*, _name: str = definition.name, **arguments: Any) -> Any:
            return await bridge.call(_name, arguments)

        from tools.registry import ToolSpec
        registry.register(ToolSpec(name=f"mcp.{definition.name}", permission="READ", timeout_seconds=bridge.timeout_seconds, input_schema=definition.input_schema), handler)
    return definitions
