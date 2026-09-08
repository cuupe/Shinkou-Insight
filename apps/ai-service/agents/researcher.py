from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import Evidence


class InternalResearcherAgent:
    name = "internal_researcher"
    description = "在当前项目知识库中检索可引用证据。"
    capabilities = ("knowledge-search", "reranking", "read-only-tools")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        payload = message.payload
        questions = payload.get("queries") or [payload["goal"]]
        found: list[Evidence] = []
        for question in questions[-3:]:
            await context.events.publish(
                context.run_id,
                "tool.started",
                {"agent": self.name, "tool": "search_knowledge", "query": question},
            )
            result = await context.tools.execute(
                "search_knowledge",
                run_id=context.run_id,
                input_data={
                    "workspace_id": context.workspace_id,
                    "project_id": context.project_id,
                    "question": question,
                    "top_k": payload.get("top_k", 8),
                    "retrieval_mode": payload.get("retrieval_mode", "HYBRID"),
                    "use_reranker": payload.get("use_reranker", False),
                    "embedding_config": payload.get("embedding_config"),
                },
            )
            found.extend(Evidence.model_validate(item) for item in result)
            await context.events.publish(
                context.run_id,
                "tool.completed",
                {"agent": self.name, "tool": "search_knowledge", "count": len(result)},
            )

        unique: dict[str, Evidence] = {
            item.id: item
            for item in (Evidence.model_validate(raw) for raw in payload.get("evidence", []))
        }
        unique.update({item.id: item for item in found})
        evidence = list(unique.values())[: context.max_evidence]
        return AgentResult(
            agent=self.name,
            payload={"evidence": [item.model_dump() for item in evidence]},
        )
