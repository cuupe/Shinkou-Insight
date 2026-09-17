from __future__ import annotations

import re
from typing import Any

from agents.contracts import AgentContext, AgentMessage, AgentResult
from models.schemas import ReviewResult
from prompts.agent_prompts import review_prompt


def _tokens(text: str) -> set[str]:
    normalized = str(text or "").casefold()
    words = set(re.findall(r"[a-z0-9][a-z0-9._-]{1,}|[\u4e00-\u9fff]{2,}", normalized))
    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        words.update(block[index : index + 2] for index in range(len(block) - 1))
    return {word for word in words if len(word) >= 2}


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w])\d+(?:\.\d+)?%?", str(text or "")))


def _draft_text(draft: dict[str, Any]) -> str:
    parts = [str(draft.get("title") or ""), str(draft.get("executive_summary") or "")]
    for section in draft.get("sections") or []:
        if isinstance(section, dict):
            parts.extend(str(section.get(key) or "") for key in ("title", "heading", "content", "body", "summary"))
    parts.extend(str(item) for item in (draft.get("recommendations") or []))
    parts.extend(str(item) for item in (draft.get("limitations") or []))
    return "\n".join(parts)


def apply_review_guards(
    review: ReviewResult,
    draft: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
) -> ReviewResult:
    """Apply deterministic release gates after the model review."""

    policy = policy or {}
    require_citations = bool(policy.get("require_citations", policy.get("requireCitations", True)))
    verify_numbers = bool(policy.get("verify_numbers", policy.get("verifyNumbers", True)))
    label_external = bool(policy.get("label_external", policy.get("labelExternal", True)))
    valid_ids = {str(item.get("id")) for item in evidence_rows if item.get("id")}
    referenced = {str(item) for item in draft.get("evidence_ids", [])}
    for section in draft.get("sections") or []:
        if isinstance(section, dict):
            referenced.update(str(item) for item in section.get("evidence_ids", []) if item)
    invalid = sorted(referenced - valid_ids)
    report_text = _draft_text(draft)
    issues = list(review.issues)
    blocking = list(review.blocking_issues)
    missing = list(review.missing_citations)
    if invalid:
        missing.extend(item for item in invalid if item not in missing)
        blocking.append(f"引用不存在的证据：{', '.join(invalid)}")

    if require_citations and report_text.strip() and valid_ids and not referenced:
        missing.append("REPORT_CITATION_REQUIRED")
        blocking.append("报告包含可发布内容但没有任何证据引用")
    citation_completeness = len(referenced & valid_ids) / len(referenced) if referenced else (0.0 if valid_ids and report_text.strip() else 1.0)

    by_id = {str(item.get("id")): item for item in evidence_rows}
    report_terms = _tokens(report_text)
    supports: list[float] = []
    for evidence_id in referenced & valid_ids:
        content_terms = _tokens(str(by_id[evidence_id].get("content") or ""))
        supports.append(len(report_terms & content_terms) / max(len(report_terms), 1))
    evidence_support = round(sum(supports) / len(supports), 4) if supports else (0.0 if report_text.strip() and valid_ids else 1.0)
    if referenced and evidence_support < 0.01:
        blocking.append("报告引用的证据与正文缺乏可识别的事实支撑")
        issues.append("至少一条引用需要回到原文重新核对")

    report_numbers = _numbers(report_text)
    evidence_numbers = _numbers("\n".join(str(item.get("content") or "") for item in evidence_rows if str(item.get("id")) in valid_ids))
    unsupported_numbers = sorted(report_numbers - evidence_numbers)
    numeric_consistency = 1.0 if not report_numbers else len(report_numbers & evidence_numbers) / len(report_numbers)
    if verify_numbers and unsupported_numbers:
        blocking.append(f"报告中的数字未在证据中找到：{', '.join(unsupported_numbers[:8])}")

    external_ids = {str(item.get("id")) for item in evidence_rows if item.get("source_type") == "web" and str(item.get("id")) in referenced}
    if label_external and external_ids and not re.search(r"外部|网页|来源|链接|web|external", report_text, re.IGNORECASE):
        blocking.append("报告使用了外部来源，但没有明确标注外部来源")

    review.missing_citations = list(dict.fromkeys(missing))
    review.issues = list(dict.fromkeys(issues + blocking))
    review.blocking_issues = list(dict.fromkeys(blocking))
    review.citation_completeness = round(citation_completeness, 4)
    review.evidence_support = round(max(0.0, min(1.0, evidence_support)), 4)
    review.factual_consistency = round(max(0.0, min(1.0, float(review.factual_consistency or (1.0 if not blocking else 0.5)))), 4)
    review.numeric_consistency = round(max(0.0, min(1.0, numeric_consistency)), 4)
    if blocking:
        review.approved = False
        review.risk_level = "BLOCKED"
        review.rewrite_instructions = list(dict.fromkeys([*review.rewrite_instructions, "逐条修正阻断项并为每个事实断言补充真实证据引用。"]))
    elif not review.approved:
        review.risk_level = "HIGH"
    else:
        review.risk_level = "LOW"
    return review


class ReportReviewerAgent:
    name = "report_reviewer"
    description = "审核报告引用完整性、证据边界、数字一致性和可发布性。"
    capabilities = ("report-review", "citation-validation", "numeric-verification", "structured-output")

    async def handle(self, message: AgentMessage, context: AgentContext) -> AgentResult:
        draft = message.payload.get("report_draft") or {}
        evidence_rows = list(message.payload.get("evidence") or [])
        valid_ids = {str(item["id"]) for item in evidence_rows if item.get("id")}
        referenced = set(str(item) for item in draft.get("evidence_ids", []))
        for section in draft.get("sections", []):
            referenced.update(str(item) for item in section.get("evidence_ids", []) if item)
        review, _ = await context.model_for(self.name).structured(
            review_prompt(
                sorted(referenced),
                sorted(valid_ids),
                message.payload.get("output_language", "zh-CN"),
                report_draft=draft,
                evidence=evidence_rows,
                review_policy=message.payload.get("review_policy"),
            ),
            ReviewResult,
        )
        review = apply_review_guards(review, draft, evidence_rows, message.payload.get("review_policy"))
        return AgentResult(agent=self.name, payload={"review_result": review.model_dump()})
