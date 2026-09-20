from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from dataclasses import dataclass, field
from typing import Any

from core.events import EventBus, RunEvent, utc_now
from models.schemas import Evidence

logger = logging.getLogger(__name__)


@dataclass
class RunRecord:
    run_id: str
    workspace_id: int
    project_id: int
    user_id: int
    goal: str
    config: dict[str, Any]
    status: str = "PENDING"
    current_node: str | None = None
    progress: int = 0
    current_step: str = "等待执行"
    error_message: str | None = None
    report: dict[str, Any] | None = None
    evidence: list[Evidence] = field(default_factory=list)
    token_count: int = 0
    prompt_snapshot: dict[str, str] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    plan_version: int = 0
    plan_history: list[dict[str, Any]] = field(default_factory=list)
    paused: bool = False
    review_result: dict[str, Any] | None = None
    queue_task_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


class InMemoryRunRepository:
    """Local adapter used by the service and tests.

    The protocol is intentionally small so the Java/Postgres repository can be
    added without changing any workflow node.
    """

    def __init__(self, events: EventBus) -> None:
        self.events = events
        self._runs: dict[str, RunRecord] = {}
        self._cancelled: set[str] = set()
        self._resume_events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def create(self, run: RunRecord) -> RunRecord:
        async with self._lock:
            existing = self._runs.get(run.run_id)
            if existing:
                return existing
            self._runs[run.run_id] = run
            self._resume_events[run.run_id] = asyncio.Event()
            self._resume_events[run.run_id].set()
            return run

    def get(self, run_id: str | int) -> RunRecord | None:
        return self._runs.get(str(run_id))

    async def update(self, run_id: str | int, **changes: Any) -> RunRecord:
        async with self._lock:
            run = self._runs[str(run_id)]
            for key, value in changes.items():
                setattr(run, key, value)
            run.updated_at = utc_now()
            return run

    async def set_initial_plan(
        self, run_id: str | int, plan: dict[str, Any]
    ) -> RunRecord:
        async with self._lock:
            run = self._runs[str(run_id)]
            if run.plan_version:
                return run
            run.plan = dict(plan)
            run.plan_version = 1
            run.plan_history = [
                {
                    "version": 1,
                    **dict(plan),
                    "source": "planner",
                    "timestamp": utc_now(),
                }
            ]
            run.updated_at = utc_now()
            return run

    async def update_plan(
        self,
        run_id: str | int,
        *,
        mode: str,
        steps: list[dict[str, Any]] | None = None,
        summary: str | None = None,
        expected_version: int | None = None,
    ) -> RunRecord:
        async with self._lock:
            run = self._runs[str(run_id)]
            if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
                raise ValueError("terminal research runs cannot be modified")
            if (
                expected_version is not None
                and int(expected_version) != run.plan_version
            ):
                raise ValueError(
                    f"plan version conflict: expected {expected_version}, current {run.plan_version}"
                )
            normalized = mode.upper()
            if normalized == "PAUSE":
                run.paused = True
                run.status = "PAUSED"
            elif normalized == "RESUME":
                run.paused = False
                if run.status == "PAUSED":
                    run.status = "RUNNING"
                self._resume_events.setdefault(run.run_id, asyncio.Event()).set()
            elif normalized in {"REPLACE", "APPEND"}:
                current = dict(run.plan or {})
                current_steps = list(current.get("steps") or [])
                incoming = list(steps or [])
                if normalized == "REPLACE":
                    current_steps = incoming
                else:
                    by_id = {str(item.get("id")): item for item in current_steps}
                    for item in incoming:
                        by_id[str(item.get("id"))] = item
                    current_steps = list(by_id.values())
                current["steps"] = current_steps
                if summary is not None:
                    current["summary"] = summary
                run.plan = current
                run.plan_version += 1
                run.plan_history = [
                    *run.plan_history,
                    {
                        "version": run.plan_version,
                        **current,
                        "source": "user",
                        "timestamp": utc_now(),
                    },
                ][-20:]
            else:
                raise ValueError("plan mode must be REPLACE, APPEND, PAUSE, or RESUME")
            run.updated_at = utc_now()
            return run

    async def cancel(self, run_id: str | int) -> bool:
        async with self._lock:
            key = str(run_id)
            if key not in self._runs:
                return False
            self._cancelled.add(key)
            self._runs[key].status = "CANCELLING"
            self._runs[key].paused = False
            self._resume_events.setdefault(key, asyncio.Event()).set()
            self._runs[key].updated_at = utc_now()
            return True

    def is_cancelled(self, run_id: str | int) -> bool:
        return str(run_id) in self._cancelled

    async def wait_if_paused(self, run_id: str | int) -> None:
        key = str(run_id)
        while True:
            run = self._runs.get(key)
            if run is None or not run.paused or self.is_cancelled(key):
                return
            event = self._resume_events.setdefault(key, asyncio.Event())
            event.clear()
            run = self._runs.get(key)
            if run is None or not run.paused or self.is_cancelled(key):
                event.set()
                return
            await event.wait()

    async def add_evidence(self, run_id: str | int, evidence: list[Evidence]) -> None:
        async with self._lock:
            run = self._runs[str(run_id)]
            known = {item.id for item in run.evidence}
            run.evidence.extend(item for item in evidence if item.id not in known)
            run.updated_at = utc_now()

    def list_evidence(self, run_id: str | int) -> list[Evidence]:
        run = self._runs.get(str(run_id))
        return list(run.evidence) if run else []

    def list_events(self, run_id: str | int, after_id: int = 0) -> list[RunEvent]:
        return self.events.history(run_id, after_id)


class DurableRunRepository(InMemoryRunRepository):
    """In-memory hot state mirrored to Redis for restart-safe run recovery."""

    def __init__(self, events: EventBus, redis_url: str | None) -> None:
        super().__init__(events)
        self.redis_url = redis_url
        self._redis: Any | None = None

    async def start(self) -> None:
        if not self.redis_url:
            return
        try:
            import redis

            client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=2.5,
            )
            await asyncio.to_thread(client.ping)
            self._redis = client
        except Exception as exc:
            logger.warning(
                "Durable run snapshots unavailable; using memory only: %s", exc
            )
            self._redis = None

    def _key(self, run_id: str | int) -> str:
        return f"shinkou-insight:runs:{str(run_id)}"

    @staticmethod
    def _serialize(run: RunRecord) -> dict[str, Any]:
        payload = asdict(run)
        payload["evidence"] = [item.model_dump(mode="json") for item in run.evidence]
        return payload

    @staticmethod
    def _deserialize(payload: str | dict[str, Any]) -> RunRecord:
        raw = json.loads(payload) if isinstance(payload, str) else payload
        raw["evidence"] = [
            Evidence.model_validate(item) for item in raw.get("evidence") or []
        ]
        return RunRecord(**raw)

    async def _persist(self, run: RunRecord) -> None:
        if self._redis is not None:
            try:
                await asyncio.to_thread(
                    self._redis.set,
                    self._key(run.run_id),
                    json.dumps(
                        self._serialize(run), ensure_ascii=False, separators=(",", ":")
                    ),
                    ex=60 * 60 * 24 * 30,
                )
            except Exception as exc:
                logger.debug("run snapshot write failed: %s", exc)

    def get(self, run_id: str | int) -> RunRecord | None:
        key = str(run_id)
        local = super().get(key)
        if local is not None or self._redis is None:
            return local
        try:
            raw = self._redis.get(self._key(key))
            if raw is None:
                return None
            run = self._deserialize(raw)
            self._runs[key] = run
            event = self._resume_events.setdefault(key, asyncio.Event())
            if run.paused:
                event.clear()
            else:
                event.set()
            return run
        except Exception as exc:
            logger.debug("run snapshot read failed: %s", exc)
            return None

    async def create(self, run: RunRecord) -> RunRecord:
        existing = self.get(run.run_id)
        if existing is not None:
            return existing
        result = await super().create(run)
        await self._persist(result)
        return result

    async def update(self, run_id: str | int, **changes: Any) -> RunRecord:
        result = await super().update(run_id, **changes)
        await self._persist(result)
        return result

    async def set_initial_plan(
        self, run_id: str | int, plan: dict[str, Any]
    ) -> RunRecord:
        result = await super().set_initial_plan(run_id, plan)
        await self._persist(result)
        return result

    async def update_plan(self, run_id: str | int, **changes: Any) -> RunRecord:
        result = await super().update_plan(run_id, **changes)
        await self._persist(result)
        return result

    async def cancel(self, run_id: str | int) -> bool:
        result = await super().cancel(run_id)
        if result and self.get(run_id) is not None:
            await self._persist(self.get(run_id))
        return result

    async def add_evidence(self, run_id: str | int, evidence: list[Evidence]) -> None:
        await super().add_evidence(run_id, evidence)
        run = self.get(run_id)
        if run is not None:
            await self._persist(run)

    def is_cancelled(self, run_id: str | int) -> bool:
        if super().is_cancelled(run_id):
            return True
        run = self.get(run_id)
        return bool(run and run.status == "CANCELLING")

    async def close(self) -> None:
        if self._redis is not None:
            await asyncio.to_thread(self._redis.close)
            self._redis = None
