from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from prompts.search_prompts import QUERY_REWRITE_SUFFIX


class QueryRewriterAgent:
    name = "query_rewriter"
    description = "根据当前证据缺口生成下一轮检索问题。"
    capabilities = ("query-rewriting", "deterministic-routing")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        query = f"{message.payload['goal']} {QUERY_REWRITE_SUFFIX}"
        return AgentResult(
            agent=self.name,
            payload={
                "queries": [query],
                "current_round": int(message.payload.get("current_round", 0)) + 1,
            },
        )
