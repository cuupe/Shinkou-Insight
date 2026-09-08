from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from agents.contracts import AgentContext, AgentMessage, AgentResult
from agents.registry import AgentRegistry
from agents.remote import RemoteAgentTransport


@dataclass(slots=True)
class _QueuedMessage:
    message: AgentMessage
    context: AgentContext
    future: asyncio.Future[AgentResult]


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

    async def start(self) -> None:
        for name in self.registry.names():
            if name not in self._queues:
                self._queues[name] = asyncio.Queue()
            worker = self._workers.get(name)
            if worker is None or worker.done():
                self._workers[name] = asyncio.create_task(self._worker(name), name=f"agent-worker:{name}")

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
        await context.events.publish(
            run_id,
            "agent.message.sent",
            {
                "messageId": message.message_id,
                "sender": sender,
                "recipient": recipient,
                "intent": intent,
                "attempt": attempt,
            },
        )
        if self.remote and self.remote.has_worker(recipient):
            try:
                await context.events.publish(
                    run_id,
                    "agent.started",
                    {
                        "agent": recipient,
                        "messageId": message.message_id,
                        "intent": intent,
                        "attempt": attempt,
                        "transport": "http",
                    },
                )
                result = await self.remote.request(message)
            except Exception as exc:
                await context.events.publish(
                    run_id,
                    "agent.failed",
                    {
                        "agent": recipient,
                        "messageId": message.message_id,
                        "intent": intent,
                        "error": str(exc)[:500],
                        "transport": "http",
                    },
                )
                return AgentResult(agent=recipient, status="FAILED", error=str(exc)[:1000])
            await context.events.publish(
                run_id,
                "agent.completed",
                {
                    "agent": recipient,
                    "messageId": message.message_id,
                    "intent": intent,
                    "status": result.status,
                    "transport": "http",
                },
            )
            return result
        if recipient not in self._queues:
            raise KeyError(f"Unknown agent: {recipient}")
        await self._queues[recipient].put(_QueuedMessage(message, context, future))
        return await future

    async def _worker(self, name: str) -> None:
        agent = self.registry.get(name)
        queue = self._queues[name]
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                return
            try:
                await item.context.events.publish(
                    item.message.run_id,
                    "agent.started",
                    {
                        "agent": name,
                        "messageId": item.message.message_id,
                        "intent": item.message.intent,
                        "attempt": item.message.attempt,
                    },
                )
                result = await agent.handle(item.message, item.context)
                await item.context.events.publish(
                    item.message.run_id,
                    "agent.completed",
                    {
                        "agent": name,
                        "messageId": item.message.message_id,
                        "intent": item.message.intent,
                        "status": result.status,
                    },
                )
                if not item.future.done():
                    item.future.set_result(result)
            except Exception as exc:
                await item.context.events.publish(
                    item.message.run_id,
                    "agent.failed",
                    {
                        "agent": name,
                        "messageId": item.message.message_id,
                        "intent": item.message.intent,
                        "error": str(exc)[:500],
                    },
                )
                if not item.future.done():
                    item.future.set_result(AgentResult(agent=name, status="FAILED", error=str(exc)[:1000]))
            finally:
                queue.task_done()

    async def close(self) -> None:
        for queue in self._queues.values():
            await queue.put(None)
        workers = tuple(self._workers.values())
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
