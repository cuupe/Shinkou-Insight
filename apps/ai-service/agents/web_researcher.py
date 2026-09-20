from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import Evidence
from tools.search_quality import focused_query, rank_web_evidence


class WebResearcherAgent:
    name = "web_researcher"
    description = "Search permitted external sources and return traceable evidence."
    capabilities = ("web-search", "external-sources")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        if not message.payload.get("allow_web_search"):
            return AgentResult(agent=self.name, payload={"evidence": []})

        requested_query = str(
            message.payload.get("search_query") or message.payload.get("goal") or ""
        ).strip()
        provider_query = focused_query(requested_query)
        web_items = await context.web_search.search(provider_query, top_k=5)
        external = rank_web_evidence(
            requested_query,
            [Evidence.model_validate(item) for item in web_items],
            5,
            require_body=True,
        )
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
                "query": provider_query,
                "items": [item.model_dump() for item in external],
            },
        )
        return AgentResult(
            agent=self.name,
            payload={"evidence": [item.model_dump() for item in evidence]},
        )
