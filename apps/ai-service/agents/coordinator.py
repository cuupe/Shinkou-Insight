from __future__ import annotations

import hashlib
import json
from typing import Any

from agents.bus import AgentMessageBus
from agents.contracts import AgentContext
from agents.defaults import build_default_agent_registry
from agents.model_router import AgentModelRouter
from agents.registry import AgentRegistry
from agents.remote import RemoteAgentTransport
from core.events import EventBus
from core.repository import InMemoryRunRepository
from models.schemas import Evidence


class RunCancelled(Exception):
    pass


class AgentCoordinator:
    """Coordinates independent agents without exposing shared mutable state.

    The coordinator owns workflow policy. Agents own domain decisions and only
    exchange typed payloads through AgentMessageBus.
    """

    _progress = {
        "planner": 15,
        "internal_researcher": 35,
        "evidence_analyst": 48,
        "query_rewriter": 28,
        "web_researcher": 55,
        "finding_analyst": 68,
        "report_writer": 82,
        "report_reviewer": 92,
    }
    _event_nodes = {
        "planner": "PLAN",
        "internal_researcher": "RETRIEVE_INTERNAL",
        "evidence_analyst": "EVALUATE_EVIDENCE",
        "query_rewriter": "REWRITE_QUERY",
        "web_researcher": "SEARCH_WEB",
        "finding_analyst": "SYNTHESIZE_FINDINGS",
        "report_writer": "WRITE_REPORT",
        "report_reviewer": "REVIEW_REPORT",
    }

    def __init__(
        self,
        *,
        repository: InMemoryRunRepository,
        events: EventBus,
        registry: AgentRegistry | None = None,
        max_evidence: int = 12,
        remote: RemoteAgentTransport | None = None,
    ) -> None:
        self.repository = repository
        self.events = events
        self.registry = registry or build_default_agent_registry()
        self.bus = AgentMessageBus(self.registry, remote=remote)
        self.max_evidence = max_evidence

    async def run(self, initial_state: dict[str, Any], *, model: Any, web_search: Any) -> dict[str, Any]:
        state = dict(initial_state)
        run_id = str(state["run_id"])
        await self._checkpoint(run_id, "VALIDATE_INPUT", "校验研究上下文", 5)
        goal = str(state.get("goal", "")).strip()
        if not goal:
            raise ValueError("goal cannot be empty")
        if not state.get("workspace_id") or not state.get("project_id"):
            raise ValueError("workspace_id and project_id are required")
        state["goal"] = goal
        state["current_round"] = 0

        context = AgentContext(
            run_id=run_id,
            workspace_id=int(state["workspace_id"]),
            project_id=int(state["project_id"]),
            user_id=int(state.get("user_id", 0)),
            model_router=AgentModelRouter(model),
            web_search=web_search,
            tools=state["tools"],
            repository=self.repository,
            events=self.events,
            max_evidence=self.max_evidence,
        )

        generated_plan = await self._dispatch(
            context,
            state,
            "planner",
            "plan.create",
            {"goal": goal, "output_language": state.get("output_language", "zh-CN")},
            "Planner 拆解研究目标",
        )
        persisted = self.repository.get(run_id)
        if persisted and persisted.plan_version and persisted.plan:
            state["plan"] = list(persisted.plan.get("steps") or [])
            state["plan_version"] = persisted.plan_version
            state["queries"] = [str(item.get("query") or item.get("question") or "").strip() for item in state["plan"] if isinstance(item, dict) and (item.get("query") or item.get("question"))]
        else:
            state.update(generated_plan)
            initial_plan = {"summary": "系统根据研究目标生成的初始计划", "steps": list(state.get("plan") or [])}
            persisted = await self.repository.set_initial_plan(run_id, initial_plan)
            state["plan_version"] = persisted.plan_version
            await self.events.publish(run_id, "plan.created", {"plan": persisted.plan, "planVersion": persisted.plan_version})
        latest_source = str((persisted.plan_history[-1] if persisted and persisted.plan_history else {}).get("source") or "planner")
        state["_plan_fingerprints"] = {} if latest_source == "user" else {
            str(item.get("id")): self._plan_fingerprint(item)
            for item in (state.get("plan") or [])
            if isinstance(item, dict) and item.get("id")
        }

        while True:
            await self._refresh_dynamic_plan(context, state)
            research = await self._dispatch(
                context,
                state,
                "internal_researcher",
                "evidence.retrieve.internal",
                {
                    "goal": goal,
                    "queries": state.get("queries", []),
                    "evidence": state.get("evidence", []),
                    "top_k": state.get("top_k", 8),
                    "retrieval_mode": state.get("retrieval_mode", "HYBRID"),
                    "use_reranker": state.get("use_reranker", False),
                    "embedding_config": state.get("embedding_config"),
                },
                "Researcher 检索项目资料",
            )
            state.update(research)
            evaluation = await self._dispatch(
                context,
                state,
                "evidence_analyst",
                "evidence.evaluate",
                {
                    "goal": goal,
                    "evidence": state.get("evidence", []),
                    "current_round": state.get("current_round", 0),
                    "max_rounds": state.get("max_rounds", 3),
                    "allow_web_search": state.get("allow_web_search", False),
                    "output_language": state.get("output_language", "zh-CN"),
                    "review_policy": state.get("review_policy", {}),
                },
                "Analyst 评估证据充分性",
            )
            state.update(evaluation)
            action = state.get("evaluation", {}).get("next_action", "ENOUGH")
            if action == "MORE_INTERNAL":
                rewritten = await self._dispatch(
                    context,
                    state,
                    "query_rewriter",
                    "query.rewrite",
                    {
                        "goal": goal,
                        "current_round": state.get("current_round", 0),
                    },
                    "Query Agent 改写检索问题",
                )
                state.update(rewritten)
                continue
            if action == "NEED_WEB":
                external = await self._dispatch(
                    context,
                    state,
                    "web_researcher",
                    "evidence.retrieve.web",
                    {
                        "goal": goal,
                        "evidence": state.get("evidence", []),
                        "allow_web_search": state.get("allow_web_search", False),
                    },
                    "Researcher 检索外部来源",
                )
                state.update(external)
            break

        findings = await self._dispatch(
            context,
            state,
            "finding_analyst",
            "finding.synthesize",
            {
                "goal": goal,
                "evidence": state.get("evidence", []),
                "output_language": state.get("output_language", "zh-CN"),
            },
            "Analyst 形成带引用发现",
        )
        state.update(findings)

        for attempt in range(2):
            draft = await self._dispatch(
                context,
                state,
                "report_writer",
                "report.write",
                {
                    "goal": goal,
                    "findings": state.get("findings", []),
                    "evidence": state.get("evidence", []),
                    "output_language": state.get("output_language", "zh-CN"),
                    "review_attempt": attempt,
                    "review_result": state.get("review_result"),
                },
                "Writer 撰写研究报告",
                attempt=attempt,
            )
            state.update(draft)
            review = await self._dispatch(
                context,
                state,
                "report_reviewer",
                "report.review",
                {
                    "report_draft": state.get("report_draft"),
                    "evidence": state.get("evidence", []),
                    "output_language": state.get("output_language", "zh-CN"),
                    "review_policy": state.get("review_policy", {}),
                },
                "Reviewer 审核引用与边界",
                attempt=attempt,
            )
            state.update(review)
            state["review_attempts"] = attempt + 1
            if state.get("review_result", {}).get("approved"):
                break

        await self._checkpoint(run_id, "PERSIST_RESULT", "保存研究结果", 98)
        await self.events.publish(
            run_id,
            "node.completed",
            {"node": "PERSIST_RESULT", "title": "保存研究结果", "agent": "coordinator"},
        )
        return state

    async def _dispatch(
        self,
        context: AgentContext,
        state: dict[str, Any],
        recipient: str,
        intent: str,
        payload: dict[str, Any],
        title: str,
        *,
        attempt: int = 0,
    ) -> dict[str, Any]:
        await self._refresh_dynamic_plan(context, state)
        event_node = self._event_nodes.get(recipient, recipient.upper())
        await self._checkpoint(
            context.run_id,
            event_node,
            title,
            self._progress.get(recipient, 0),
        )
        dispatch_payload = dict(payload)
        if state.get("runtime_model"):
            dispatch_payload["_runtime_model"] = state["runtime_model"]
        if state.get("runtime_web_search"):
            dispatch_payload["_runtime_web_search"] = state["runtime_web_search"]
        if state.get("tool_max_calls") is not None:
            dispatch_payload["_tool_max_calls"] = state["tool_max_calls"]
        if state.get("disabled_tools"):
            dispatch_payload["_disabled_tools"] = state["disabled_tools"]
        result = await self.bus.request(
            run_id=context.run_id,
            sender="research_coordinator",
            recipient=recipient,
            intent=intent,
            payload=dispatch_payload,
            context=context,
            attempt=attempt,
        )
        if result.status != "SUCCEEDED":
            raise RuntimeError(result.error or f"agent failed: {recipient}")
        await self.events.publish(
            context.run_id,
            "node.completed",
            {"node": event_node, "title": title, "agent": recipient},
        )
        return result.payload

    @staticmethod
    def _plan_fingerprint(step: dict[str, Any]) -> str:
        encoded = json.dumps(step, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]

    async def _refresh_dynamic_plan(self, context: AgentContext, state: dict[str, Any]) -> None:
        """Apply plan changes at safe checkpoints and execute changed steps."""

        await self.repository.wait_if_paused(context.run_id)
        run = self.repository.get(context.run_id)
        if run is None or run.plan_version <= int(state.get("plan_version", 0)):
            return
        plan = list((run.plan or {}).get("steps") or [])
        fingerprints = state.setdefault("_plan_fingerprints", {})
        state["plan"] = plan
        state["plan_version"] = run.plan_version
        await self.events.publish(
            context.run_id,
            "plan.applied",
            {"plan": run.plan, "planVersion": run.plan_version},
        )
        for raw_step in plan:
            if not isinstance(raw_step, dict) or not raw_step.get("id"):
                continue
            step_id = str(raw_step["id"])
            fingerprint = self._plan_fingerprint(raw_step)
            if fingerprints.get(step_id) == fingerprint:
                continue
            await self._execute_dynamic_step(context, state, raw_step)
            fingerprints[step_id] = fingerprint

    async def _execute_dynamic_step(self, context: AgentContext, state: dict[str, Any], step: dict[str, Any]) -> None:
        action = str(step.get("action") or "SEARCH_INTERNAL").upper()
        query = str(step.get("query") or step.get("objective") or step.get("question") or "").strip()
        if action == "SYNTHESIZE" or not query:
            await self.events.publish(context.run_id, "plan.step.completed", {"stepId": step.get("id"), "action": action, "detail": "计划步骤已标记为整理阶段"})
            return
        evidence: list[Evidence] = []
        try:
            if action == "SEARCH_INTERNAL":
                raw = await context.tools.execute(
                    "search_knowledge",
                    run_id=context.run_id,
                    input_data={
                        "workspace_id": context.workspace_id,
                        "project_id": context.project_id,
                        "question": query,
                        "top_k": state.get("top_k", 8),
                        "retrieval_mode": state.get("retrieval_mode", "HYBRID"),
                        "use_reranker": state.get("use_reranker", False),
                        "embedding_config": state.get("embedding_config"),
                    },
                )
                evidence = [Evidence.model_validate(item) for item in raw]
            elif action == "SEARCH_WEB":
                if not state.get("allow_web_search"):
                    raise RuntimeError("联网搜索未授权")
                evidence = [Evidence.model_validate(item) for item in await context.web_search.search(query, top_k=state.get("top_k", 8))]
            elif action == "SEARCH_GRAPH":
                raw = await context.tools.execute(
                    "search_graph",
                    run_id=context.run_id,
                    input_data={"workspace_id": context.workspace_id, "project_id": context.project_id, "query": query, "limit": state.get("top_k", 8)},
                )
                for index, node in enumerate((raw or {}).get("nodes", []), start=1):
                    name = str(node.get("name") or node.get("key") or "实体")
                    properties = node.get("properties") or {}
                    evidence.append(Evidence(id=f"GP{step.get('id')}-{index}", chunk_id=f"plan-graph:{step.get('id')}-{index}", content=f"实体：{name}\n属性：{json.dumps(properties, ensure_ascii=False)}", source_name="项目知识图谱", source_type="graph"))
                for index, edge in enumerate((raw or {}).get("relationships", []), start=1):
                    evidence.append(Evidence(id=f"GR{step.get('id')}-{index}", chunk_id=f"plan-graph-edge:{step.get('id')}-{index}", content=f"关系：{edge.get('source')} -[{edge.get('relation')}]-> {edge.get('target')}", source_name="项目知识图谱", source_type="graph"))
            else:
                raise RuntimeError(f"不支持的计划动作：{action}")
        except Exception as exc:
            await self.events.publish(context.run_id, "plan.step.failed", {"stepId": step.get("id"), "action": action, "error": str(exc)[:300]})
            return
        unique = {str(item.get("id")): item for item in state.get("evidence", []) if isinstance(item, dict) and item.get("id")}
        unique.update({item.id: item.model_dump() for item in evidence})
        state["evidence"] = list(unique.values())[: self.max_evidence]
        await self.repository.add_evidence(context.run_id, evidence)
        await self.events.publish(
            context.run_id,
            "plan.step.completed",
            {"stepId": step.get("id"), "action": action, "query": query, "evidenceCount": len(evidence)},
        )

    async def _checkpoint(self, run_id: str, node: str, title: str, progress: int) -> None:
        await self.repository.wait_if_paused(run_id)
        if self.repository.is_cancelled(run_id):
            raise RunCancelled("run cancelled by caller")
        await self.repository.update(
            run_id,
            current_node=node,
            current_step=title,
            progress=progress,
        )
        await self.events.publish(
            run_id,
            "node.started",
            {"node": node, "title": title, "agent": node.lower()},
        )
        await self.events.publish(
            run_id,
            "run.progress",
            {"node": node, "progress": progress, "currentStep": title},
        )
