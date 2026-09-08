from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    version: str = "1.0"
    permission: Literal["READ", "WRITE"]
    timeout_seconds: float = Field(default=10, gt=0, le=120)
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


@dataclass
class RegisteredTool:
    spec: ToolSpec
    handler: Callable[..., Awaitable[Any]]


class ToolCallError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    run_id: str
    tool: str
    permission: str
    input_data: dict[str, Any]
    status: str
    duration_ms: int
    error: str | None = None


class ToolRegistry:
    def __init__(self, *, max_calls_per_run: int = 50) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._calls: dict[str, int] = {}
        self._history: list[ToolCallRecord] = []
        self._max_calls_per_run = max_calls_per_run
        self._run_limits: dict[str, int] = {}

    def configure_run(self, run_id: str | int, *, max_calls: int | None = None) -> None:
        if max_calls is not None:
            self._run_limits[str(run_id)] = max(1, min(int(max_calls), 50))

    def clear_run(self, run_id: str | int) -> None:
        key = str(run_id)
        self._run_limits.pop(key, None)
        self._calls.pop(key, None)

    def register(self, spec: ToolSpec, handler: Callable[..., Awaitable[Any]]) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = RegisteredTool(spec, handler)

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def history(self, run_id: str | None = None) -> list[dict[str, Any]]:
        records = [item for item in self._history if run_id is None or item.run_id == str(run_id)]
        return [asdict(item) for item in records]

    async def execute(self, name: str, *, run_id: str, input_data: dict[str, Any], allow_writes: bool = False) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolCallError(f"Unknown tool: {name}")
        if tool.spec.permission == "WRITE" and (tool.spec.requires_confirmation or not allow_writes):
            raise ToolCallError(f"Tool requires confirmation: {name}")
        key = str(run_id)
        limit = self._run_limits.get(key, self._max_calls_per_run)
        if self._calls.get(key, 0) >= limit:
            raise ToolCallError("Tool call limit exceeded")
        self._calls[key] = self._calls.get(key, 0) + 1
        started = time.perf_counter()
        status = "SUCCEEDED"
        error: str | None = None
        try:
            return await asyncio.wait_for(tool.handler(**input_data), timeout=tool.spec.timeout_seconds)
        except asyncio.TimeoutError as exc:
            status = "TIMEOUT"
            error = str(exc) or "tool timed out"
            raise ToolCallError(f"Tool timed out: {name}") from exc
        except Exception as exc:
            status = "FAILED"
            error = str(exc)[:500]
            raise
        finally:
            self._history.append(ToolCallRecord(run_id=str(run_id), tool=name, permission=tool.spec.permission, input_data=_redact(input_data), status=status, duration_ms=int((time.perf_counter() - started) * 1000), error=error))
            del self._history[:-1000]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if any(token in key.casefold() for token in ("key", "token", "secret", "password")) else _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
