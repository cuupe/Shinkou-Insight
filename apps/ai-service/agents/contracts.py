from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentMessage:
    """Transport-neutral message exchanged between the coordinator and an agent."""

    message_id: str
    run_id: str
    sender: str
    recipient: str
    intent: str
    payload: dict[str, Any]
    trace_id: str
    workspace_id: int = 0
    project_id: int = 0
    user_id: int = 0
    attempt: int = 0


@dataclass(slots=True)
class AgentResult:
    """Stable result envelope; agents never mutate coordinator state directly."""

    agent: str
    status: str = "SUCCEEDED"
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class AgentContext:
    """Per-run dependency scope passed to an isolated agent invocation."""

    run_id: str
    workspace_id: int
    project_id: int
    user_id: int
    model_router: Any
    web_search: Any
    tools: Any
    repository: Any
    events: Any
    max_evidence: int

    def model_for(self, agent: str) -> Any:
        return self.model_router.for_agent(agent)
