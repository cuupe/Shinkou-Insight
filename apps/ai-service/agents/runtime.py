from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from agents.contracts import AgentContext, AgentMessage, AgentResult
from agents.coordinator import AgentCoordinator, RunCancelled
from agents.model_router import AgentModelRouter
from agents.remote import RemoteAgentTransport
from core.events import EventBus
from core.repository import InMemoryRunRepository, RunRecord
from models.llm import ModelGateway, build_model_gateway
from models.schemas import Evidence, ExecuteRunRequest, ResearchConfig, RuntimeModelConfig, RuntimeWebSearchConfig
from prompts.agent_prompts import PROMPTS
from rag.retriever import Retriever
from tools.registry import ToolRegistry
from tools.web import BraveWebSearch, WebSearchProvider

logger = logging.getLogger(__name__)


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
            prompt_snapshot=PROMPTS.snapshot(request.config.system_prompts),
        )
        return await self.repository.create(run)

    async def execute(self, request: ExecuteRunRequest) -> None:
        run = self.repository.get(request.run_id) or await self.accept(request)
        if run.status == "COMPLETED":
            return
        await self.repository.update(run.run_id, status="RUNNING", current_node="VALIDATE_INPUT", current_step="开始执行", progress=1)
        await self.events.publish(run.run_id, "run.started", {"status": "RUNNING"})
        state = {
            "run_id": run.run_id,
            "workspace_id": request.workspace_id,
            "project_id": request.project_id,
            "user_id": request.user_id,
            "goal": request.goal,
            "output_language": request.config.output_language,
            "allow_web_search": request.config.allow_web_search,
            "max_rounds": request.config.max_research_rounds,
            "top_k": request.config.top_k,
            "retrieval_mode": request.config.retrieval_mode,
            "use_reranker": request.config.use_reranker,
            "tool_max_calls": request.config.tool_max_calls,
            "require_tool_approval": request.config.require_tool_approval,
            "system_prompts": request.config.system_prompts,
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
            self._run_models[run.run_id] = self._build_run_model(request.runtime_model)
            self._run_web_search[run.run_id] = self._build_run_web_search(request.runtime_web_search)
            result = await self.coordinator.run(
                state,
                model=self.model_for(run.run_id),
                web_search=self.web_search_for(run.run_id),
            )
            evidence = [Evidence.model_validate(item) for item in result.get("evidence", [])]
            await self.repository.add_evidence(run.run_id, evidence)
            await self.repository.update(run.run_id, status="COMPLETED", current_node="END", current_step="已完成", progress=100, report=result.get("report_draft"), token_count=0)
            await self.events.publish(run.run_id, "run.completed", {"status": "COMPLETED", "report": result.get("report_draft"), "promptSnapshot": result.get("prompt_snapshot", PROMPTS.snapshot(request.config.system_prompts))})
            await self._callback(request, {"status": "COMPLETED", "projectId": request.project_id, "userId": request.user_id, "report": result.get("report_draft")})
        except RunCancelled:
            await self.repository.update(run.run_id, status="CANCELLED", current_node="CANCELLED", current_step="已取消", progress=100)
            await self.events.publish(run.run_id, "run.cancelled", {"status": "CANCELLED"})
            await self._callback(request, {"status": "CANCELLED", "projectId": request.project_id, "userId": request.user_id})
        except Exception as exc:  # graph boundary: persist failure and close stream
            logger.exception("agent run failed", extra={"run_id": run.run_id})
            message = str(exc)[:1000] or "agent run failed"
            await self.repository.update(run.run_id, status="FAILED", current_node="FAILED", current_step="执行失败", error_message=message)
            await self.events.publish(run.run_id, "run.failed", {"status": "FAILED", "message": message})
            await self._callback(request, {"status": "FAILED", "projectId": request.project_id, "userId": request.user_id, "errorMessage": message})
        finally:
            self.tools.clear_run(run.run_id)
            self._run_models.pop(run.run_id, None)
            self._run_web_search.pop(run.run_id, None)
            await self.events.close(run.run_id)
            if relay_task:
                await relay_task

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
            timeout_seconds=config.timeout_seconds,
            max_retries=config.retries,
            structured_output_method=config.structured_output_method,
            generation=config.generation,
        )

    def web_search_for(self, run_id: str | int) -> WebSearchProvider:
        return self._run_web_search.get(str(run_id), self.web_search)

    def _build_run_web_search(self, config: RuntimeWebSearchConfig | None) -> WebSearchProvider:
        if config is None:
            return self.web_search
        if self.callback_client is None:
            raise RuntimeError("runtime web search requires a shared HTTP client")
        if config.provider.lower() != "brave":
            raise RuntimeError("runtime web search provider must be brave")
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
