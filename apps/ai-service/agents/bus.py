from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime

from agents.contracts import AgentContext, AgentMessage, AgentResult
from agents.registry import AgentRegistry
from agents.remote import RemoteAgentTransport
from core.events import utc_now


class _TaskCancelled(RuntimeError):
    pass


@dataclass(slots=True)
class _QueuedMessage:
    message: AgentMessage
    context: AgentContext
    future: asyncio.Future[AgentResult]
    task: dict


class AgentMessageBus:
    """In-process transport with the same contract as a queue-backed transport.

    The coordinator only knows how to send envelopes. Replacing this class with
    Redis Streams, NATS, or an HTTP transport does not require changing agents.
    """

    def __init__(self, registry: AgentRegistry, remote: RemoteAgentTransport | None = None) -> None:
        self.registry = registry
        self.remote = remote
        self._queues: dict[str, asyncio.Queue[_QueuedMessage | None]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._concurrency = 3

    async def start(self) -> None:
        for name in self.registry.names():
            if name not in self._queues:
                self._queues[name] = asyncio.Queue()
            for slot in range(self._concurrency):
                key = f"{name}:{slot}"
                worker = self._workers.get(key)
                if worker is None or worker.done():
                    self._workers[key] = asyncio.create_task(self._worker(name), name=f"agent-worker:{key}")

    async def request(
        self,
        *,
        run_id: str,
        sender: str,
        recipient: str,
        intent: str,
        payload: dict,
        context: AgentContext,
        attempt: int = 0,
    ) -> AgentResult:
        await self.start()
        if recipient not in self._queues:
            raise KeyError(f"Unknown agent: {recipient}")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[AgentResult] = loop.create_future()
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            run_id=str(run_id),
            sender=sender,
            recipient=recipient,
            intent=intent,
            payload=payload,
            trace_id=str(run_id),
            workspace_id=context.workspace_id,
            project_id=context.project_id,
            user_id=context.user_id,
            attempt=attempt,
        )
        task = {
            "id": message.message_id, "parentId": f"{run_id}:primary",
            "agent": recipient, "title": str(payload.get("_task_title") or recipient),
            "objective": str(payload.get("_task_objective") or payload.get("goal") or intent)[:2000],
            "status": "pending", "createdAt": utc_now(), "attempt": attempt,
            "transport": "http" if self.remote and self.remote.has_worker(recipient) else "local",
        }
        await context.events.publish(
            run_id,
            "agent.message.sent",
            {
                "messageId": message.message_id,
                "sender": sender,
                "recipient": recipient,
                "intent": intent,
                "attempt": attempt,
                "task": dict(task),
            },
        )
        if self.remote and self.remote.has_worker(recipient):
            try:
                await self._task_event(context, message, task, "running")
                result = await self._invoke(self.remote.request(message), context, future)
            except Exception as exc:
                await self._task_event(context, message, task, "cancelled" if isinstance(exc, _TaskCancelled) else "failed", error=str(exc))
                return AgentResult(agent=recipient, status="FAILED", error=str(exc)[:1000])
            await self._task_event(context, message, task, "completed" if result.status == "SUCCEEDED" else "failed", result=result)
            return result
        if recipient not in self._queues:
            raise KeyError(f"Unknown agent: {recipient}")
        await self._queues[recipient].put(_QueuedMessage(message, context, future, task))
        return await future

    async def _invoke(self, invocation, context: AgentContext, future: asyncio.Future) -> AgentResult:
        work = asyncio.create_task(invocation)
        try:
            while not work.done():
                if future.cancelled() or (context.repository and context.repository.is_cancelled(context.run_id)):
                    raise _TaskCancelled("本次任务已取消")
                await asyncio.wait({work}, timeout=0.1)
            return await work
        finally:
            if not work.done():
                work.cancel()
                await asyncio.gather(work, return_exceptions=True)

    async def _task_event(self, context, message, task, status, *, result=None, error=None):
        now = utc_now()
        task["status"] = status
        if status == "running":
            task["startedAt"] = now
        else:
            task["completedAt"] = now
            if task.get("startedAt"):
                task["durationMs"] = max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(task["startedAt"])).total_seconds() * 1000))
            if error or (result and result.error):
                task["error"] = str(error or result.error)[:500]
            if result and status == "completed":
                payload = result.payload
                if "plan" in payload:
                    task["summary"] = str(payload.get("plan_summary") or f"已形成 {len(payload['plan'])} 项计划")[:2000]
                elif "evidence" in payload:
                    task["summary"] = f"返回 {len(payload['evidence'])} 条证据" if payload["evidence"] else "未找到可引用证据"
                elif "findings" in payload:
                    task["summary"] = "\n".join(str(item.get("statement", "")) for item in payload["findings"])[:2000]
                elif "review_result" in payload:
                    review = payload["review_result"] or {}
                    task["summary"] = "审核通过" if review.get("approved") else "审核未通过：" + str(review.get("issues") or review.get("reasons") or "需修订")[:1000]
                elif "report_draft" in payload:
                    task["summary"] = "已返回报告草稿，等待主智能体汇总"
                else:
                    task["summary"] = "已返回执行结果"
        await context.events.publish(message.run_id, f"agent.{'started' if status == 'running' else status}", {
            "agent": message.recipient, "messageId": message.message_id,
            "intent": message.intent, "attempt": message.attempt,
            "status": result.status if result else status,
            "task": dict(task),
        })

    async def _worker(self, name: str) -> None:
        agent = self.registry.get(name)
        queue = self._queues[name]
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                return
            try:
                if item.future.cancelled() or (item.context.repository and item.context.repository.is_cancelled(item.message.run_id)):
                    raise _TaskCancelled("本次任务已取消")
                await self._task_event(item.context, item.message, item.task, "running")
                result = await self._invoke(agent.handle(item.message, item.context), item.context, item.future)
                await self._task_event(item.context, item.message, item.task, "completed" if result.status == "SUCCEEDED" else "failed", result=result)
                if not item.future.done():
                    item.future.set_result(result)
            except Exception as exc:
                await self._task_event(item.context, item.message, item.task, "cancelled" if isinstance(exc, _TaskCancelled) else "failed", error=str(exc))
                if not item.future.done():
                    item.future.set_result(AgentResult(agent=name, status="FAILED", error=str(exc)[:1000]))
            finally:
                queue.task_done()

    async def close(self) -> None:
        for queue in self._queues.values():
            for _ in range(self._concurrency):
                await queue.put(None)
        workers = tuple(self._workers.values())
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
