from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import ReviewResult
from prompts.agent_prompts import review_prompt


class ReportReviewerAgent:
    name = "report_reviewer"
    description = "审核报告引用完整性、证据边界和可发布性。"
    capabilities = ("report-review", "citation-validation", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        draft = message.payload.get("report_draft") or {}
        valid_ids = {item["id"] for item in message.payload.get("evidence", [])}
        referenced = set(draft.get("evidence_ids", []))
        for section in draft.get("sections", []):
            referenced.update(section.get("evidence_ids", []))
        invalid = sorted(referenced - valid_ids)
        review, _ = await context.model_for(self.name).structured(
            review_prompt(sorted(referenced), sorted(valid_ids), message.payload.get("output_language", "zh-CN")),
            ReviewResult,
        )
        review.missing_citations = invalid
        review.approved = not invalid
        if invalid:
            review.issues = [f"引用不存在的证据：{', '.join(invalid)}"]
        return AgentResult(agent=self.name, payload={"review_result": review.model_dump()})
