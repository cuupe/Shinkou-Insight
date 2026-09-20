from __future__ import annotations

import json
from typing import Any

from prompts.registry import PromptRegistry
from prompts.security import sanitize_untrusted_text

PROMPTS = PromptRegistry.default()


def _messages(
    name: str,
    *,
    output_language: str = "zh-CN",
    **variables: Any,
) -> list[dict[str, str]]:
    messages = PROMPTS.render(
        name,
        **variables,
    ).messages
    if messages and output_language:
        messages[0][
            "content"
        ] += f"\nRespond in the requested language: {output_language}."
    return messages


def planner_prompt(goal: str, output_language: str = "zh-CN") -> list[dict[str, str]]:
    return _messages("planner", output_language=output_language, goal=goal)


def evidence_evaluation_prompt(
    goal: str,
    evidence_count: int,
    output_language: str = "zh-CN",
    evidence: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    return _messages(
        "evidence_evaluation",
        output_language=output_language,
        goal=goal,
        evidence_count=evidence_count,
        evidence=evidence or [],
    )


def finding_prompt(
    goal: str, evidence: list[dict[str, Any]], output_language: str = "zh-CN"
) -> list[dict[str, str]]:
    return _messages(
        "finding", output_language=output_language, goal=goal, evidence=evidence
    )


def report_prompt(
    goal: str,
    findings: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    output_language: str = "zh-CN",
) -> list[dict[str, str]]:
    return _messages(
        "report",
        output_language=output_language,
        goal=goal,
        findings=json.dumps(findings, ensure_ascii=False),
        evidence=evidence,
    )


def review_prompt(
    referenced_ids: list[str],
    valid_ids: list[str],
    output_language: str = "zh-CN",
    report_draft: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    review_policy: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    return _messages(
        "review",
        output_language=output_language,
        referenced_ids=json.dumps(referenced_ids, ensure_ascii=False),
        valid_ids=json.dumps(valid_ids, ensure_ascii=False),
        report_draft=json.dumps(report_draft or {}, ensure_ascii=False),
        evidence=evidence or [],
        review_policy=json.dumps(review_policy or {}, ensure_ascii=False),
    )


def reflection_prompt(
    goal: str,
    answer: str,
    evidence: list[dict[str, Any]],
    output_language: str = "zh-CN",
) -> list[dict[str, str]]:
    return _messages(
        "reflection",
        output_language=output_language,
        goal=goal,
        answer=answer,
        evidence=evidence,
    )


def react_action_prompt(
    goal: str,
    context: str,
    evidence: list[dict[str, Any]],
    allow_web_search: bool,
    output_language: str = "zh-CN",
) -> list[dict[str, str]]:
    return _messages(
        "react_action",
        output_language=output_language,
        goal=goal,
        context=sanitize_untrusted_text(context, max_chars=8_000),
        evidence=evidence,
        allow_web_search="yes" if allow_web_search else "no",
    )


def plan_and_solve_prompt(
    goal: str,
    context: str,
    allow_web_search: bool,
    output_language: str = "zh-CN",
) -> list[dict[str, str]]:
    return _messages(
        "plan_and_solve",
        output_language=output_language,
        goal=goal,
        context=sanitize_untrusted_text(context, max_chars=8_000),
        allow_web_search="yes" if allow_web_search else "no",
    )
