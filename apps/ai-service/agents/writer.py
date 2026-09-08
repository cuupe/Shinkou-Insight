from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import Evidence, ReportDraft
from prompts.agent_prompts import report_prompt


class ReportWriterAgent:
    name = "report_writer"
    description = "根据研究发现和证据生成可审计报告草稿。"
    capabilities = ("report-writing", "citation-validation", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        payload = message.payload
        evidence = [Evidence.model_validate(item) for item in payload.get("evidence", [])]
        valid_ids = {item.id for item in evidence}
        messages = report_prompt(
            payload["goal"],
            payload.get("findings", []),
            [item.model_dump() for item in evidence],
            payload.get("output_language", "zh-CN"),
            system_prompts=payload.get("system_prompts"),
        )
        if payload.get("review_result"):
            messages.append(
                {
                    "role": "user",
                    "content": "Previous reviewer feedback (must be addressed): "
                    + str(payload["review_result"]),
                }
            )
        draft, _ = await context.model_for(self.name).structured(
            messages,
            ReportDraft,
        )
        draft.evidence_ids = [item for item in draft.evidence_ids if item in valid_ids]
        for section in draft.sections:
            section["evidence_ids"] = [
                item for item in section.get("evidence_ids", []) if item in valid_ids
            ]
        if not evidence:
            draft.limitations = [
                "没有检索到可引用的项目证据，结论仅能作为待验证假设。",
                *draft.limitations,
            ]
        return AgentResult(agent=self.name, payload={"report_draft": draft.model_dump()})
