from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PromptEvalCase:
    name: str
    prompt_name: str
    input_data: dict[str, Any]
    expected_evidence_ids: set[str]


@dataclass(frozen=True, slots=True)
class GroundingMetrics:
    referenced_ids: set[str]
    valid_ids: set[str]
    citation_precision: float
    citation_recall: float
    passed: bool


def evaluate_grounding(output: dict[str, Any], valid_evidence_ids: set[str], expected_evidence_ids: set[str] | None = None) -> GroundingMetrics:
    referenced = set(output.get("evidence_ids", []))
    for section in output.get("sections", []):
        referenced.update(section.get("evidence_ids", []))
    valid = referenced & valid_evidence_ids
    precision = len(valid) / len(referenced) if referenced else 1.0
    expected = expected_evidence_ids or set()
    recall = len(valid & expected) / len(expected) if expected else 1.0
    return GroundingMetrics(referenced, valid, round(precision, 4), round(recall, 4), not (referenced - valid))


def evaluate_prompt_case(case: PromptEvalCase, output: dict[str, Any], valid_evidence_ids: set[str]) -> dict[str, Any]:
    metrics = evaluate_grounding(output, valid_evidence_ids, case.expected_evidence_ids)
    return {"case": case.name, "prompt": case.prompt_name, "passed": metrics.passed, "citationPrecision": metrics.citation_precision, "citationRecall": metrics.citation_recall, "invalidIds": sorted(metrics.referenced_ids - metrics.valid_ids)}
