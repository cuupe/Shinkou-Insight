from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
import time
from typing import Any

import httpx

from agents.contracts import AgentContext, AgentMessage, AgentResult
from agents.coordinator import AgentCoordinator, RunCancelled
from agents.model_router import AgentModelRouter
from agents.remote import RemoteAgentTransport
from core.events import EventBus, utc_now
from core.repository import InMemoryRunRepository, RunRecord
from models.llm import ModelGateway, ModelStreamChunk, build_model_gateway
from models.schemas import AgentPlan, Evidence, ExecuteRunRequest, ModelChatResult, ModelGenerationConfig, ReActAction, ReflectionResult, ResearchConfig, RuntimeModelConfig, RuntimeWebSearchConfig, TokenUsage
from prompts.agent_prompts import PROMPTS, plan_and_solve_prompt, react_action_prompt, reflection_prompt
from rag.retriever import Retriever
from tools.registry import ToolRegistry
from tools.web import DEFAULT_DUCKDUCKGO_BASE_URL, BraveWebSearch, DuckDuckGoWebSearch, WebSearchProvider

logger = logging.getLogger(__name__)


def _compact_chat_context(messages: list[dict[str, str]], max_chars: int = 24_000) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Compress old turns deterministically so compression never costs another model call."""

    normalized = [
        {"role": str(message.get("role", "user")), "content": str(message.get("content", "")).strip()}
        for message in messages
        if str(message.get("content", "")).strip()
    ]
    original_chars = sum(len(message["content"]) for message in normalized)
    if original_chars <= max_chars:
        return normalized, {
            "originalChars": original_chars,
            "finalChars": original_chars,
            "compressedMessages": 0,
            "originalTokenEstimate": max(0, original_chars // 4),
            "finalTokenEstimate": max(0, original_chars // 4),
            "finalMessageCount": len(normalized),
        }

    recent_count = 8
    recent = normalized[-recent_count:]
    recent_budget = max(4_000, max_chars - 6_000)
    bounded_recent: list[dict[str, str]] = []
    remaining_recent = recent_budget
    for message in reversed(recent):
        if remaining_recent <= 0:
            break
        content = message["content"]
        limit = min(len(content), remaining_recent)
        bounded_recent.append(
            {
                "role": message["role"],
                "content": content[:limit] + ("\n[本条消息已截断]" if limit < len(content) else ""),
            }
        )
        remaining_recent -= limit
    recent = list(reversed(bounded_recent))
    older = normalized[:-recent_count]
    older_count = len(older)
    recent_chars = sum(len(message["content"]) for message in recent)
    summary_budget = max(600, min(6_000, max_chars - recent_chars - 80))
    summary_lines: list[str] = []
    summary_chars = 0
    for message in older:
        excerpt = " ".join(message["content"].split())[:240]
        line = f"{message['role']}: {excerpt}"
        if summary_chars + len(line) + 1 > summary_budget:
            break
        summary_lines.append(line)
        summary_chars += len(line) + 1
    summary = {
        "role": "system",
        "content": (
            f"[上下文已自动压缩：保留最近 {len(recent)} 条消息，"
            f"较早 {older_count} 条仅保留摘要；完整内容仍在对话记录中。]\n"
            + "\n".join(summary_lines)
        ),
    }
    compacted = [summary, *recent]
    final_chars = sum(len(message["content"]) for message in compacted)
    return compacted, {
        "originalChars": original_chars,
        "finalChars": final_chars,
        "compressedMessages": older_count,
        "originalTokenEstimate": max(0, original_chars // 4),
        "finalTokenEstimate": max(0, final_chars // 4),
        "finalMessageCount": len(compacted),
    }


def _chat_context_limit(request: ExecuteRunRequest) -> int:
    generation = request.runtime_model.generation if request.runtime_model else request.config.generation
    context_window = int(generation.context_window if generation else 128_000)
    max_tokens = int(generation.max_tokens if generation else 4_096)
    # Keep a small, bounded prompt even when the provider advertises a very large window.
    return max(8_000, min(24_000, (context_window - max_tokens - 512) * 4))


_FOLLOW_UP_SEARCH_HINTS = (
    "我允许你联网", "允许你联网", "可以联网了", "联网了", "现在告诉我答案", "告诉我答案",
    "继续回答", "回答刚才", "回答上一个", "前面那个问题", "刚才那个问题", "再试一次", "重新回答",
)
_EXPLICIT_SEARCH_HINTS = ("查一下", "搜索", "检索", "查找", "查证", "搜一下")
_PROJECT_CONTEXT_HINTS = (
    "项目", "本项目", "当前项目", "工作区", "知识库", "资料", "文档", "文件", "附件",
    "代码", "仓库", "配置", "需求", "架构", "接口", "数据库", "日志", "规范", "方案",
    "设计", "报告", "部署", "环境", "依据", "引用", "来源", "上面的", "这个文件",
    "project", "workspace", "knowledge base", "document", "file", "attachment", "code",
    "repository", "config", "requirement", "architecture", "api", "database", "log",
    "spec", "design", "report", "deployment", "source", "citation", "according to",
)
_BROAD_RESEARCH_HINTS = (
    "全面", "详细", "尽可能", "所有", "各方面", "比较", "对比", "评估", "风险", "优缺点",
    "方案", "架构", "迁移", "排查", "总结", "研究", "compare", "evaluate", "trade-off",
)

_CHAT_STRATEGY_VALUES = {"DIRECT", "REACT", "PLAN_AND_SOLVE", "REFLECTION"}


def _select_chat_strategy(request: ExecuteRunRequest, question: str | None = None) -> str:
    """Choose the smallest workflow that matches the current chat request.

    The automatic router is deliberately deterministic and cheap. It only
    chooses the workflow; all tool calls remain bounded by the run's tool
    budget and the selected workflow's step limit.
    """

    requested = str(request.config.strategy or "AUTO").upper()
    if requested in _CHAT_STRATEGY_VALUES:
        return requested

    normalized = re.sub(r"\s+", "", str(question if question is not None else request.goal).casefold())
    broad_request = any(hint in normalized for hint in _BROAD_RESEARCH_HINTS)
    broad_request = broad_request or len(normalized) > 120 or normalized.count("?") + normalized.count("？") > 1
    if broad_request:
        return "PLAN_AND_SOLVE"

    quality_sensitive = any(hint in normalized for hint in _REFLECTION_HINTS)
    needs_project_context = _should_search_knowledge(normalized)
    if quality_sensitive and (needs_project_context or len(normalized) > 36):
        return "REFLECTION"
    if needs_project_context or request.config.allow_web_search:
        return "REACT"
    if quality_sensitive:
        return "REFLECTION"
    return "DIRECT"


def _chat_context_text(request: ExecuteRunRequest) -> str:
    return "\n".join(
        f"{message.role}: {message.content.strip()[:2_000]}"
        for message in request.context_messages[-8:]
        if message.content.strip()
    )[:8_000]


def _should_search_knowledge(question: str) -> bool:
    """Decide whether a chat turn needs project retrieval before generation.

    Chat is intentionally not a research workflow. Retrieval is useful for
    project-specific claims, but it should not be a mandatory tax on greetings,
    simple explanations, or other direct questions.
    """

    normalized = re.sub(r"\s+", "", str(question or "").casefold())
    if not normalized:
        return False
    if any(hint in normalized for hint in _EXPLICIT_SEARCH_HINTS):
        return True
    if any(hint in normalized for hint in _PROJECT_CONTEXT_HINTS):
        return True
    if re.fullmatch(r"[\d\s+\-*/().=?]+", normalized):
        return False
    return False


def _chat_retrieval_limit(question: str, requested: int, maximum: int) -> int:
    """Keep routine project questions focused while honoring broad requests."""

    limit = max(1, min(int(requested), int(maximum)))
    normalized = re.sub(r"\s+", "", str(question or "").casefold())
    if any(hint in normalized for hint in _BROAD_RESEARCH_HINTS):
        return limit
    return min(limit, 3)


def _web_search_query(request: ExecuteRunRequest) -> str:
    """Use the unresolved user question for permission/continuation follow-ups."""

    current = request.goal.strip()
    previous_user_messages = [
        message.content.strip()
        for message in request.context_messages
        if message.role == "user" and message.content.strip()
    ]
    if not previous_user_messages:
        return current

    normalized = re.sub(r"\s+", "", current.casefold())
    is_follow_up = any(hint in normalized for hint in _FOLLOW_UP_SEARCH_HINTS)
    if not is_follow_up:
        return current
    if any(hint in normalized for hint in _EXPLICIT_SEARCH_HINTS):
        return current
    return previous_user_messages[-1]


_RECENCY_HINTS = (
    "\u6700\u65b0",
    "\u6700\u8fd1",
    "\u76ee\u524d",
    "\u5f53\u524d",
    "latest",
    "recent",
    "newest",
    "current",
)


def _augment_web_search_query(query: str) -> str:
    """Give recency-sensitive searches a current, source-oriented query."""

    normalized = query.casefold()
    if not any(hint in normalized for hint in _RECENCY_HINTS):
        return query
    if re.search(r"\b20\d{2}\b", query):
        return query
    current_year = date.today().year
    return f"{query} {current_year} {current_year - 1} \u5b98\u65b9 \u53d1\u5e03 official release"


def _should_search_web(question: str) -> bool:
    """Recognize an explicit or time-sensitive request for external sources."""

    normalized = re.sub(r"\s+", "", str(question or "").casefold())
    if not normalized:
        return False
    return any(hint in normalized for hint in _EXPLICIT_SEARCH_HINTS + _RECENCY_HINTS)


def _evidence_message(evidence: list[Evidence], query: str = "") -> dict[str, str]:
    if not evidence:
        return {
            "role": "system",
            "content": (
                f"本次围绕“{query[:200]}”没有检索到可引用的项目资料或网页。请明确区分已知信息与待核验假设，"
                "不要编造来源。"
            ),
        }
    lines = [
        f"以下是围绕“{query[:200]}”检索得到的资料记录。只把它们当作待人工判断的来源，不要自动写入知识库。",
        "只有来源明确支持回答中的事实时才能使用 [来源ID] 标注；请把标注紧跟在对应事实句或段落末尾，不要把多个来源序号集中放在文章最后，也不要单独输出引用清单。无关或不足的来源不得引用，资料不足时直接说明。",
    ]
    for item in evidence:
        source = f"{item.source_name}{f' ({item.url})' if item.url else ''}"
        lines.append(f"[{item.id}] {source}\n{item.content[:2_000]}")
    return {"role": "system", "content": "\n\n".join(lines)}


_REFLECTION_HINTS = (
    "比较", "对比", "选择", "方案", "分析", "评估", "风险", "影响", "优缺点", "选型",
    "规划", "研究", "总结", "解释", "说明", "为什么", "如何", "排查", "修复", "性能",
    "安全", "成本", "迁移", "最新", "详细", "代码", "决策", "compare", "analyse", "analyze",
    "recommend", "architecture", "risk", "trade-off", "why", "how", "explain",
)


def _reflection_decision(
    request: ExecuteRunRequest,
    evidence: list[Evidence],
    draft: ModelChatResult,
    strategy: str = "AUTO",
) -> tuple[bool, str]:
    """Run one extra quality pass only when the question benefits from it.

    This is intentionally a small, deterministic policy. It does not inspect
    or expose hidden model reasoning and avoids spending another model call on
    short, direct questions.
    """

    if strategy == "REFLECTION":
        return True, "按当前设置执行一次回答质量检查"
    if strategy == "DIRECT":
        return False, "当前问题适合直接回答，跳过额外检查以节省 token"
    if not request.config.reflection_enabled:
        return False, "已关闭回答质量检查，直接发送初稿"

    question = request.goal.strip().casefold()
    has_complexity_hint = any(hint in question for hint in _REFLECTION_HINTS)
    complex_context = len(request.context_messages) > 6
    long_question = len(question) > 48
    evidence_needs_check = len(evidence) >= 3
    long_draft = len(draft.content.strip()) > 900
    if has_complexity_hint or complex_context or long_question or evidence_needs_check or long_draft:
        return True, "问题较复杂，执行一次回答自检"
    return False, "问题较简单，跳过额外自检以节省 token"


def _aggregate_usage(results: list[Any]) -> TokenUsage:
    """Account for the draft, reflection, and optional revision as one run."""

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    usages: list[TokenUsage] = []
    models: list[str] = []
    for result in results:
        usage = getattr(result, "usage", None)
        if usage is None:
            continue
        usages.append(usage)
        model = getattr(result, "model", None) or getattr(usage, "model", None)
        if model and str(model) not in models:
            models.append(str(model))
        input_tokens += max(0, int(usage.input_tokens or 0))
        output_tokens += max(0, int(usage.output_tokens or 0))
        total_tokens += max(0, int(usage.total_tokens or 0)) or (
            max(0, int(usage.input_tokens or 0)) + max(0, int(usage.output_tokens or 0))
        )
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=models[0] if len(models) == 1 else ("、".join(models) if models else None),
        available=bool(usages) and all(bool(usage.available) for usage in usages),
        estimated=any(bool(usage.estimated) for usage in usages),
    )


class AgentRuntime:
    """Application service coordinating independent agents and run events."""

    def __init__(self, *, model: ModelGateway, retriever: Retriever, web_search: WebSearchProvider, tools: ToolRegistry, repository: InMemoryRunRepository, events: EventBus, internal_api_key: str = "", max_evidence: int = 12, callback_client: httpx.AsyncClient | None = None, max_retries: int = 2, structured_output_method: str = "json_schema", agent_worker_urls: dict[str, str] | None = None, agent_worker_role: str | None = None):
        self.model = model
        self.retriever = retriever
        self.web_search = web_search
        self.tools = tools
        self.repository = repository
        self.events = events
        self.internal_api_key = internal_api_key
        self.max_evidence = max_evidence
        self.callback_client = callback_client
        self.max_retries = max_retries
        self.structured_output_method = structured_output_method
        self._run_models: dict[str, ModelGateway] = {}
        self._run_web_search: dict[str, WebSearchProvider] = {}
        self.agent_worker_role = agent_worker_role
        remote = (
            RemoteAgentTransport(
                worker_urls=agent_worker_urls or {},
                client=callback_client,
                internal_api_key=internal_api_key,
            )
            if agent_worker_urls and callback_client
            else None
        )
        self.coordinator = AgentCoordinator(
            repository=repository,
            events=events,
            max_evidence=max_evidence,
            remote=remote,
        )
        self.agent_registry = self.coordinator.registry

    def is_cancelled(self, run_id: str) -> bool:
        return self.repository.is_cancelled(run_id)

    async def accept(self, request: ExecuteRunRequest) -> RunRecord:
        run = RunRecord(
            run_id=str(request.run_id),
            workspace_id=request.workspace_id,
            project_id=request.project_id,
            user_id=request.user_id,
            goal=request.goal,
            config=request.config.model_dump(),
            prompt_snapshot=PROMPTS.snapshot(),
        )
        return await self.repository.create(run)

    async def execute(self, request: ExecuteRunRequest) -> None:
        run = self.repository.get(request.run_id) or await self.accept(request)
        if run.status == "COMPLETED":
            return
        started_at = time.perf_counter()
        started_timestamp = utc_now()
        await self.repository.update(run.run_id, status="RUNNING", current_node="VALIDATE_INPUT", current_step="开始执行", progress=1)
        await self.events.publish(run.run_id, "run.started", {"status": "RUNNING", "startedAt": started_timestamp})
        state = {
            "run_id": run.run_id,
            "workspace_id": request.workspace_id,
            "project_id": request.project_id,
            "user_id": request.user_id,
            "goal": request.goal,
            "strategy": request.config.strategy,
            "output_language": request.config.output_language,
            "allow_web_search": request.config.allow_web_search,
            "max_rounds": request.config.max_research_rounds,
            "top_k": request.config.top_k,
            "retrieval_mode": request.config.retrieval_mode,
            "use_reranker": request.config.use_reranker,
            "tool_max_calls": request.config.tool_max_calls,
            "require_tool_approval": request.config.require_tool_approval,
            "embedding_config": request.runtime_embedding.model_dump() if request.runtime_embedding else None,
            "runtime_model": request.runtime_model.model_dump() if request.runtime_model else None,
            "runtime_web_search": request.runtime_web_search.model_dump() if request.runtime_web_search else None,
            "max_evidence": self.max_evidence,
            "current_round": 0,
            "plan": [],
            "queries": [],
            "evidence": [],
            "findings": [],
            "errors": [],
            "review_attempts": 0,
            "prompt_snapshot": run.prompt_snapshot,
            "tools": self.tools,
        }
        self.tools.configure_run(run.run_id, max_calls=request.config.tool_max_calls)
        relay_task = asyncio.create_task(self._relay_events(request)) if request.callback else None
        try:
            model = self._build_run_model(request.runtime_model)
            if request.runtime_model is None and request.config.generation is not None:
                model = self._with_generation(model, request.config.generation)
            self._run_models[run.run_id] = model
            self._run_web_search[run.run_id] = self._build_run_web_search(request.runtime_web_search)
            if request.agent_message_id:
                await self._execute_chat(request, run, started_at, started_timestamp)
            else:
                result = await self.coordinator.run(
                    state,
                    model=self.model_for(run.run_id),
                    web_search=self.web_search_for(run.run_id),
                )
                evidence = [Evidence.model_validate(item) for item in result.get("evidence", [])]
                await self.repository.add_evidence(run.run_id, evidence)
                await self.repository.update(run.run_id, status="COMPLETED", current_node="END", current_step="已完成", progress=100, report=result.get("report_draft"), token_count=0)
                await self.events.publish(
                    run.run_id,
                    "run.completed",
                    {
                        "status": "COMPLETED",
                        "report": result.get("report_draft"),
                        "promptSnapshot": result.get("prompt_snapshot", PROMPTS.snapshot()),
                        "startedAt": started_timestamp,
                        "durationMs": int((time.perf_counter() - started_at) * 1000),
                    },
                )
                await self._callback(request, {"status": "COMPLETED", "projectId": request.project_id, "userId": request.user_id, "report": result.get("report_draft")})
        except RunCancelled:
            await self.repository.update(run.run_id, status="CANCELLED", current_node="CANCELLED", current_step="已取消", progress=100)
            await self.events.publish(
                run.run_id,
                "run.cancelled",
                {
                    "status": "CANCELLED",
                    "startedAt": started_timestamp,
                    "durationMs": int((time.perf_counter() - started_at) * 1000),
                },
            )
            await self._callback(request, {"status": "CANCELLED", "projectId": request.project_id, "userId": request.user_id})
        except Exception as exc:  # graph boundary: persist failure and close stream
            logger.exception("agent run failed", extra={"run_id": run.run_id})
            message = str(exc)[:1000] or "agent run failed"
            await self.repository.update(run.run_id, status="FAILED", current_node="FAILED", current_step="执行失败", error_message=message)
            await self.events.publish(
                run.run_id,
                "run.failed",
                {
                    "status": "FAILED",
                    "message": message,
                    "startedAt": started_timestamp,
                    "durationMs": int((time.perf_counter() - started_at) * 1000),
                },
            )
            await self._callback(request, {"status": "FAILED", "projectId": request.project_id, "userId": request.user_id, "errorMessage": message})
        finally:
            self.tools.clear_run(run.run_id)
            self._run_models.pop(run.run_id, None)
            self._run_web_search.pop(run.run_id, None)
            await self.events.close(run.run_id)
            if relay_task:
                await relay_task

    async def _stream_chat(
        self,
        request: ExecuteRunRequest,
        model: ModelGateway,
        messages: list[dict[str, str]],
        *,
        replace: bool = False,
    ) -> ModelChatResult:
        """Forward provider deltas to the run event bus as soon as they arrive."""

        message_id = str(request.agent_message_id or "")
        started_at = time.perf_counter()

        async def publish_usage(result: ModelChatResult) -> None:
            await self.events.publish(
                request.run_id,
                "usage.updated",
                {
                    "type": "usage.updated",
                    "runId": str(request.run_id),
                    "usage": result.usage.model_dump(),
                    "latencyMs": result.latency_ms,
                    "delta": True,
                },
            )

        if replace and message_id:
            await self.events.publish(
                request.run_id,
                "message.replace",
                {
                    "type": "message.replace",
                    "runId": str(request.run_id),
                    "messageId": message_id,
                    "content": "",
                },
            )

        stream = getattr(model, "stream", None)
        if not callable(stream):
            result = await model.chat(messages)
            if message_id and result.content:
                await self.events.publish(
                    request.run_id,
                    "message.delta",
                    {
                        "type": "message.delta",
                        "runId": str(request.run_id),
                        "messageId": message_id,
                        "delta": result.content,
                    },
                )
            await publish_usage(result)
            return result

        parts: list[str] = []
        usage: TokenUsage | None = None
        async for chunk in stream(messages):
            if isinstance(chunk, ModelStreamChunk):
                delta = chunk.delta
                if chunk.usage is not None:
                    usage = chunk.usage
            else:
                delta = str(chunk or "")
            if not delta:
                continue
            parts.append(delta)
            if message_id:
                await self.events.publish(
                    request.run_id,
                    "message.delta",
                    {
                        "type": "message.delta",
                        "runId": str(request.run_id),
                        "messageId": message_id,
                        "delta": delta,
                    },
                )

        content = "".join(parts)
        if not content.strip():
            raise RuntimeError("LLM returned empty content")
        if usage is None:
            usage = TokenUsage(available=False)
        result = ModelChatResult(
            content=content,
            model=getattr(model, "model", None),
            usage=usage,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
        )
        await publish_usage(result)
        return result

    async def _search_internal(
        self,
        request: ExecuteRunRequest,
        run: RunRecord,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[Evidence]:
        """Run one bounded project search and turn failures into observations."""

        if self.is_cancelled(run.run_id):
            raise RunCancelled()
        requested = top_k or _chat_retrieval_limit(query, request.config.top_k, self.max_evidence)
        await self.events.publish(
            run.run_id,
            "tool.started",
            {
                "tool": "search_knowledge",
                "query": query,
                "detail": f"正在查询项目资料，最多读取 {requested} 条相关来源",
            },
        )
        try:
            internal = await self.tools.execute(
                "search_knowledge",
                run_id=run.run_id,
                input_data={
                    "workspace_id": request.workspace_id,
                    "project_id": request.project_id,
                    "question": query,
                    "top_k": max(1, min(int(requested), self.max_evidence)),
                    "retrieval_mode": request.config.retrieval_mode,
                    "use_reranker": request.config.use_reranker,
                    "embedding_config": request.runtime_embedding.model_dump() if request.runtime_embedding else None,
                },
            )
            evidence = [Evidence.model_validate(item) for item in internal]
            await self.events.publish(
                run.run_id,
                "tool.completed",
                {
                    "tool": "search_knowledge",
                    "count": len(evidence),
                    "detail": "已找到与问题直接相关的项目资料" if evidence else "没有找到直接相关的项目资料",
                },
            )
            return evidence
        except Exception as exc:
            logger.warning("chat knowledge search failed", extra={"run_id": run.run_id, "error": str(exc)})
            detail = "项目资料检索失败，继续使用已有信息"
            if "timed out" in str(exc).casefold() or "timeout" in str(exc).casefold():
                detail = "项目资料检索超时，继续使用已有信息"
            await self.events.publish(
                run.run_id,
                "tool.completed",
                {"tool": "search_knowledge", "count": 0, "detail": detail},
            )
            return []

    async def _search_web(self, request: ExecuteRunRequest, run: RunRecord, query: str) -> list[Evidence]:
        """Run one explicitly permitted external search."""

        if self.is_cancelled(run.run_id):
            raise RunCancelled()
        web_query = _augment_web_search_query(query)
        await self.events.publish(
            run.run_id,
            "tool.started",
            {"tool": "web_search", "query": web_query, "detail": f"正在检索网页：{web_query[:120]}"},
        )
        try:
            external = [Evidence.model_validate(item) for item in await self.web_search_for(run.run_id).search(web_query, top_k=5)]
            await self.events.publish(
                run.run_id,
                "tool.completed",
                {
                    "tool": "web_search",
                    "count": len(external),
                    "detail": "已找到与问题直接相关的网页" if external else "未找到直接相关网页，已忽略无关结果",
                },
            )
            return external
        except Exception as exc:
            logger.warning("chat web search failed", extra={"run_id": run.run_id, "error": str(exc)})
            await self.events.publish(
                run.run_id,
                "tool.completed",
                {"tool": "web_search", "count": 0, "detail": "联网搜索不可用，未伪造结果"},
            )
            return []

    @staticmethod
    def _unique_evidence(evidence: list[Evidence], maximum: int) -> list[Evidence]:
        unique: dict[str, Evidence] = {}
        for item in evidence:
            unique.setdefault(item.id, item)
        return list(unique.values())[:maximum]

    async def _run_react(
        self,
        request: ExecuteRunRequest,
        run: RunRecord,
        search_query: str,
    ) -> tuple[list[Evidence], list[ModelChatResult]]:
        """Let the model choose bounded search actions and observe each result."""

        model = self.model_for(run.run_id)
        evidence: list[Evidence] = []
        model_results: list[ModelChatResult] = []
        observations: list[str] = []
        searched_queries: set[tuple[str, str]] = set()
        base_context = _chat_context_text(request)
        max_steps = min(4, max(2, request.config.max_research_rounds + 1))

        # Explicitly current/search-oriented wording is already a clear user
        # request, so seed the loop with that observation before asking for the
        # next action. This still keeps the final decision model-driven.
        if request.config.allow_web_search and _should_search_web(search_query):
            external = await self._search_web(request, run, search_query)
            evidence.extend(external)
            observations.append(f"网页搜索返回 {len(external)} 条来源")

        for step_number in range(1, max_steps + 1):
            if self.is_cancelled(run.run_id):
                raise RunCancelled()
            await self.events.publish(
                run.run_id,
                "node.started",
                {
                    "node": "SEARCH",
                    "title": "查找并核对资料",
                    "detail": f"正在判断第 {step_number} 步是否需要补充资料",
                    "agent": "react",
                    "step": step_number,
                    "strategy": "REACT",
                },
            )
            loop_context = base_context
            if observations:
                loop_context += "\n工具观察：\n" + "\n".join(observations[-4:])
            try:
                action, action_call = await model.structured(
                    react_action_prompt(
                        request.goal,
                        loop_context,
                        [item.model_dump() for item in self._unique_evidence(evidence, self.max_evidence)],
                        request.config.allow_web_search,
                        request.config.output_language,
                    ),
                    ReActAction,
                )
                model_results.append(action_call)
            except Exception as exc:
                logger.warning("chat action selection failed; using deterministic fallback", extra={"run_id": run.run_id, "error": str(exc)})
                if not evidence and _should_search_knowledge(search_query):
                    found = await self._search_internal(request, run, search_query)
                    evidence.extend(found)
                    observations.append(f"项目资料检索返回 {len(found)} 条来源")
                await self.events.publish(
                    run.run_id,
                    "node.completed",
                    {
                        "node": "SEARCH",
                        "title": "查找并核对资料",
                        "detail": "无法继续判断，已使用当前资料生成回答",
                        "agent": "react",
                        "step": step_number,
                        "strategy": "REACT",
                    },
                )
                break

            action_name = action.action
            query = (action.query or search_query).strip()[:2_000]
            if action_name == "FINAL":
                detail = "现有信息已足够，开始组织回答"
                observations.append("已判断无需继续查找资料")
                finished = True
            elif not query:
                detail = "没有生成有效查询，开始组织回答"
                observations.append("没有有效查询")
                finished = True
            else:
                key = (action_name, query.casefold())
                if key in searched_queries:
                    detail = "已使用相同查询，开始组织回答"
                    observations.append("相同查询已执行过")
                    finished = True
                elif action_name == "SEARCH_INTERNAL":
                    searched_queries.add(key)
                    found = await self._search_internal(request, run, query)
                    evidence.extend(found)
                    observations.append(f"项目资料检索返回 {len(found)} 条来源")
                    detail = f"已核对项目资料，获得 {len(found)} 条来源"
                    finished = False
                elif action_name == "SEARCH_WEB" and request.config.allow_web_search:
                    searched_queries.add(key)
                    found = await self._search_web(request, run, query)
                    evidence.extend(found)
                    observations.append(f"网页搜索返回 {len(found)} 条来源")
                    detail = f"已核对网页资料，获得 {len(found)} 条来源"
                    finished = False
                else:
                    detail = "当前未开启联网搜索，使用已有信息生成回答"
                    observations.append("联网搜索未开启")
                    finished = True

            await self.events.publish(
                run.run_id,
                "node.completed",
                {
                    "node": "SEARCH",
                    "title": "查找并核对资料",
                    "detail": detail,
                    "agent": "react",
                    "step": step_number,
                    "strategy": "REACT",
                    "action": action_name,
                },
            )
            if finished:
                break

        if not observations:
            observations.append("已使用当前对话信息")
        return self._unique_evidence(evidence, self.max_evidence), model_results

    async def _run_plan_and_solve(
        self,
        request: ExecuteRunRequest,
        run: RunRecord,
        search_query: str,
    ) -> tuple[list[Evidence], list[ModelChatResult]]:
        """Create and execute a short plan, then leave synthesis to the answer model."""

        model = self.model_for(run.run_id)
        evidence: list[Evidence] = []
        model_results: list[ModelChatResult] = []
        await self.events.publish(
            run.run_id,
            "node.started",
            {
                "node": "PLAN",
                "title": "整理处理步骤",
                "detail": "正在把问题拆成可执行的资料核对步骤",
                "agent": "planner",
                "strategy": "PLAN_AND_SOLVE",
            },
        )
        try:
            plan, plan_call = await model.structured(
                plan_and_solve_prompt(
                    request.goal,
                    _chat_context_text(request),
                    request.config.allow_web_search,
                    request.config.output_language,
                ),
                AgentPlan,
            )
            model_results.append(plan_call)
        except Exception as exc:
            logger.warning("chat plan generation failed; using deterministic fallback", extra={"run_id": run.run_id, "error": str(exc)})
            fallback_steps = []
            if _should_search_knowledge(search_query):
                fallback_steps.append({"id": "S1", "objective": "核对项目资料", "action": "SEARCH_INTERNAL", "query": search_query})
            if request.config.allow_web_search and _should_search_web(search_query):
                fallback_steps.append({"id": "S2", "objective": "核对外部资料", "action": "SEARCH_WEB", "query": search_query})
            fallback_steps.append({"id": "S3", "objective": "整理最终回答", "action": "SYNTHESIZE", "query": ""})
            plan = AgentPlan(summary="根据问题范围执行必要的资料核对", steps=fallback_steps)

        steps = plan.steps[:4]
        await self.events.publish(
            run.run_id,
            "node.completed",
            {
                "node": "PLAN",
                "title": "整理处理步骤",
                "detail": f"已整理 {len(steps)} 个步骤，接下来执行资料核对并生成回答",
                "agent": "planner",
                "strategy": "PLAN_AND_SOLVE",
                "stepCount": len(steps),
            },
        )
        searched_queries: set[tuple[str, str]] = set()
        for index, step in enumerate(steps, start=1):
            if self.is_cancelled(run.run_id):
                raise RunCancelled()
            action = step.action
            query = (step.query or search_query).strip()[:2_000]
            await self.events.publish(
                run.run_id,
                "node.started",
                {
                    "node": "PLAN",
                    "title": f"执行第 {index} 步",
                    "detail": step.objective[:300],
                    "agent": "planner",
                    "strategy": "PLAN_AND_SOLVE",
                    "step": index,
                },
            )
            detail = step.objective[:300]
            if action == "SYNTHESIZE":
                detail = "资料核对完成，开始组织最终回答"
            elif not query:
                detail = "缺少有效查询，跳过此步骤"
            else:
                key = (action, query.casefold())
                if key in searched_queries:
                    detail = "相同查询已完成，跳过重复步骤"
                elif action == "SEARCH_INTERNAL":
                    searched_queries.add(key)
                    found = await self._search_internal(request, run, query)
                    evidence.extend(found)
                    detail = f"已完成项目资料核对，获得 {len(found)} 条来源"
                elif action == "SEARCH_WEB" and request.config.allow_web_search:
                    searched_queries.add(key)
                    found = await self._search_web(request, run, query)
                    evidence.extend(found)
                    detail = f"已完成网页资料核对，获得 {len(found)} 条来源"
                else:
                    detail = "当前未开启联网搜索，跳过外部资料步骤"
            await self.events.publish(
                run.run_id,
                "node.completed",
                {
                    "node": "PLAN",
                    "title": f"执行第 {index} 步",
                    "detail": detail,
                    "agent": "planner",
                    "strategy": "PLAN_AND_SOLVE",
                    "step": index,
                    "action": action,
                },
            )
            if action == "SYNTHESIZE":
                break

        if not evidence and _should_search_knowledge(search_query):
            # A malformed or over-conservative plan must not silently answer a
            # project question without checking the project sources.
            evidence.extend(await self._search_internal(request, run, search_query))
        return self._unique_evidence(evidence, self.max_evidence), model_results

    async def _collect_initial_evidence(
        self,
        request: ExecuteRunRequest,
        run: RunRecord,
        search_query: str,
    ) -> list[Evidence]:
        evidence: list[Evidence] = []
        if _should_search_knowledge(search_query):
            evidence.extend(await self._search_internal(request, run, search_query))
        if request.config.allow_web_search and _should_search_web(search_query):
            evidence.extend(await self._search_web(request, run, search_query))
        return self._unique_evidence(evidence, self.max_evidence)

    async def _execute_chat(
        self,
        request: ExecuteRunRequest,
        run: RunRecord,
        started_at: float,
        started_timestamp: str,
    ) -> None:
        """Run an audited chat workflow selected for the current request."""

        search_query = _web_search_query(request)
        strategy = _select_chat_strategy(request, search_query)
        await self.repository.update(
            run.run_id,
            current_node="CHAT",
            current_step="确定回答路径",
            progress=10,
        )
        await self.events.publish(
            run.run_id,
            "node.started",
            {
                "node": "CHAT",
                "title": "确定回答路径",
                "detail": "正在根据问题范围和可用资料选择必要的处理步骤",
                "agent": "router",
                "strategy": strategy,
            },
        )
        await self.events.publish(
            run.run_id,
            "node.completed",
            {
                "node": "CHAT",
                "title": "确定回答路径",
                "detail": "已选择适合当前问题的处理路径",
                "agent": "router",
                "strategy": strategy,
            },
        )
        await self.events.publish(
            run.run_id,
            "node.started",
            {"node": "CHAT", "title": "生成回答", "agent": "chat"},
        )

        evidence: list[Evidence] = []
        model_results: list[ModelChatResult] = []
        should_search_project = _should_search_knowledge(search_query)
        if strategy in {"DIRECT", "REFLECTION"}:
            await self.events.publish(
                run.run_id,
                "node.started",
                {
                    "node": "SEARCH",
                    "title": "按需检查项目资料",
                    "agent": "retriever",
                    "skipped": not should_search_project and not _should_search_web(search_query),
                },
            )
            evidence = await self._collect_initial_evidence(request, run, search_query)
            await self.events.publish(
                run.run_id,
                "node.completed",
                {
                    "node": "SEARCH",
                    "title": "按需检查项目资料",
                    "detail": (
                        f"围绕“{search_query[:80]}”记录 {len(evidence)} 条相关来源"
                        if evidence or should_search_project
                        else "当前问题不依赖项目资料，未检索引用"
                    ),
                    "skipped": not evidence and not should_search_project and not _should_search_web(search_query),
                },
            )
        elif strategy == "REACT":
            evidence, model_results = await self._run_react(request, run, search_query)
        elif strategy == "PLAN_AND_SOLVE":
            evidence, model_results = await self._run_plan_and_solve(request, run, search_query)

        evidence = self._unique_evidence(evidence, self.max_evidence)
        if evidence:
            await self.events.publish(
                run.run_id,
                "evidence.added",
                {"count": len(evidence), "source": "chat", "items": [item.model_dump() for item in evidence]},
            )
        await self.events.publish(
            run.run_id,
            "node.started",
            {"node": "SYNTHESIS", "title": "组织回答", "detail": "正在结合对话与资料生成回答", "agent": "chat"},
        )

        context_messages = [message.model_dump() for message in request.context_messages]
        if evidence:
            context_messages.append(_evidence_message(evidence, search_query))
        else:
            context_messages.append(
                {
                    "role": "system",
                    "content": "本次没有可引用的额外资料。请直接回答，不要编造项目内部事实或引用；若问题依赖项目上下文，请明确说明。",
                }
            )
        context_messages.append({"role": "user", "content": request.goal})
        compacted_messages, compression = _compact_chat_context(
            context_messages,
            max_chars=_chat_context_limit(request),
        )
        model = self.model_for(run.run_id)
        draft = await self._stream_chat(request, model, compacted_messages)
        result = draft
        model_results.append(draft)
        should_reflect, reflection_reason = _reflection_decision(request, evidence, draft, strategy)
        if should_reflect:
            await self.events.publish(
                run.run_id,
                "node.started",
                {"node": "REFLECTION", "title": "回答质量检查", "agent": "reflection"},
            )
            reflection_payload: dict[str, Any] = {
                "node": "REFLECTION",
                "title": "回答质量检查",
                "agent": "reflection",
                "approved": False,
                "revised": False,
                "strategy": strategy,
            }
            try:
                reflection, reflection_call = await model.structured(
                    reflection_prompt(
                        request.goal,
                        draft.content,
                        [item.model_dump() for item in evidence],
                        request.config.output_language,
                    ),
                    ReflectionResult,
                )
                model_results.append(reflection_call)
                issues = [str(item).strip()[:500] for item in reflection.issues[:8] if str(item).strip()]
                corrections = [str(item).strip()[:500] for item in reflection.corrections[:8] if str(item).strip()]
                reflection_payload.update(
                    {
                        "approved": reflection.approved,
                        "confidence": reflection.confidence,
                        "issues": issues,
                        "corrections": corrections,
                    }
                )
                if not reflection.approved and (issues or corrections):
                    notes = "\n".join(
                        [*(f"- 问题：{item}" for item in issues), *(f"- 修正建议：{item}" for item in corrections)]
                    )
                    revision_messages = [
                        {
                            "role": "system",
                            "content": (
                                "你正在修正上一版项目聊天回答。以下是一次回答质量检查的结果，"
                                "它只是修改建议，不是新的事实来源。只使用原有上下文和证据，"
                                "不要补造事实、来源或引用。"
                                f"\nQuality notes:\n{notes[:4_000]}"
                            ),
                        },
                        *compacted_messages,
                        {"role": "user", "content": "请输出修正后的最终回答，不要解释修改过程。"},
                    ]
                    result = await self._stream_chat(request, model, revision_messages, replace=True)
                    model_results.append(result)
                    reflection_payload["revised"] = True
                    reflection_payload["detail"] = "发现问题，已完成一次修正"
                elif reflection.approved:
                    reflection_payload["detail"] = "检查通过，保留初稿"
                else:
                    reflection_payload["detail"] = "检查未给出可执行修正，保留初稿"
            except Exception as exc:
                # Quality checking must not turn a usable chat answer into a
                # failed run when a provider lacks structured output.
                logger.warning("chat quality check failed; keeping draft", extra={"run_id": run.run_id, "error": str(exc)})
                reflection_payload["detail"] = "质量检查不可用，保留初稿"
                reflection_payload["error"] = str(exc)[:300]
            await self.events.publish(run.run_id, "node.completed", reflection_payload)
        else:
            await self.events.publish(
                run.run_id,
                "node.completed",
                {
                    "node": "REFLECTION",
                    "title": "回答质量检查",
                    "agent": "reflection",
                    "approved": True,
                    "revised": False,
                    "skipped": True,
                    "detail": reflection_reason,
                    "strategy": strategy,
                },
            )

        await self.events.publish(
            run.run_id,
            "node.completed",
            {"node": "SYNTHESIS", "title": "组织回答", "detail": "已完成回答生成", "agent": "chat", "strategy": strategy},
        )

        usage = _aggregate_usage(model_results)
        await self.repository.update(
            run.run_id,
            status="COMPLETED",
            current_node="END",
            current_step="已完成",
            progress=100,
            report={"answer": result.content},
            token_count=usage.total_tokens,
        )
        await self.events.publish(
            run.run_id,
            "node.completed",
            {"node": "CHAT", "title": "生成回答", "agent": "chat", "strategy": strategy},
        )
        completion = {
            "status": "COMPLETED",
            "report": result.content,
            "usage": usage.model_dump(),
            "contextCompression": compression,
            "startedAt": started_timestamp,
            "durationMs": int((time.perf_counter() - started_at) * 1000),
            "strategy": strategy,
        }
        await self.events.publish(run.run_id, "run.completed", completion)
        await self._callback(
            request,
            {
                "status": "COMPLETED",
                "projectId": request.project_id,
                "userId": request.user_id,
                "report": result.content,
                "usage": usage.model_dump(),
                "contextCompression": compression,
                "startedAt": started_timestamp,
                "durationMs": completion["durationMs"],
                "strategy": strategy,
            },
        )

    async def close(self) -> None:
        await self.coordinator.bus.close()

    async def cancel(self, run_id: str | int) -> bool:
        return await self.repository.cancel(run_id)

    async def handle_agent_message(self, message: AgentMessage) -> AgentResult:
        """Execute one envelope when this process is deployed as an Agent Worker."""

        agent = self.agent_registry.get(message.recipient)
        runtime_model = RuntimeModelConfig.model_validate(message.payload["_runtime_model"]) if message.payload.get("_runtime_model") else None
        runtime_web_search = RuntimeWebSearchConfig.model_validate(message.payload["_runtime_web_search"]) if message.payload.get("_runtime_web_search") else None
        context = AgentContext(
            run_id=message.run_id,
            workspace_id=message.workspace_id,
            project_id=message.project_id,
            user_id=message.user_id,
            model_router=AgentModelRouter(self._build_run_model(runtime_model)),
            web_search=self._build_run_web_search(runtime_web_search),
            tools=self.tools,
            repository=self.repository,
            events=self.events,
            max_evidence=self.max_evidence,
        )
        raw_limit = message.payload.get("_tool_max_calls", 10)
        try:
            self.tools.configure_run(message.run_id, max_calls=int(raw_limit))
            return await agent.handle(message, context)
        finally:
            self.tools.clear_run(message.run_id)

    def run_config(self, request: ExecuteRunRequest) -> ResearchConfig:
        return request.config

    def model_for(self, run_id: str | int) -> ModelGateway:
        return self._run_models.get(str(run_id), self.model)

    def _build_run_model(self, config: RuntimeModelConfig | None) -> ModelGateway:
        if config is None:
            return self.model
        if self.callback_client is None:
            raise RuntimeError("runtime model requires a shared HTTP client")
        return build_model_gateway(
            mode="http",
            client=self.callback_client,
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            provider=config.provider,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.retries,
            structured_output_method=config.structured_output_method,
            generation=config.generation,
        )

    def _with_generation(self, model: ModelGateway, generation: ModelGenerationConfig) -> ModelGateway:
        """Apply one request's generation controls to the process default model."""
        with_generation = getattr(model, "with_generation", None)
        if callable(with_generation):
            return with_generation(generation)
        return model

    def web_search_for(self, run_id: str | int) -> WebSearchProvider:
        return self._run_web_search.get(str(run_id), self.web_search)

    def _build_run_web_search(self, config: RuntimeWebSearchConfig | None) -> WebSearchProvider:
        if config is None:
            return self.web_search
        if self.callback_client is None:
            raise RuntimeError("runtime web search requires a shared HTTP client")
        provider = config.provider.lower()
        if provider not in {"brave", "duckduckgo"}:
            raise RuntimeError("runtime web search provider must be brave or duckduckgo")
        if provider == "duckduckgo":
            return DuckDuckGoWebSearch(
                client=self.callback_client,
                base_url=config.base_url or DEFAULT_DUCKDUCKGO_BASE_URL,
                search_language=config.language,
            )
        return BraveWebSearch(
            client=self.callback_client,
            api_key=config.api_key,
            base_url=config.base_url,
            search_language=config.language,
        )

    async def _relay_events(self, request: ExecuteRunRequest) -> None:
        async for event in self.events.subscribe(request.run_id):
            await self._callback(
                request,
                {"eventType": event.event_type, "payload": event.payload},
            )

    async def _callback(self, request: ExecuteRunRequest, payload: dict[str, Any]) -> None:
        endpoint = (request.callback or {}).get("eventEndpoint") or (request.callback or {}).get("event_endpoint")
        if not endpoint:
            return
        try:
            if self.callback_client:
                await self.callback_client.post(endpoint, timeout=10, headers={"X-Internal-Api-Key": self.internal_api_key}, json={"runId": request.run_id, "workspaceId": request.workspace_id, "projectId": request.project_id, "userId": request.user_id, **payload})
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(endpoint, headers={"X-Internal-Api-Key": self.internal_api_key}, json={"runId": request.run_id, "workspaceId": request.workspace_id, "projectId": request.project_id, "userId": request.user_id, **payload})
        except Exception:
            logger.warning("agent callback failed", extra={"run_id": request.run_id}, exc_info=True)
