from __future__ import annotations

from typing import Any

from agents.base import ResearchAgent


class AgentRegistry:
    """Runtime registry that keeps agent identity separate from orchestration."""

    def __init__(self) -> None:
        self._agents: dict[str, ResearchAgent] = {}

    def register(self, agent: ResearchAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agent already registered: {agent.name}")
        self._agents[agent.name] = agent

    def get(self, name: str) -> ResearchAgent:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"Unknown agent: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self._agents)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "capabilities": list(agent.capabilities),
            }
            for agent in self._agents.values()
        ]
