from __future__ import annotations

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import Evidence, EvidenceEvaluation, Finding
from prompts.agent_prompts import evidence_evaluation_prompt, finding_prompt
from tools.search_quality import filter_relevant_evidence


class EvidenceAnalystAgent:
    name = "evidence_analyst"
    description = "Evaluate evidence coverage and choose a bounded next step."
    capabilities = ("evidence-evaluation", "bounded-routing", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        payload = message.payload
        raw_evidence = list(payload.get("evidence", []))
        evidence_count = len(raw_evidence)
        relevant_count = len(filter_relevant_evidence(str(payload["goal"]), raw_evidence))
        current_round = int(payload.get("current_round", 0))
        max_rounds = int(payload.get("max_rounds", 3))

        if relevant_count:
            action = "ENOUGH"
        elif payload.get("allow_web_search") and current_round == 0:
            action = "NEED_WEB"
        elif current_round + 1 < max_rounds:
            action = "MORE_INTERNAL"
        else:
            action = "ENOUGH"

        evaluation, _ = await context.model_for(self.name).structured(
            evidence_evaluation_prompt(
                payload["goal"],
                evidence_count,
                payload.get("output_language", "zh-CN"),
                [item for item in raw_evidence if isinstance(item, dict)],
            ),
            EvidenceEvaluation,
        )
        evaluation.next_action = action
        evaluation.sufficient = action == "ENOUGH" and relevant_count > 0
        if not relevant_count:
            evaluation.missing = [
                "缺少与问题主题直接相关、可追溯的证据"
                if evidence_count
                else "缺少可引用的项目资料"
            ]
        return AgentResult(agent=self.name, payload={"evaluation": evaluation.model_dump()})


class FindingAnalystAgent:
    name = "finding_analyst"
    description = "Synthesize traceable findings from the supplied evidence."
    capabilities = ("finding-synthesis", "citation-validation", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        payload = message.payload
        evidence = filter_relevant_evidence(payload["goal"], payload.get("evidence", []))
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
