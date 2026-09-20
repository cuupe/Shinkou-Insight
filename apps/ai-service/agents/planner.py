from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import AgentPlan, PlanStep
from prompts.agent_prompts import planner_prompt


class PlannerAgent:
    name = "planner"
    description = "Turn a research goal into a bounded executable plan."
    capabilities = ("planning", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        goal = str(message.payload["goal"])
        language = str(message.payload.get("output_language", "zh-CN"))
        plan, _ = await context.model_for(self.name).structured(
            planner_prompt(goal, language),
            AgentPlan,
        )
        steps = [step.model_dump() for step in plan.steps[:4]]
        if not steps:
            steps = [
                PlanStep(
                    id="S1",
                    objective="核对与问题直接相关的项目资料",
                    action="SEARCH_INTERNAL",
                    query=goal[:2_000],
                ).model_dump()
            ]
        queries = [
            str(step.get("query") or step.get("objective") or "").strip()
            for step in steps
            if step.get("action") != "SYNTHESIZE"
            and (step.get("query") or step.get("objective"))
        ]
        return AgentResult(
            agent=self.name,
            payload={
                "plan": steps,
                "queries": list(dict.fromkeys(queries)),
                "plan_summary": plan.summary,
            },
        )
