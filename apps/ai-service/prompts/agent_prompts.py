from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from prompts.registry import PromptRegistry

PROMPTS = PromptRegistry.default()


def _messages(
    name: str,
    *,
    output_language: str = "zh-CN",
    system_prompts: Mapping[str, str] | None = None,
    **variables: Any,
) -> list[dict[str, str]]:
    system_prompt = None
    if system_prompts:
        for key, value in system_prompts.items():
            if str(key).strip().lower() == name:
                system_prompt = value
                break
    messages = PROMPTS.render(
        name,
        system_prompt_override=system_prompt,
        **variables,
    ).messages
    if messages and output_language:
        messages[0]["content"] += f"\nRespond in the requested language: {output_language}."
    return messages


def planner_prompt(goal: str, output_language: str = "zh-CN", *, system_prompts: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    return _messages("planner", output_language=output_language, system_prompts=system_prompts, goal=goal)


def evidence_evaluation_prompt(goal: str, evidence_count: int, output_language: str = "zh-CN", *, system_prompts: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    return _messages("evidence_evaluation", output_language=output_language, system_prompts=system_prompts, goal=goal, evidence_count=evidence_count)


def finding_prompt(goal: str, evidence: list[dict[str, Any]], output_language: str = "zh-CN", *, system_prompts: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    return _messages("finding", output_language=output_language, system_prompts=system_prompts, goal=goal, evidence=evidence)


def report_prompt(goal: str, findings: list[dict[str, Any]], evidence: list[dict[str, Any]], output_language: str = "zh-CN", *, system_prompts: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    return _messages("report", output_language=output_language, system_prompts=system_prompts, goal=goal, findings=json.dumps(findings, ensure_ascii=False), evidence=evidence)


def review_prompt(referenced_ids: list[str], valid_ids: list[str], output_language: str = "zh-CN", *, system_prompts: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    return _messages("review", output_language=output_language, system_prompts=system_prompts, referenced_ids=json.dumps(referenced_ids), valid_ids=json.dumps(valid_ids))
