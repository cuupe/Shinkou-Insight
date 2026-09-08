# Shinkou Insight AI Service

## Production architecture

The service is a tenant-scoped multi-agent runtime, not a single chat handler:

- LangChain `ChatOpenAI`/Core adapters, prompt templates, and a versioned prompt registry with SHA-256 snapshots.
- Prompt-injection boundary for user/document data, structured Pydantic outputs, citation validation, and a small grounding evaluation module.
- Hybrid RAG: Milvus embeddings plus PostgreSQL full-text search, in-memory deterministic mode for CI, document parsers/chunking, object storage adapters, and optional Neo4j graph extraction.
- Replayable SSE run events, cancellation, Java callbacks, bounded tool execution, and optional MCP read-only extension tools.

## Runtime boundaries

- `config.py`: loads only the repository root `.env`; `.env.example` is documentation and is never read.
- `core/container.py`: the single composition root for LLM, embeddings, storage, PostgreSQL, graph, web search, tools, and lifecycle cleanup.
- `app.py`: HTTP boundary only; routes use dependencies exposed by the container.
- `agents/`: independent Agent contracts, registry, message bus, coordinator, and provider-free role implementations.
- `workflows/`: legacy graph compatibility and focused workflow experiments; production research runs use `AgentCoordinator`.
- `rag/`, `documents/`, `embeddings/`, `storage/`, and `tools/`: isolated adapters with explicit interfaces.

The production path is PostgreSQL + Milvus + MinIO + an OpenAI-compatible LLM/embedding provider. PostgreSQL stores source chunks and FTS metadata; Milvus stores filtered vector indexes. The in-memory knowledge adapter is empty by default and is reserved for tests or explicit local diagnostics.

## MCP

MCP is an extension boundary, not a replacement for the core registry. Run the optional read-only server with `MCP_TRANSPORT=streamable-http` for production or `stdio` for local desktop clients:

```powershell
cd apps/ai-service
MCP_TRANSPORT=streamable-http .\.venv\Scripts\python.exe mcp_server.py
```

The server exposes only `search_knowledge` and `search_graph`. Every call requires both `workspace_id` and `project_id`; the client bridge additionally supports an explicit tool allow-list, timeouts, and read-only registration. Enable the bridge in the main service with `MCP_ENABLED=true`, `MCP_URL`, and `MCP_ALLOWED_TOOLS`.

Prompt versions are defined in `prompts/registry.py`. Agent calls continue to use the compatibility functions in `prompts/agent_prompts.py`, so prompts can evolve independently from the Agent transport and orchestration layers.

这是研究型多智能体后端，不是单次聊天脚本。Java 后端负责登录、工作区/项目权限和业务数据；本服务只接受带 `workspace_id`、`project_id` 的内部请求，负责调度独立 Agent、检索、证据校验、报告生成和可回放事件流。

## 多智能体运行时

研究运行由 `AgentCoordinator` 负责策略编排，Agent 之间不共享可变的研究状态，而是通过 `AgentMessage` 和 `AgentResult` 契约通信。当前注册的 Agent 包括：

```text
Planner
  ├─ InternalResearcher ─┐
  ├─ WebResearcher       ├─ EvidenceAnalyst
  └─ QueryRewriter ──────┘
       ↓
FindingAnalyst → ReportWriter → ReportReviewer
```

`AgentMessageBus` 默认使用进程内队列，具备独立队列、worker、消息 ID、trace ID、重试 attempt 和 Agent 生命周期事件；设置 `AGENT_TRANSPORT=http` 并配置 `AGENT_WORKER_URLS=planner=http://planner-worker:8000,report_writer=http://writer-worker:8000` 后，可将指定 Agent 路由到独立进程。独立 Worker 设置 `AGENT_WORKER_ROLE=planner` 后只接受 Planner 消息。Agent 通过 `AgentRegistry` 注册，可单独替换模型、工具权限和实现；后续也可以把同一消息契约替换为 Redis Streams 或 NATS，而不改变 Agent 业务代码。

运维可通过 `GET /internal/agents` 查看运行时 Agent 清单。原有研究接口、SSE 事件和 Java 回调保持兼容；旧版 `workflows/qa_graph.py` 仅作为兼容和实验实现保留，生产执行路径已经切换到消息总线架构。

## 运行

```powershell
cd apps/ai-service
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

运行链路默认使用 LangChain 的 `ChatOpenAI` 适配器和 OpenAI-compatible Chat Completions API：设置 `LLM_MODE=http`；模型服务地址、模型 ID 和 API Key 由前端项目设置保存，Java 后端只在运行时将当前项目解析出的凭证注入本次请求。`LLM_STRUCTURED_OUTPUT_METHOD` 支持 `json_schema`、`function_calling` 和 `json_mode`，用于适配不同模型服务的结构化输出能力。设置 `EMBEDDING_MODE=openai` 和对应的 Embedding 配置接入真实向量模型。`LLM_MODE=mock` 仅允许在 `APP_ENV=test` 或 `ci` 下用于单元测试。

开发依赖和测试配置集中在 `pyproject.toml`，生产镜像使用 `requirements.txt`，本地质量检查可安装 `requirements-dev.txt` 后运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

## 工作流

`AgentCoordinator` 先向 `planner`、`internal_researcher` 和 `evidence_analyst` 分派消息；证据不足时路由到 `query_rewriter` 或 `web_researcher`，之后再分派 `finding_analyst → report_writer → report_reviewer`。所有 Agent 消息、分支、重试、取消和工具调用都会写入事件总线，SSE 支持 `Last-Event-ID` 回放。

## 内部接口

- `POST /internal/research/runs/{run_id}/execute`
- `POST /internal/research/runs/{run_id}/cancel`
- `GET /internal/research/runs/{run_id}/events`
- `POST /internal/knowledge/search`
- `POST /internal/knowledge/answer`
- `POST /internal/llm/chat`
- `POST /internal/llm/test`
- `GET /internal/agents`
- `POST /internal/agents/{agent_name}/messages`

请求必须带 `X-Internal-Api-Key`。默认使用 `DATABASE_URL` 指向 PostgreSQL、`MILVUS_URI` 指向 Milvus，并从 Java 上传到 MinIO 的真实资产建立索引；只有显式设置 `RETRIEVER_MODE=memory` 才启用空的进程内存储。模型、联网搜索和 Embedding 的用户凭证都由前端项目设置保存并在单次请求中注入；项目创建者的配置优先。没有 Embedding 配置时使用本地 hash 向量兜底，生产环境应在“模型配置 → 知识库向量化 API”中填写与 Milvus 集合维度一致的 Embedding 配置。需要外部资料时，项目工具设置中的 `WEB_SEARCH` 连接器提供 API Key，研究请求还必须将 `allowWebSearch` 设为 `true`。

上线时 Java 后端会从项目配置表解析启用的模型和 `WEB_SEARCH` 连接器，将凭证仅注入当前运行请求；凭证不会进入前端响应或研究运行记录。模型和工具配置支持 `TEAM` 与 `PERSONAL` 作用域：默认按项目创建者个人配置、创建者共享配置、当前用户个人配置、其他共享配置的顺序选择；用户显式选择的可见配置仍可覆盖默认值。Agent 对话和研究任务共用同一套 Agent Registry 与消息契约，Java 只负责权限、持久化与 SSE 转发。
