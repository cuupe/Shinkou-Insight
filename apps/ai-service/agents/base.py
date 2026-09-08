from __future__ import annotations

from typing import Protocol

from agents.contracts import AgentContext, AgentMessage, AgentResult


class ResearchAgent(Protocol):
    name: str
    description: str
    capabilities: tuple[str, ...]

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult: ...
