from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import PlanItem
from prompts.agent_prompts import planner_prompt


class PlannerAgent:
    name = "planner"
    description = "把研究目标拆分成可验证的研究问题。"
    capabilities = ("planning", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        goal = str(message.payload["goal"])
        language = str(message.payload.get("output_language", "zh-CN"))
        item, _ = await context.model_for(self.name).structured(
            planner_prompt(
                goal,
                language,
                system_prompts=message.payload.get("system_prompts"),
            ),
            PlanItem,
        )
        return AgentResult(
            agent=self.name,
            payload={"plan": [item.model_dump()], "queries": [item.question]},
        )
