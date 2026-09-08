from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import Evidence, EvidenceEvaluation, Finding
from prompts.agent_prompts import evidence_evaluation_prompt, finding_prompt


class EvidenceAnalystAgent:
    name = "evidence_analyst"
    description = "评估证据充分性并决定下一步协作路径。"
    capabilities = ("evidence-evaluation", "bounded-routing", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        payload = message.payload
        evidence_count = len(payload.get("evidence", []))
        if evidence_count:
            action = "ENOUGH"
        elif payload.get("allow_web_search") and payload.get("current_round", 0) == 0:
            action = "NEED_WEB"
        elif payload.get("current_round", 0) + 1 < payload["max_rounds"]:
            action = "MORE_INTERNAL"
        else:
            action = "ENOUGH"
        evaluation, _ = await context.model_for(self.name).structured(
            evidence_evaluation_prompt(
                payload["goal"],
                evidence_count,
                payload.get("output_language", "zh-CN"),
                system_prompts=payload.get("system_prompts"),
            ),
            EvidenceEvaluation,
        )
        evaluation.next_action = action
        evaluation.sufficient = action == "ENOUGH" and evidence_count > 0
        if not evidence_count:
            evaluation.missing = ["缺少可引用的项目资料"]
        return AgentResult(agent=self.name, payload={"evaluation": evaluation.model_dump()})


class FindingAnalystAgent:
    name = "finding_analyst"
    description = "把证据综合为带引用的研究发现。"
    capabilities = ("finding-synthesis", "citation-validation", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        payload = message.payload
        evidence = [Evidence.model_validate(item) for item in payload.get("evidence", [])]
        if not evidence:
            finding = Finding(
                id="F1",
                kind="gap",
                statement="当前项目资料不足以支持可靠结论。",
                evidence_ids=[],
                confidence=1.0,
            )
        else:
            finding, _ = await context.model_for(self.name).structured(
                finding_prompt(
                    payload["goal"],
                    [item.model_dump() for item in evidence],
                    payload.get("output_language", "zh-CN"),
                    system_prompts=payload.get("system_prompts"),
                ),
                Finding,
            )
            valid_ids = {item.id for item in evidence}
            finding.evidence_ids = [item for item in finding.evidence_ids if item in valid_ids]
        await context.events.publish(
            context.run_id,
            "finding.added",
            {"agent": self.name, "findingId": finding.id, "evidenceIds": finding.evidence_ids},
        )
        return AgentResult(agent=self.name, payload={"findings": [finding.model_dump()]})
