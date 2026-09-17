from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Any]
EventSink = Callable[[str | int, str, dict[str, Any]], Awaitable[Any]]
TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "TIMEOUT", "CANCELLED"})


class ToolSpec(BaseModel):
    """The safe, provider-neutral contract exposed to an agent or a chain."""

    name: str
    version: str = "1.0"
    description: str = ""
    permission: Literal["READ", "WRITE"] = "READ"
    timeout_seconds: float = Field(default=10, gt=0, le=120)
    max_concurrency: int = Field(default=4, ge=1, le=64)
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


@dataclass
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler
    semaphore: asyncio.Semaphore
    source: str = "builtin"


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
    call_id: str = ""
    chain_id: str | None = None
    step_id: str | None = None
    attempt: int = 1


@dataclass(slots=True)
class ToolTask:
    call_id: str
    run_id: str
    tool: str
    permission: str
    input_data: dict[str, Any]
    status: str = "QUEUED"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    result: Any = field(default=None, repr=False)
    task: asyncio.Task[Any] | None = field(default=None, repr=False)
    chain_id: str | None = None
    step_id: str | None = None

    def snapshot(self, *, include_result: bool = False) -> dict[str, Any]:
        value: dict[str, Any] = {
            "callId": self.call_id,
            "runId": self.run_id,
            "tool": self.tool,
            "permission": self.permission,
            "inputData": _redact(self.input_data),
            "status": self.status,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "durationMs": self.duration_ms,
            "error": self.error,
        }
        if self.chain_id:
            value["chainId"] = self.chain_id
        if self.step_id:
            value["stepId"] = self.step_id
        if include_result and self.status == "SUCCEEDED":
            value["result"] = _json_safe(self.result)
        return value


@dataclass(frozen=True, slots=True)
class ToolChainStep:
    """A deterministic chain node; dependencies are explicit, never inferred."""

    id: str
    tool: str
    input_data: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    continue_on_error: bool = False


@dataclass(slots=True)
class ToolChainTask:
    chain_id: str
    run_id: str
    steps: list[ToolChainStep]
    status: str = "QUEUED"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    step_results: dict[str, Any] = field(default_factory=dict, repr=False)
    step_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    task: asyncio.Task[Any] | None = field(default=None, repr=False)

    def snapshot(self, *, include_results: bool = False) -> dict[str, Any]:
        value: dict[str, Any] = {
            "chainId": self.chain_id,
            "runId": self.run_id,
            "status": self.status,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "durationMs": self.duration_ms,
            "error": self.error,
            "steps": list(self.step_states.values()),
        }
        if include_results and self.status == "SUCCEEDED":
            value["results"] = {key: _json_safe(result) for key, result in self.step_results.items()}
        return value


class ToolRegistry:
    """Bounded tool execution with sync compatibility, async tasks and DAG chains.

    ``execute`` remains the compatibility API used by agents. ``submit_async``
    and ``submit_chain`` are non-blocking APIs. Every call consumes the same
    per-run budget, uses the registered timeout and is retained as redacted
    audit data.
    """

    def __init__(
        self,
        *,
        max_calls_per_run: int = 50,
        max_concurrent_tasks: int = 32,
        max_retained_tasks: int = 500,
        event_sink: EventSink | None = None,
    ) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._calls: dict[str, int] = {}
        self._disabled_tools: dict[str, set[str]] = {}
        self._history: list[ToolCallRecord] = []
        self._run_limits: dict[str, int] = {}
        self._tasks: dict[str, ToolTask] = {}
        self._chains: dict[str, ToolChainTask] = {}
        self._max_calls_per_run = max(1, min(int(max_calls_per_run), 1_000))
        self._max_concurrent_tasks = max(1, min(int(max_concurrent_tasks), 128))
        self._max_retained_tasks = max(50, min(int(max_retained_tasks), 5_000))
        self._task_slots = asyncio.Semaphore(self._max_concurrent_tasks)
        self._event_sink = event_sink

    def configure_run(
        self,
        run_id: str | int,
        *,
        max_calls: int | None = None,
        disabled_tools: set[str] | list[str] | None = None,
    ) -> None:
        key = str(run_id)
        if max_calls is not None:
            self._run_limits[key] = max(1, min(int(max_calls), self._max_calls_per_run))
        if disabled_tools is not None:
            self._disabled_tools[key] = {str(name) for name in disabled_tools if str(name).strip()}

    def clear_run(self, run_id: str | int) -> None:
        """Cancel outstanding tasks for a run without blocking the caller."""

        key = str(run_id)
        self._run_limits.pop(key, None)
        self._disabled_tools.pop(key, None)
        self._calls.pop(key, None)
        for task in tuple(self._tasks.values()):
            if task.run_id == key and task.task and not task.task.done():
                task.task.cancel()
        for chain in tuple(self._chains.values()):
            if chain.run_id == key and chain.task and not chain.task.done():
                chain.task.cancel()
        self._prune_tasks()

    def register(self, spec: ToolSpec, handler: ToolHandler, *, source: str = "builtin") -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        if not callable(handler):
            raise TypeError(f"Tool handler is not callable: {spec.name}")
        self._tools[spec.name] = RegisteredTool(spec, handler, asyncio.Semaphore(spec.max_concurrency), source)

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def remove_source(self, source: str) -> list[str]:
        """Remove only tools from one provider, used for safe custom reloads."""

        removed = [name for name, registered in self._tools.items() if registered.source == source]
        for name in removed:
            self._tools.pop(name, None)
        return removed

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": registered.spec.name,
                "version": registered.spec.version,
                "description": registered.spec.description,
                "permission": registered.spec.permission,
                "timeoutSeconds": registered.spec.timeout_seconds,
                "maxConcurrency": registered.spec.max_concurrency,
                "requiresConfirmation": registered.spec.requires_confirmation,
                "inputSchema": registered.spec.input_schema,
                "source": registered.source,
            }
            for registered in self._tools.values()
        ]

    def history(self, run_id: str | None = None) -> list[dict[str, Any]]:
        records = [item for item in self._history if run_id is None or item.run_id == str(run_id)]
        return [asdict(item) for item in records]

    def get_task(self, call_id: str, *, include_result: bool = False) -> dict[str, Any] | None:
        task = self._tasks.get(str(call_id))
        return task.snapshot(include_result=include_result) if task else None

    def get_chain(self, chain_id: str, *, include_results: bool = False) -> dict[str, Any] | None:
        chain = self._chains.get(str(chain_id))
        return chain.snapshot(include_results=include_results) if chain else None

    async def execute(
        self,
        name: str,
        *,
        run_id: str,
        input_data: dict[str, Any],
        allow_writes: bool = False,
        confirmed: bool = False,
        call_id: str | None = None,
        chain_id: str | None = None,
        step_id: str | None = None,
        emit_events: bool = False,
    ) -> Any:
        """Execute a tool and wait for its result."""

        registered = self._authorize(name, run_id=run_id, allow_writes=allow_writes, confirmed=confirmed)
        _validate_input(registered.spec, input_data)
        call_key = call_id or _new_id("tool")
        self._reserve_call(run_id)
        return await self._invoke(
            call_key,
            str(run_id),
            registered,
            input_data,
            chain_id=chain_id,
            step_id=step_id,
            emit_events=emit_events,
        )

    async def submit_async(
        self,
        name: str,
        *,
        run_id: str,
        input_data: dict[str, Any],
        allow_writes: bool = False,
        confirmed: bool = False,
        call_id: str | None = None,
        chain_id: str | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """Queue a tool and return immediately with a stable task handle."""

        registered = self._authorize(name, run_id=run_id, allow_writes=allow_writes, confirmed=confirmed)
        call_key = call_id or _new_id("tool")
        if call_key in self._tasks:
            raise ToolCallError(f"Tool call already exists: {call_key}")
        _validate_input(registered.spec, input_data)
        self._reserve_call(run_id)
        task = ToolTask(
            call_id=call_key,
            run_id=str(run_id),
            tool=name,
            permission=registered.spec.permission,
            input_data=dict(input_data),
            chain_id=chain_id,
            step_id=step_id,
        )
        self._tasks[call_key] = task
        await self._emit(task.run_id, "tool.queued", self._event_payload(task, status="QUEUED"))
        task.task = asyncio.create_task(self._run_task(task, registered), name=f"shinkou-tool-{call_key}")
        self._prune_tasks()
        return task.snapshot()

    async def execute_async(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Compatibility alias for callers that name background execution explicitly."""

        return await self.submit_async(name, **kwargs)

    async def wait_task(self, call_id: str, *, timeout: float | None = None) -> dict[str, Any] | None:
        task = self._tasks.get(str(call_id))
        if task is None:
            return None
        if task.task and not task.task.done():
            waiter = asyncio.shield(task.task)
            if timeout is None:
                await waiter
            else:
                await asyncio.wait_for(waiter, timeout=max(0.01, min(float(timeout), 600)))
        return task.snapshot(include_result=True)

    async def cancel_task(self, call_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(str(call_id))
        if task is None:
            return None
        if task.status not in TERMINAL_STATUSES and task.task and not task.task.done():
            task.task.cancel()
            await asyncio.gather(task.task, return_exceptions=True)
        return task.snapshot(include_result=True)

    async def submit_chain(
        self,
        steps: list[ToolChainStep | dict[str, Any]],
        *,
        run_id: str,
        allow_writes: bool = False,
        confirmed: bool = False,
        chain_id: str | None = None,
        max_steps: int = 32,
        timeout_seconds: float = 300,
    ) -> dict[str, Any]:
        """Queue a bounded DAG; independent ready steps execute concurrently."""

        normalized = _normalize_steps(steps, max_steps=max_steps)
        for step in normalized:
            self._authorize(step.tool, run_id=run_id, allow_writes=allow_writes, confirmed=confirmed)
        chain_key = chain_id or _new_id("chain")
        if chain_key in self._chains:
            raise ToolCallError(f"Tool chain already exists: {chain_key}")
        chain = ToolChainTask(chain_id=chain_key, run_id=str(run_id), steps=normalized)
        chain.step_states = {
            step.id: {"id": step.id, "tool": step.tool, "status": "QUEUED", "dependsOn": list(step.depends_on)}
            for step in normalized
        }
        self._chains[chain_key] = chain
        await self._emit(chain.run_id, "chain.queued", self._chain_payload(chain))
        chain.task = asyncio.create_task(
            self._run_chain(chain, allow_writes=allow_writes, confirmed=confirmed, timeout_seconds=timeout_seconds),
            name=f"shinkou-chain-{chain_key}",
        )
        self._prune_tasks()
        return chain.snapshot()

    async def execute_chain(
        self,
        steps: list[ToolChainStep | dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a chain to completion for in-process callers that need its result."""

        accepted = await self.submit_chain(steps, **kwargs)
        result = await self.wait_chain(accepted["chainId"])
        if result is None:
            raise ToolCallError("Tool chain disappeared before completion")
        return result

    async def wait_chain(self, chain_id: str, *, timeout: float | None = None) -> dict[str, Any] | None:
        chain = self._chains.get(str(chain_id))
        if chain is None:
            return None
        if chain.task and not chain.task.done():
            waiter = asyncio.shield(chain.task)
            if timeout is None:
                await waiter
            else:
                await asyncio.wait_for(waiter, timeout=max(0.01, min(float(timeout), 600)))
        return chain.snapshot(include_results=True)

    async def cancel_chain(self, chain_id: str) -> dict[str, Any] | None:
        chain = self._chains.get(str(chain_id))
        if chain is None:
            return None
        if chain.status not in TERMINAL_STATUSES and chain.task and not chain.task.done():
            chain.task.cancel()
            await asyncio.gather(chain.task, return_exceptions=True)
        return chain.snapshot(include_results=True)

    def _authorize(
        self,
        name: str,
        *,
        run_id: str | int | None = None,
        allow_writes: bool,
        confirmed: bool,
    ) -> RegisteredTool:
        registered = self._tools.get(name)
        if registered is None:
            raise ToolCallError(f"Unknown tool: {name}")
        if run_id is not None and name in self._disabled_tools.get(str(run_id), set()):
            raise ToolCallError(f"Tool disabled for run: {name}")
        spec = registered.spec
        if spec.permission == "WRITE" and (not allow_writes or (spec.requires_confirmation and not confirmed)):
            raise ToolCallError(f"Tool requires confirmation: {name}")
        if spec.permission not in {"READ", "WRITE"}:
            raise ToolCallError(f"Unsupported tool permission: {name}")
        return registered

    def _reserve_call(self, run_id: str) -> None:
        key = str(run_id)
        limit = self._run_limits.get(key, self._max_calls_per_run)
        if self._calls.get(key, 0) >= limit:
            raise ToolCallError("Tool call limit exceeded")
        self._calls[key] = self._calls.get(key, 0) + 1

    async def _run_task(self, task: ToolTask, registered: RegisteredTool) -> None:
        task.status = "RUNNING"
        task.started_at = _now()
        try:
            task.result = await self._invoke(
                task.call_id,
                task.run_id,
                registered,
                task.input_data,
                chain_id=task.chain_id,
                step_id=task.step_id,
                emit_events=True,
            )
            task.status = "SUCCEEDED"
        except asyncio.CancelledError:
            task.status = "CANCELLED"
            task.error = "tool task cancelled"
        except ToolCallError as exc:
            task.status = "TIMEOUT" if "timed out" in str(exc).casefold() else "FAILED"
            task.error = str(exc)[:500] or "tool failed"
        except Exception as exc:
            task.status = "FAILED"
            task.error = str(exc)[:500] or "tool failed"
        finally:
            task.finished_at = _now()
            task.duration_ms = _duration_ms(task.started_at, task.finished_at)
            if task.status == "SUCCEEDED":
                return
            event_type = "tool.cancelled" if task.status == "CANCELLED" else "tool.failed"
            await self._emit(task.run_id, event_type, self._event_payload(task, status=task.status))

    async def _invoke(
        self,
        call_id: str,
        run_id: str,
        registered: RegisteredTool,
        input_data: dict[str, Any],
        *,
        chain_id: str | None,
        step_id: str | None,
        emit_events: bool,
    ) -> Any:
        spec = registered.spec
        started = time.perf_counter()
        status = "SUCCEEDED"
        error: str | None = None
        await self._emit(
            run_id,
            "tool.started",
            {
                "callId": call_id,
                "tool": spec.name,
                "status": "RUNNING",
                **({"chainId": chain_id} if chain_id else {}),
                **({"stepId": step_id} if step_id else {}),
            },
            enabled=emit_events,
        )
        try:
            async with self._task_slots, registered.semaphore:
                return await asyncio.wait_for(_call_handler(registered.handler, input_data), timeout=spec.timeout_seconds)
        except asyncio.TimeoutError as exc:
            status = "TIMEOUT"
            error = "tool timed out"
            raise ToolCallError(f"Tool timed out: {spec.name}") from exc
        except asyncio.CancelledError:
            status = "CANCELLED"
            error = "tool task cancelled"
            raise
        except Exception as exc:
            status = "FAILED"
            error = str(exc)[:500] or "tool failed"
            raise
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._history.append(
                ToolCallRecord(
                    run_id=run_id,
                    tool=spec.name,
                    permission=spec.permission,
                    input_data=_redact(input_data),
                    status=status,
                    duration_ms=duration_ms,
                    error=error,
                    call_id=call_id,
                    chain_id=chain_id,
                    step_id=step_id,
                )
            )
            del self._history[:-1000]
            if emit_events:
                if status == "SUCCEEDED":
                    await self._emit(
                        run_id,
                        "tool.completed",
                        {
                            "callId": call_id,
                            "tool": spec.name,
                            "status": status,
                            "durationMs": duration_ms,
                            **({"chainId": chain_id} if chain_id else {}),
                            **({"stepId": step_id} if step_id else {}),
                        },
                    )

    async def _run_chain(self, chain: ToolChainTask, *, allow_writes: bool, confirmed: bool, timeout_seconds: float) -> None:
        chain.status = "RUNNING"
        chain.started_at = _now()
        await self._emit(chain.run_id, "chain.started", self._chain_payload(chain))
        try:
            await asyncio.wait_for(
                self._execute_chain_steps(chain, allow_writes=allow_writes, confirmed=confirmed),
                timeout=max(0.1, min(float(timeout_seconds), 1_800)),
            )
            chain.status = "SUCCEEDED"
        except asyncio.CancelledError:
            chain.status = "CANCELLED"
            chain.error = "tool chain cancelled"
            for state in chain.step_states.values():
                if state["status"] in {"QUEUED", "RUNNING"}:
                    state["status"] = "CANCELLED"
        except Exception as exc:
            chain.status = "FAILED"
            chain.error = str(exc)[:500] or "tool chain failed"
        finally:
            chain.finished_at = _now()
            chain.duration_ms = _duration_ms(chain.started_at, chain.finished_at)
            event_type = {"SUCCEEDED": "chain.completed", "CANCELLED": "chain.cancelled"}.get(chain.status, "chain.failed")
            await self._emit(chain.run_id, event_type, self._chain_payload(chain))

    async def _execute_chain_steps(self, chain: ToolChainTask, *, allow_writes: bool, confirmed: bool) -> None:
        pending = {step.id: step for step in chain.steps}
        while pending:
            ready = [step for step in pending.values() if all(dependency not in pending for dependency in step.depends_on)]
            if not ready:
                raise ToolCallError("Tool chain contains a dependency cycle")
            for step in ready:
                chain.step_states[step.id]["status"] = "RUNNING"
                chain.step_states[step.id]["callId"] = _new_id("tool")
                await self._emit(
                    chain.run_id,
                    "chain.step.started",
                    {"chainId": chain.chain_id, "runId": chain.run_id, "stepId": step.id, "tool": step.tool},
                )
            outcomes = await asyncio.gather(
                *(
                    self.execute(
                        step.tool,
                        run_id=chain.run_id,
                        input_data=_resolve_references(step.input_data, chain.step_results),
                        allow_writes=allow_writes,
                        confirmed=confirmed,
                        call_id=chain.step_states[step.id]["callId"],
                        chain_id=chain.chain_id,
                        step_id=step.id,
                        emit_events=True,
                    )
                    for step in ready
                ),
                return_exceptions=True,
            )
            for step, outcome in zip(ready, outcomes):
                pending.pop(step.id, None)
                state = chain.step_states[step.id]
                if isinstance(outcome, BaseException):
                    state["status"] = "FAILED"
                    state["error"] = str(outcome)[:500] or "step failed"
                    await self._emit(chain.run_id, "chain.step.failed", {"chainId": chain.chain_id, "stepId": step.id, "error": state["error"]})
                    if not step.continue_on_error:
                        raise ToolCallError(f"Tool chain step failed: {step.id}") from outcome
                    continue
                state["status"] = "SUCCEEDED"
                state["resultSummary"] = _summarize(outcome)
                chain.step_results[step.id] = outcome
                await self._emit(
                    chain.run_id,
                    "chain.step.completed",
                    {"chainId": chain.chain_id, "stepId": step.id, "tool": step.tool, "resultSummary": state["resultSummary"]},
                )

    async def _emit(self, run_id: str | int, event_type: str, payload: dict[str, Any], *, enabled: bool = True) -> None:
        if not enabled or self._event_sink is None:
            return
        try:
            await self._event_sink(run_id, event_type, payload)
        except Exception:
            logger.warning("tool event sink failed", extra={"run_id": str(run_id), "event_type": event_type})

    @staticmethod
    def _event_payload(task: ToolTask, *, status: str) -> dict[str, Any]:
        return {
            "callId": task.call_id,
            "runId": task.run_id,
            "tool": task.tool,
            "status": status,
            **({"chainId": task.chain_id} if task.chain_id else {}),
            **({"stepId": task.step_id} if task.step_id else {}),
            **({"durationMs": task.duration_ms} if task.duration_ms is not None else {}),
            **({"error": task.error} if task.error else {}),
        }

    @staticmethod
    def _chain_payload(chain: ToolChainTask) -> dict[str, Any]:
        return {
            "chainId": chain.chain_id,
            "runId": chain.run_id,
            "status": chain.status,
            "steps": list(chain.step_states.values()),
            **({"error": chain.error} if chain.error else {}),
            **({"durationMs": chain.duration_ms} if chain.duration_ms is not None else {}),
        }

    def _prune_tasks(self) -> None:
        if len(self._tasks) <= self._max_retained_tasks and len(self._chains) <= self._max_retained_tasks:
            return
        removable = [key for key, task in self._tasks.items() if task.status in TERMINAL_STATUSES]
        for key in removable[: max(0, len(self._tasks) - self._max_retained_tasks)]:
            self._tasks.pop(key, None)
        removable_chains = [key for key, chain in self._chains.items() if chain.status in TERMINAL_STATUSES]
        for key in removable_chains[: max(0, len(self._chains) - self._max_retained_tasks)]:
            self._chains.pop(key, None)


async def _call_handler(handler: ToolHandler, input_data: dict[str, Any]) -> Any:
    """Run sync handlers off-loop while supporting async callables and wrappers."""

    call = getattr(handler, "__call__", handler)
    if inspect.iscoroutinefunction(handler) or inspect.iscoroutinefunction(call):
        result = handler(**input_data)
    else:
        result = await asyncio.to_thread(handler, **input_data)
    return await result if inspect.isawaitable(result) else result


def _normalize_steps(steps: list[ToolChainStep | dict[str, Any]], *, max_steps: int) -> list[ToolChainStep]:
    if not steps:
        raise ToolCallError("Tool chain must contain at least one step")
    if len(steps) > max(1, min(int(max_steps), 64)):
        raise ToolCallError("Tool chain step limit exceeded")
    result: list[ToolChainStep] = []
    seen: set[str] = set()
    for raw in steps:
        if isinstance(raw, ToolChainStep):
            step = raw
        else:
            step_id = str(raw.get("id") or raw.get("step_id") or "").strip()
            tool = str(raw.get("tool") or "").strip()
            step = ToolChainStep(
                id=step_id,
                tool=tool,
                input_data=dict(raw.get("input_data") or raw.get("inputData") or {}),
                depends_on=tuple(str(item) for item in (raw.get("depends_on") or raw.get("dependsOn") or [])),
                continue_on_error=bool(raw.get("continue_on_error") or raw.get("continueOnError") or False),
            )
        if not step.id or len(step.id) > 64 or not step.tool or len(step.tool) > 200:
            raise ToolCallError("Tool chain step id and tool are required")
        if step.id in seen:
            raise ToolCallError(f"Duplicate tool chain step: {step.id}")
        seen.add(step.id)
        result.append(step)
    unknown = {dependency for step in result for dependency in step.depends_on if dependency not in seen}
    if unknown:
        raise ToolCallError(f"Tool chain dependency not found: {sorted(unknown)[0]}")
    return result


def _resolve_references(value: Any, outputs: dict[str, Any]) -> Any:
    """Resolve only explicit ``$from`` and ``{{steps.*}}`` references."""

    if isinstance(value, dict):
        if set(value) == {"$from"}:
            return _read_path(outputs, str(value["$from"]))
        return {key: _resolve_references(item, outputs) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_references(item, outputs) for item in value]
    if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
        reference = value[2:-2].strip()
        if reference.startswith("steps."):
            return _read_path(outputs, reference[6:])
    return value


def _read_path(outputs: dict[str, Any], path: str) -> Any:
    parts = [part for part in path.split(".") if part]
    if parts and parts[0] == "steps":
        parts = parts[1:]
    if not parts:
        raise ToolCallError("Tool chain reference is empty")
    current: Any = outputs
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, (list, tuple)) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
            continue
        raise ToolCallError(f"Tool chain reference not found: {path}")
    return current


def _summarize(value: Any) -> dict[str, Any]:
    if isinstance(value, (list, tuple, set)):
        return {"type": "list", "count": len(value)}
    if isinstance(value, dict):
        return {"type": "object", "keys": list(value)[:20], "count": len(value)}
    if isinstance(value, str):
        return {"type": "text", "length": len(value)}
    return {"type": type(value).__name__}


def _validate_input(spec: ToolSpec, input_data: dict[str, Any]) -> None:
    """Validate the useful JSON-Schema subset without adding a runtime dependency."""

    schema = spec.input_schema or {}
    if schema.get("type") == "object" and not isinstance(input_data, dict):
        raise ToolCallError(f"Invalid input for tool: {spec.name}")
    for name in schema.get("required", []):
        if name not in input_data or input_data[name] is None:
            raise ToolCallError(f"Missing required input '{name}' for tool: {spec.name}")
    for name, rule in (schema.get("properties") or {}).items():
        if name not in input_data or not isinstance(rule, dict):
            continue
        value = input_data[name]
        expected = rule.get("type")
        valid = {
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "array": isinstance(value, list),
            "object": isinstance(value, dict),
        }.get(expected, True)
        if not valid:
            raise ToolCallError(f"Invalid input '{name}' for tool: {spec.name}")
        if isinstance(value, str) and rule.get("maxLength") is not None and len(value) > int(rule["maxLength"]):
            raise ToolCallError(f"Input '{name}' is too long for tool: {spec.name}")
        if rule.get("enum") is not None and value not in rule["enum"]:
            raise ToolCallError(f"Invalid input '{name}' for tool: {spec.name}")


def _json_safe(value: Any, *, max_chars: int = 20_000) -> Any:
    if isinstance(value, BaseModel):
        return _json_safe(value.model_dump(), max_chars=max_chars)
    if isinstance(value, dict):
        return {str(key): _json_safe(item, max_chars=max_chars) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, max_chars=max_chars) for item in value]
    if isinstance(value, str):
        return value if len(value) <= max_chars else value[:max_chars] + "…"
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)[:max_chars]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if any(token in key.casefold() for token in ("key", "token", "secret", "password", "credential"))
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started: str | None, finished: str | None) -> int | None:
    if not started or not finished:
        return None
    try:
        return max(0, int((datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds() * 1000))
    except ValueError:
        return None
