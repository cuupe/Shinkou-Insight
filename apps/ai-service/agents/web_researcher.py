from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import Evidence


class WebResearcherAgent:
    name = "web_researcher"
    description = "在获得授权时检索外部来源并返回可追溯证据。"
    capabilities = ("web-search", "external-sources")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        if not message.payload.get("allow_web_search"):
            return AgentResult(agent=self.name, payload={"evidence": []})
        web_items = await context.web_search.search(message.payload["goal"], top_k=5)
        external = [Evidence.model_validate(item) for item in web_items]
        unique: dict[str, Evidence] = {
            item.id: item
            for item in (Evidence.model_validate(raw) for raw in message.payload.get("evidence", []))
        }
        unique.update({item.id: item for item in external})
        evidence = list(unique.values())[: context.max_evidence]
        await context.events.publish(
            context.run_id,
            "evidence.added",
            {
                "agent": self.name,
                "count": len(external),
                "source": "web",
                "items": [item.model_dump() for item in external],
            },
        )
        return AgentResult(
            agent=self.name,
            payload={"evidence": [item.model_dump() for item in evidence]},
        )
