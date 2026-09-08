from __future__ import annotations

from dataclasses import asdict
from typing import Any

import httpx

from agents.contracts import AgentMessage, AgentResult


class RemoteAgentTransport:
    """HTTP transport for agents deployed in separate worker processes."""

    def __init__(
        self,
        *,
        worker_urls: dict[str, str],
        client: httpx.AsyncClient,
        internal_api_key: str,
    ) -> None:
        self.worker_urls = {name: url.rstrip("/") for name, url in worker_urls.items()}
        self.client = client
        self.internal_api_key = internal_api_key

    def has_worker(self, agent: str) -> bool:
        return agent in self.worker_urls

    async def request(self, message: AgentMessage) -> AgentResult:
        base_url = self.worker_urls[message.recipient]
        response = await self.client.post(
            f"{base_url}/internal/agents/{message.recipient}/messages",
            headers={"X-Internal-Api-Key": self.internal_api_key},
            json=asdict(message),
            timeout=120,
        )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        return AgentResult(
            agent=str(body.get("agent", message.recipient)),
            status=str(body.get("status", "FAILED")),
            payload=dict(body.get("payload") or {}),
            error=body.get("error"),
        )
