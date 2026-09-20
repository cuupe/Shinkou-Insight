from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from models.schemas import ExecuteRunRequest

logger = logging.getLogger(__name__)
TaskHandler = Callable[[ExecuteRunRequest], Awaitable[None]]


class ResearchTaskQueue:
    """Redis Streams queue with consumer-group recovery and local fallback."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        redis_url: str | None = None,
        stream: str = "shinkou:research-tasks",
        group: str = "ai-service",
        max_retries: int = 3,
        concurrency: int = 8,
    ) -> None:
        self.enabled = enabled
        self.redis_url = redis_url
        self.stream = stream
        self.group = group
        self.max_retries = max_retries
        self.concurrency = max(1, min(int(concurrency), 64))
        self.consumer = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.backend = "disabled" if not enabled else "memory"
        self._redis: Any | None = None
        self._memory: asyncio.Queue[tuple[ExecuteRunRequest, int]] = asyncio.Queue()
        self._handler: TaskHandler | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._stop = asyncio.Event()
        self._enqueued = 0
        self._completed = 0
        self._failed = 0
        self._retried = 0
        self._processing = 0
        self._last_error: str | None = None

    @classmethod
    async def create(cls, **kwargs: Any) -> "ResearchTaskQueue":
        queue = cls(**kwargs)
        await queue.start()
        return queue

    async def start(self) -> None:
        if not self.enabled or not self.redis_url:
            return
        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=5,
            )
            await self._redis.ping()
            try:
                await self._redis.xgroup_create(
                    self.stream, self.group, id="0", mkstream=True
                )
            except Exception as exc:
                if "BUSYGROUP" not in str(exc).upper():
                    raise
            self.backend = "redis-stream"
        except Exception as exc:
            self._last_error = str(exc)[:500]
            logger.warning(
                "Redis task queue unavailable; using in-process fallback: %s", exc
            )
            if self._redis is not None:
                await self._redis.aclose()
            self._redis = None
            self.backend = "memory"

    async def enqueue(self, request: ExecuteRunRequest) -> str:
        if not self.enabled:
            raise RuntimeError("task queue is disabled")
        payload = request.model_dump(mode="json")
        if self._redis is not None:
            task_id = await self._redis.xadd(
                self.stream,
                {
                    "payload": json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":")
                    ),
                    "attempt": "0",
                    "enqueuedAt": str(time.time()),
                },
                maxlen=10_000,
                approximate=True,
            )
        else:
            task_id = f"memory-{uuid.uuid4().hex}"
            await self._memory.put((request, 0))
        self._enqueued += 1
        return str(task_id)

    async def run_worker(self, handler: TaskHandler) -> None:
        self._handler = handler
        self._stop.clear()
        self._workers = [worker for worker in self._workers if not worker.done()]
        missing = self.concurrency - len(self._workers)
        for _ in range(missing):
            worker_index = len(self._workers)
            self._workers.append(
                asyncio.create_task(
                    self._worker_loop(worker_index),
                    name=f"research-task-worker-{worker_index + 1}",
                )
            )

    async def _worker_loop(self, worker_index: int) -> None:
        consumer = f"{self.consumer}-{worker_index + 1}"
        while not self._stop.is_set():
            try:
                item = await self._next(consumer)
                if item is None:
                    continue
                request, message_id, attempt = item
                self._processing += 1
                acknowledge = True
                heartbeat = (
                    asyncio.create_task(
                        self._heartbeat(consumer, message_id),
                        name=f"research-task-heartbeat-{worker_index + 1}",
                    )
                    if self._redis is not None and message_id
                    else None
                )
                try:
                    if self._handler is None:
                        raise RuntimeError("task queue handler is not configured")
                    await self._handler(request)
                except asyncio.CancelledError:
                    acknowledge = False
                    raise
                except Exception as exc:
                    self._failed += 1
                    self._last_error = str(exc)[:500]
                    if attempt < self.max_retries:
                        self._retried += 1
                        try:
                            await self._retry(request, attempt + 1)
                        except Exception:
                            acknowledge = False
                            raise
                    logger.warning(
                        "research task failed (attempt %s): %s", attempt + 1, exc
                    )
                else:
                    self._completed += 1
                finally:
                    if heartbeat is not None:
                        heartbeat.cancel()
                        await asyncio.gather(heartbeat, return_exceptions=True)
                    self._processing = max(0, self._processing - 1)
                    if acknowledge:
                        await self._ack(message_id)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self._last_error = str(exc)[:500]
                logger.warning("research task worker iteration failed: %s", exc)
                await asyncio.sleep(1)

    async def _heartbeat(self, consumer: str, message_id: str) -> None:
        """Keep a long-running Redis task owned by its active worker.

        Without this lease refresh, XAUTOCLAIM can hand a still-running LLM
        request to another worker after the short recovery timeout. That makes
        one run execute several times and interleaves its stream deltas.
        """

        try:
            while not self._stop.is_set() and self._redis is not None:
                await asyncio.sleep(10)
                if self._redis is None or self._stop.is_set():
                    return
                await self._redis.xclaim(
                    self.stream,
                    self.group,
                    consumer,
                    min_idle_time=0,
                    message_ids=[message_id],
                    justid=True,
                )
                self._last_error = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # A transient heartbeat failure should not abort the user task;
            # the worker still acknowledges it when the handler completes.
            self._last_error = str(exc)[:500]
            logger.warning("research task heartbeat failed: %s", exc)

    async def _next(self, consumer: str) -> tuple[ExecuteRunRequest, str, int] | None:
        if self._redis is None:
            try:
                request, attempt = await asyncio.wait_for(
                    self._memory.get(), timeout=0.5
                )
            except asyncio.TimeoutError:
                return None
            return request, "", attempt
        # First reclaim work left pending by a crashed worker, then read new
        # entries. XAUTOCLAIM is supported by Redis 6.2+.
        try:
            claimed = await self._redis.xautoclaim(
                self.stream,
                self.group,
                consumer,
                min_idle_time=30_000,
                start_id="0-0",
                count=1,
            )
            messages = claimed[1] if len(claimed) > 1 else []
            if messages:
                return self._decode_message(messages[0])
        except Exception:
            pass
        rows = await self._redis.xreadgroup(
            self.group, consumer, streams={self.stream: ">"}, count=1, block=500
        )
        self._last_error = None
        if not rows:
            return None
        return self._decode_message(rows[0][1][0])

    def _decode_message(
        self, message: tuple[str, dict[str, str]]
    ) -> tuple[ExecuteRunRequest, str, int]:
        message_id, fields = message
        payload = json.loads(fields.get("payload") or "{}")
        return (
            ExecuteRunRequest.model_validate(payload),
            str(message_id),
            int(fields.get("attempt") or 0),
        )

    async def _retry(self, request: ExecuteRunRequest, attempt: int) -> None:
        if self._redis is not None:
            await self._redis.xadd(
                self.stream,
                {
                    "payload": json.dumps(
                        request.model_dump(mode="json"),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "attempt": str(attempt),
                    "enqueuedAt": str(time.time()),
                },
                maxlen=10_000,
                approximate=True,
            )
        else:
            await self._memory.put((request, attempt))

    async def _ack(self, message_id: str) -> None:
        if self._redis is not None and message_id:
            try:
                await self._redis.xack(self.stream, self.group, message_id)
            except Exception as exc:
                self._last_error = str(exc)[:500]

    async def stats(self) -> dict[str, Any]:
        pending = None
        length = None
        if self._redis is not None:
            try:
                length = await self._redis.xlen(self.stream)
                pending_info = await self._redis.xpending(self.stream, self.group)
                pending = (
                    int(pending_info.get("pending", 0))
                    if isinstance(pending_info, dict)
                    else None
                )
            except Exception as exc:
                self._last_error = str(exc)[:500]
        else:
            length = self._memory.qsize()
        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "stream": self.stream,
            "group": self.group,
            "consumer": self.consumer,
            "concurrency": self.concurrency,
            "workers": sum(1 for worker in self._workers if not worker.done()),
            "queueLength": length,
            "pending": pending,
            "processing": self._processing,
            "enqueued": self._enqueued,
            "completed": self._completed,
            "failed": self._failed,
            "retried": self._retried,
            "lastError": self._last_error,
        }

    async def close(self) -> None:
        self._stop.set()
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
