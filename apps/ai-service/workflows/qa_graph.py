"""Legacy LangGraph workflow kept for compatibility.

The production runtime now uses ``agents.coordinator.AgentCoordinator`` and
the message-bus based agent registry. This module remains available for older
integrations and focused graph experiments.
"""

from __future__ import annotations

from typing import Any, Protocol

from langgraph.graph import END, START, StateGraph

from core.events import EventBus
from agents.reviewer import apply_review_guards
from models.llm import ModelGateway
from models.schemas import (
    Evidence,
    EvidenceEvaluation,
    Finding,
    PlanItem,
    ReportDraft,
    ReviewResult,
)
from prompts.agent_prompts import (
    evidence_evaluation_prompt,
    finding_prompt,
    planner_prompt,
    report_prompt,
    review_prompt,
)
from rag.retriever import Retriever
from workflows.state import ResearchState


class RunCancelled(Exception):
    pass


class GraphRuntime(Protocol):
    model: ModelGateway
    retriever: Retriever
    web_search: Any
    events: EventBus
    tools: Any
    repository: Any

    def is_cancelled(self, run_id: str) -> bool: ...

    def model_for(self, run_id: str | int) -> ModelGateway: ...

    def web_search_for(self, run_id: str | int) -> Any: ...


def build_qa_graph(runtime: GraphRuntime, *, checkpointer: Any | None = None):
    """Build the planner/researcher/analyst/writer/reviewer graph.

    Nodes only return state patches. Side effects are limited to the event
    bus, which keeps the workflow deterministic and makes checkpointing safe.
    """

    async def checkpoint(state: ResearchState, node: str, title: str) -> bool:
        if runtime.is_cancelled(state["run_id"]):
            raise RunCancelled("run cancelled by caller")
        progress = {
            "VALIDATE_INPUT": 5,
            "PLAN": 15,
            "RETRIEVE_INTERNAL": 35,
            "EVALUATE_EVIDENCE": 48,
            "REWRITE_QUERY": 28,
            "SEARCH_WEB": 55,
            "SYNTHESIZE_FINDINGS": 68,
            "WRITE_REPORT": 82,
            "REVIEW_REPORT": 92,
            "PERSIST_RESULT": 98,
        }.get(node, 0)
        await runtime.repository.update(
            state["run_id"], current_node=node, current_step=title, progress=progress
        )
        await runtime.events.publish(
            state["run_id"], "node.started", {"node": node, "title": title}
        )
        await runtime.events.publish(
            state["run_id"],
            "run.progress",
            {"node": node, "progress": progress, "currentStep": title},
        )
        return True

    async def done(
        state: ResearchState, node: str, title: str, detail: str = ""
    ) -> None:
        await runtime.events.publish(
            state["run_id"],
            "node.completed",
            {"node": node, "title": title, "detail": detail},
        )

    async def validate_input(state: ResearchState) -> dict:
        await checkpoint(state, "VALIDATE_INPUT", "校验研究上下文")
        goal = state["goal"].strip()
        if not goal:
            raise ValueError("goal cannot be empty")
        if not state["workspace_id"] or not state["project_id"]:
            raise ValueError("workspace_id and project_id are required")
        await done(state, "VALIDATE_INPUT", "校验研究上下文")
        return {"goal": goal, "current_round": 0}

    async def plan(state: ResearchState) -> dict:
        await checkpoint(state, "PLAN", "Planner 拆解研究目标")
        item, _ = await runtime.model_for(state["run_id"]).structured(
            planner_prompt(state["goal"], state.get("output_language", "zh-CN")),
            PlanItem,
        )
        plan_item = item.model_dump()
        await done(state, "PLAN", "Planner 拆解研究目标", "已生成 1 个高价值子问题")
        return {"plan": [plan_item], "queries": [item.question]}

    async def retrieve_internal(state: ResearchState) -> dict:
        await checkpoint(state, "RETRIEVE_INTERNAL", "Researcher 检索项目资料")
        questions = state.get("queries") or [state["goal"]]
        found: list[Evidence] = []
        for question in questions[-3:]:
            await runtime.events.publish(
                state["run_id"],
                "tool.started",
                {"tool": "search_knowledge", "query": question},
            )
            result = await runtime.tools.execute(
                "search_knowledge",
                run_id=state["run_id"],
                input_data={
                    "workspace_id": state["workspace_id"],
                    "project_id": state["project_id"],
                    "question": question,
                    "top_k": state.get("top_k", 8),
                    "retrieval_mode": state.get("retrieval_mode", "HYBRID"),
                    "use_reranker": state.get("use_reranker", False),
                },
            )
            found.extend(result)
            await runtime.events.publish(
                state["run_id"],
                "tool.completed",
                {"tool": "search_knowledge", "count": len(result)},
            )
        unique: dict[str, Evidence] = {
            item.id: item
            for item in (
                Evidence.model_validate(raw) for raw in state.get("evidence", [])
            )
        }
        unique.update({item.id: item for item in found})
        items = list(unique.values())[: state.get("max_evidence", 12)]
        await done(
            state,
            "RETRIEVE_INTERNAL",
            "Researcher 检索项目资料",
            f"获得 {len(items)} 条证据",
        )
        await runtime.events.publish(
            state["run_id"],
            "evidence.added",
            {
                "count": len(items),
                "source": "internal",
                "items": [item.model_dump() for item in items],
            },
        )
        return {"evidence": [item.model_dump() for item in items]}

    async def evaluate_evidence(state: ResearchState) -> dict:
        await checkpoint(state, "EVALUATE_EVIDENCE", "Analyst 评估证据充分性")
        evidence_count = len(state.get("evidence", []))
        if evidence_count:
            action = "ENOUGH"
        elif state.get("allow_web_search") and state.get("current_round", 0) == 0:
            action = "NEED_WEB"
        elif state.get("current_round", 0) + 1 < state["max_rounds"]:
            action = "MORE_INTERNAL"
        else:
            action = "ENOUGH"
        evaluation, _ = await runtime.model_for(state["run_id"]).structured(
            evidence_evaluation_prompt(
                state["goal"], evidence_count, state.get("output_language", "zh-CN")
            ),
            EvidenceEvaluation,
        )
        # The routing decision is rule-constrained; the model cannot widen the
        # tenant scope or invent a tool path.
        evaluation.next_action = action
        evaluation.sufficient = action == "ENOUGH" and evidence_count > 0
        if not evidence_count:
            evaluation.missing = ["缺少可引用的项目资料"]
        await done(
            state, "EVALUATE_EVIDENCE", "Analyst 评估证据充分性", f"下一步：{action}"
        )
        return {"evaluation": evaluation.model_dump()}

    async def rewrite_query(state: ResearchState) -> dict:
        await checkpoint(state, "REWRITE_QUERY", "Query Agent 改写检索问题")
        round_no = state.get("current_round", 0) + 1
        query = f"{state['goal']} 关键指标、限制条件、原始依据"
        await done(state, "REWRITE_QUERY", "Query Agent 改写检索问题", query)
        return {"queries": [query], "current_round": round_no}

    async def search_web(state: ResearchState) -> dict:
        await checkpoint(state, "SEARCH_WEB", "Researcher 检索外部来源")
        if not state.get("allow_web_search"):
            await done(
                state, "SEARCH_WEB", "Researcher 检索外部来源", "调用方未授权，已跳过"
            )
            return {}
        web_items = await runtime.web_search_for(state["run_id"]).search(
            state["goal"], top_k=5
        )
        merged = [Evidence.model_validate(item) for item in web_items]
        await done(
            state,
            "SEARCH_WEB",
            "Researcher 检索外部来源",
            f"获得 {len(merged)} 条外部证据",
        )
        await runtime.events.publish(
            state["run_id"],
            "evidence.added",
            {
                "count": len(merged),
                "source": "web",
                "items": [item.model_dump() for item in merged],
            },
        )
        unique: dict[str, Evidence] = {
            item.id: item
            for item in (
                Evidence.model_validate(raw) for raw in state.get("evidence", [])
            )
        }
        unique.update({item.id: item for item in merged})
        return {
            "evidence": [
                item.model_dump()
                for item in list(unique.values())[: state.get("max_evidence", 12)]
            ]
        }

    async def synthesize_findings(state: ResearchState) -> dict:
        await checkpoint(state, "SYNTHESIZE_FINDINGS", "Analyst 形成带引用发现")
        evidence = [Evidence.model_validate(item) for item in state.get("evidence", [])]
        if not evidence:
            finding = Finding(
                id="F1",
                kind="gap",
                statement="当前项目资料不足以支持可靠结论。",
                evidence_ids=[],
                confidence=1.0,
            )
        else:
            finding, _ = await runtime.model_for(state["run_id"]).structured(
                finding_prompt(
                    state["goal"],
                    [item.model_dump() for item in evidence],
                    state.get("output_language", "zh-CN"),
                ),
                Finding,
            )
            valid_ids = {item.id for item in evidence}
            finding.evidence_ids = [
                item for item in finding.evidence_ids if item in valid_ids
            ]
        await done(state, "SYNTHESIZE_FINDINGS", "Analyst 形成带引用发现")
        await runtime.events.publish(
            state["run_id"],
            "finding.added",
            {"findingId": finding.id, "evidenceIds": finding.evidence_ids},
        )
        return {"findings": [finding.model_dump()]}

    async def write_report(state: ResearchState) -> dict:
        await checkpoint(state, "WRITE_REPORT", "Writer 撰写研究报告")
        evidence = [Evidence.model_validate(item) for item in state.get("evidence", [])]
        valid_ids = {item.id for item in evidence}
        draft, _ = await runtime.model_for(state["run_id"]).structured(
            report_prompt(
                state["goal"],
                state.get("findings", []),
                [item.model_dump() for item in evidence],
                state.get("output_language", "zh-CN"),
            ),
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
        await done(state, "WRITE_REPORT", "Writer 撰写研究报告")
        await runtime.events.publish(
            state["run_id"], "report.generated", {"title": draft.title}
        )
        return {"report_draft": draft.model_dump()}

    async def review_report(state: ResearchState) -> dict:
        await checkpoint(state, "REVIEW_REPORT", "Reviewer 审核引用与边界")
        draft = state.get("report_draft") or {}
        valid_ids = {item["id"] for item in state.get("evidence", [])}
        referenced = set(draft.get("evidence_ids", []))
        for section in draft.get("sections", []):
            referenced.update(section.get("evidence_ids", []))
        invalid = sorted(referenced - valid_ids)
        review, _ = await runtime.model_for(state["run_id"]).structured(
            review_prompt(
                sorted(referenced),
                sorted(valid_ids),
                state.get("output_language", "zh-CN"),
            ),
            ReviewResult,
        )
        review.missing_citations = invalid
        review = apply_review_guards(
            review, draft, state.get("evidence", []), state.get("review_policy")
        )
        await done(
            state,
            "REVIEW_REPORT",
            "Reviewer 审核引用与边界",
            "通过" if review.approved else "需要重写",
        )
        return {
            "review_result": review.model_dump(),
            "review_attempts": state.get("review_attempts", 0) + 1,
        }

    async def persist_result(state: ResearchState) -> dict:
        await checkpoint(state, "PERSIST_RESULT", "保存研究结果")
        await done(state, "PERSIST_RESULT", "保存研究结果")
        return {}

    def evidence_route(state: ResearchState) -> str:
        return state.get("evaluation", {}).get("next_action", "ENOUGH")

    def review_route(state: ResearchState) -> str:
        if (
            state.get("review_result", {}).get("approved")
            or state.get("review_attempts", 0) >= 2
        ):
            return "persist_result"
        return "write_report"

    graph = StateGraph(ResearchState)
    graph.add_node("validate_input", validate_input)
    graph.add_node("plan", plan)
    graph.add_node("retrieve_internal", retrieve_internal)
    graph.add_node("evaluate_evidence", evaluate_evidence)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("search_web", search_web)
    graph.add_node("synthesize_findings", synthesize_findings)
    graph.add_node("write_report", write_report)
    graph.add_node("review_report", review_report)
    graph.add_node("persist_result", persist_result)
    graph.add_edge(START, "validate_input")
    graph.add_edge("validate_input", "plan")
    graph.add_edge("plan", "retrieve_internal")
    graph.add_edge("retrieve_internal", "evaluate_evidence")
    graph.add_conditional_edges(
        "evaluate_evidence",
        evidence_route,
        {
            "ENOUGH": "synthesize_findings",
            "MORE_INTERNAL": "rewrite_query",
            "NEED_WEB": "search_web",
        },
    )
    graph.add_edge("rewrite_query", "retrieve_internal")
    graph.add_edge("search_web", "synthesize_findings")
    graph.add_edge("synthesize_findings", "write_report")
    graph.add_edge("write_report", "review_report")
    graph.add_conditional_edges(
        "review_report",
        review_route,
        {"persist_result": "persist_result", "write_report": "write_report"},
    )
    graph.add_edge("persist_result", END)
    return graph.compile(checkpointer=checkpointer)
