from __future__ import annotations

from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    run_id: str
    workspace_id: int
    project_id: int
    user_id: int
    goal: str
    output_language: str
    allow_web_search: bool
    max_rounds: int
    top_k: int
    retrieval_mode: str
    use_reranker: bool
    max_evidence: int
    current_round: int
    plan: list[dict[str, Any]]
    queries: list[str]
    evidence: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    evaluation: dict[str, Any] | None
    report_draft: dict[str, Any] | None
    review_result: dict[str, Any] | None
    errors: list[dict[str, Any]]
    cancelled: bool
    review_attempts: int
    prompt_snapshot: dict[str, str]
    system_prompts: dict[str, str]
