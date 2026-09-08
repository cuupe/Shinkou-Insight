from __future__ import annotations

from typing import Any


class AgentModelRouter:
    """Allows each agent to use its own gateway while retaining a safe fallback."""

    def __init__(self, default: Any, overrides: dict[str, Any] | None = None) -> None:
        self.default = default
        self.overrides = dict(overrides or {})

    def register(self, agent: str, gateway: Any) -> None:
        self.overrides[agent] = gateway

    def for_agent(self, agent: str) -> Any:
        return self.overrides.get(agent, self.default)
