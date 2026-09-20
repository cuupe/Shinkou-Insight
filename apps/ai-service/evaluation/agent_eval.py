"""Deterministic, provider-independent checks for an agent run.

These checks do not judge writing style or model intelligence. They guard the
parts that must be true regardless of which model is configured: tool policy,
source usability, answer grounding, and bounded decomposition of complex work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

from evaluation.prompt_eval import evaluate_grounding
from models.schemas import Evidence
from tools.search_quality import topic_score


@dataclass(frozen=True, slots=True)
class AgentDimensionResult:
    name: str
    passed: bool
    score: float
    findings: tuple[str, ...]
    metrics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentEvaluation:
    dimensions: tuple[AgentDimensionResult, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.dimensions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "dimensions": [
                {
                    "name": item.name,
                    "passed": item.passed,
                    "score": item.score,
                    "findings": list(item.findings),
                    "metrics": item.metrics,
                }
                for item in self.dimensions
            ],
        }


def _event_parts(event: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(event, dict):
        return str(event.get("event_type") or event.get("type") or ""), dict(event.get("payload") or {})
    return str(getattr(event, "event_type", "")), dict(getattr(event, "payload", {}) or {})


def evaluate_tool_usage(
    events: Iterable[Any], expected_tools: set[str] | None = None
) -> AgentDimensionResult:
    started: list[str] = []
    failed = 0
    denied = 0
    for event in events:
        event_type, payload = _event_parts(event)
        if event_type == "tool.started" and payload.get("tool"):
            started.append(str(payload["tool"]))
        if event_type in {"tool.failed", "tool.error"} or payload.get("failed") is True:
            failed += 1
        if event_type in {"tool.denied", "tool.blocked"} or payload.get("denied") is True:
            denied += 1
    used = set(started)
    expected = expected_tools or set()
    missing = sorted(expected - used)
    findings: list[str] = []
    if failed:
        findings.append(f"{failed} tool call(s) failed")
    if missing:
        findings.append(f"missing expected tools: {', '.join(missing)}")
    score = 1.0
    if failed:
        score -= min(0.6, failed * 0.2)
    if missing:
        score -= min(0.5, len(missing) * 0.25)
    return AgentDimensionResult(
        name="tool_usage",
        passed=not failed and not missing,
        score=round(max(score, 0.0), 4),
        findings=tuple(findings),
        metrics={"calls": len(started), "tools": sorted(used), "failed": failed, "denied": denied, "missing": missing},
    )


def evaluate_resource_quality(
    goal: str,
    evidence: Iterable[Evidence | dict[str, Any]],
    *,
    requires_external: bool = False,
    requires_evidence: bool = True,
) -> AgentDimensionResult:
    rows = [Evidence.model_validate(item) for item in evidence]
    relevant = [
        item
        for item in rows
        if topic_score(goal, f"{item.source_name}\n{item.section_title or ''}\n{item.content}") > 0
    ]
    web_rows = [item for item in relevant if item.source_type == "web"]
    citation_ready_web = [
        item
        for item in web_rows
        if item.content_kind == "fulltext"
        and bool(item.url)
        and urlsplit(item.url or "").scheme in {"http", "https"}
    ]
    if requires_external:
        passed = bool(citation_ready_web)
    else:
        passed = bool(relevant) or not requires_evidence
    usable = len(relevant)
    score = 1.0 if passed else (0.0 if not rows else round(min(0.75, usable / max(len(rows), 1)), 4))
    findings = () if passed else ("没有获取到与问题直接相关且可追溯的资料",)
    return AgentDimensionResult(
        name="resource_quality",
        passed=passed,
        score=score,
        findings=findings,
        metrics={
            "total": len(rows),
            "relevant": usable,
            "webRelevant": len(web_rows),
            "citationReadyWeb": len(citation_ready_web),
        },
    )


def evaluate_answer_quality(
    answer: dict[str, Any],
    valid_evidence_ids: set[str],
    expected_evidence_ids: set[str] | None = None,
) -> AgentDimensionResult:
    grounding = evaluate_grounding(answer, valid_evidence_ids, expected_evidence_ids)
    passed = grounding.passed and grounding.citation_recall >= 1.0
    findings = () if passed else ("回答存在无效引用或未覆盖期望证据",)
    return AgentDimensionResult(
        name="answer_grounding",
        passed=passed,
        score=round((grounding.citation_precision + grounding.citation_recall) / 2, 4),
        findings=findings,
        metrics={
            "referenced": sorted(grounding.referenced_ids),
            "valid": sorted(grounding.valid_ids),
            "citationPrecision": grounding.citation_precision,
            "citationRecall": grounding.citation_recall,
        },
    )


def evaluate_complexity(
    plan: Iterable[dict[str, Any]],
    events: Iterable[Any],
    *,
    complex_request: bool,
) -> AgentDimensionResult:
    steps = [dict(step) for step in plan]
    executable = [step for step in steps if str(step.get("action", "")).upper() != "SYNTHESIZE"]
    has_synthesis = any(str(step.get("action", "")).upper() == "SYNTHESIZE" for step in steps)
    agents = set()
    for event in events:
        event_type, payload = _event_parts(event)
        if event_type == "agent.started" and payload.get("agent"):
            agents.add(str(payload["agent"]))
    if not complex_request:
        passed = True
    else:
        passed = len(executable) >= 2 and has_synthesis and len(agents) >= 2
    findings = () if passed else ("复杂问题没有形成足够的检索步骤和汇总阶段",)
    target = 3 if complex_request else 1
    score = min(1.0, (len(executable) + int(has_synthesis)) / target) if target else 1.0
    return AgentDimensionResult(
        name="complex_problem_solving",
        passed=passed,
        score=round(score, 4),
        findings=findings,
        metrics={"steps": len(steps), "executableSteps": len(executable), "hasSynthesis": has_synthesis, "agents": sorted(agents)},
    )


def evaluate_agent_run(
    *,
    goal: str,
    events: Iterable[Any],
    evidence: Iterable[Evidence | dict[str, Any]],
    answer: dict[str, Any],
    plan: Iterable[dict[str, Any]],
    valid_evidence_ids: set[str],
    expected_evidence_ids: set[str] | None = None,
    expected_tools: set[str] | None = None,
    requires_external: bool = False,
    complex_request: bool = False,
) -> AgentEvaluation:
    event_list = list(events)
    evidence_list = list(evidence)
    return AgentEvaluation(
        dimensions=(
            evaluate_tool_usage(event_list, expected_tools),
            evaluate_resource_quality(goal, evidence_list, requires_external=requires_external),
            evaluate_answer_quality(answer, valid_evidence_ids, expected_evidence_ids),
            evaluate_complexity(plan, event_list, complex_request=complex_request),
        )
    )
