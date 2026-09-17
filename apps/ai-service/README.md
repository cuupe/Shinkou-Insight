# Shinkou Insight AI Service

## Production architecture

The service is a tenant-scoped multi-agent runtime, not a single chat handler:

- LangChain `ChatOpenAI`/Core adapters, prompt templates, and a versioned prompt registry with SHA-256 snapshots.
- Prompt-injection boundary for user/document data, structured Pydantic outputs, citation validation, and a small grounding evaluation module.
- Hybrid RAG: Milvus embeddings plus PostgreSQL full-text/BM25-like search, shared RRF/linear fusion, Chinese n-gram recall, duplicate suppression, MMR diversity selection, deterministic query variants, in-memory deterministic mode for CI, document parsers/chunking, object storage adapters, and optional Neo4j graph extraction.
- Replayable SSE run events, cancellation, Java callbacks, bounded tool execution, async tool tasks, deterministic tool chains, and optional MCP read-only extension tools.

## Runtime boundaries

- `config.py`: loads only the repository root `.env`; `.env.example` is documentation and is never read.
- `core/container.py`: the single composition root for LLM, embeddings, storage, PostgreSQL, graph, web search, tools, and lifecycle cleanup.
- `app.py`: HTTP boundary only; routes use dependencies exposed by the container.
- `agents/`: independent Agent contracts, registry, message bus, coordinator, and provider-free role implementations.
- `workflows/`: legacy graph compatibility and focused workflow experiments; production research runs use `AgentCoordinator`.
- `rag/`, `documents/`, `embeddings/`, `storage/`, and `tools/`: isolated adapters with explicit interfaces.

## 文件分析与多模态附件

文件分析走本地工具链，不把原始二进制直接放进模型上下文：

- PDF 先用 `pypdf` 提取文本；文本为空的页面用 Poppler 渲染，再交给 Tesseract（默认 `chi_sim+eng`）OCR。
- DOC/DOCX、XLS/XLSX、PPT/PPTX、ODF 和 RTF 分别使用原生 Python 解析器或 LibreOffice headless 转 PDF；DOCX/PPTX 中的表格、标题和嵌入图片也会尽量提取，图片走 OCR。
- PNG/JPG 等图片走 Tesseract OCR；SVG 提取其文本节点。
- MP3/WAV/M4A 等音频和 MP4/WebM/MOV 等视频使用 FFmpeg/媒体解码与 `faster-whisper` 生成带时间戳的转写文本；视频还会按固定间隔抽取最多 8 帧，对画面文字执行 OCR。
- Agent 对话附件在进入模型前才按附件读取并生成有限长度的本地分析上下文，默认总上限 20,000 字符，避免大文件无界消耗 token；知识库索引仍然使用完整解析结果。

Docker 镜像已包含 Tesseract（简体中文和英文语言包）、Poppler、LibreOffice 和 FFmpeg，并安装 `python-pptx`、Pillow、`faster-whisper`。可用 `GET /internal/files/tools` 检查当前服务的工具就绪情况。缺少某个本地工具时不会静默跳过，而会在附件分析结果和运行事件中报告具体原因。

论文可以直接从项目“知识库”上传 PDF，完成文本/OCR 后建立索引；对话中的外部论文引用仍保留来源链接，用户可以先下载原始 PDF，再手动上传以获得完整、可引用的论文内容，而不是只保存搜索摘要。

The production path is PostgreSQL + Milvus + MinIO + an OpenAI-compatible LLM/embedding provider. PostgreSQL stores source chunks and FTS metadata; Milvus stores filtered vector indexes. The in-memory knowledge adapter is empty by default and is reserved for tests or explicit local diagnostics.

## 缓存、队列与可恢复运行

- `core/cache.py` 提供 Redis 优先、内存有界降级的异步缓存。检索缓存按工作区/项目版本隔离；索引成功后只递增项目版本即可让旧召回失效。向量化按模型、维度和文本 SHA-256 缓存，联网搜索按提供商、查询和 `topK` 缓存；缓存包含 TTL、单进程 single-flight、命中率和错误计数，可通过 `GET /internal/runtime/status` 检查。
- `core/task_queue.py` 使用 Redis Streams consumer group，支持服务重启后接管 pending 消息、失败重试和最大重试次数；Redis 不可用时退回进程内队列。研究入口返回 202 后立即入队，不再占用 HTTP 后台任务。
- `core/repository.py` 将运行快照、计划版本、审查结果和证据镜像到 Redis，内存状态作为热缓存。队列消息和快照均保留 30 天，服务重启后可以重新接管未确认任务。
- 计划修改使用 `PATCH /internal/research/runs/{run_id}/plan`，支持 `APPEND`、`REPLACE`、`PAUSE`、`RESUME` 和 `expectedVersion` 乐观锁。修改在 Agent 安全检查点应用，新增/修改步骤会产生新的检索证据。

主要配置为 `REDIS_URL`（或 `REDIS_HOST`、`REDIS_PORT`、`REDIS_PASSWORD`）、`CACHE_*` 和 `TASK_QUEUE_*`。生产环境应保持 Redis 持久化开启，并为不同部署设置不同的 `CACHE_NAMESPACE` 与 `TASK_QUEUE_GROUP`。

## 审查门禁

`ReportReviewerAgent` 现在同时执行模型审查和确定性门禁：引用 ID 存在性、正文是否有引用、引用与证据的可识别支撑、数字是否出现在证据、外部来源标注，以及阻断项和风险等级。项目“审查中心”的引用、数字、冲突和外部来源策略会在 Java 调度研究时注入 `reviewPolicy`；任何确定性阻断项都会覆盖模型的通过判断，并要求 Writer 重写。

## MCP

MCP is an extension boundary, not a replacement for the core registry. Run the optional read-only server with `MCP_TRANSPORT=streamable-http` for production or `stdio` for local desktop clients:

```powershell
cd apps/ai-service
MCP_TRANSPORT=streamable-http .\.venv\Scripts\python.exe mcp_server.py
```

The server exposes only `search_knowledge` and `search_graph`. Every call requires both `workspace_id` and `project_id`; the client bridge additionally supports an explicit tool allow-list, timeouts, and read-only registration. Enable the bridge in the main service with `MCP_ENABLED=true`, `MCP_URL`, and `MCP_ALLOWED_TOOLS`.

Prompt versions are defined in `prompts/registry.py`; search routing vocabulary, query-rewrite terms, and grounded-answer/search prompts live in `prompts/search_prompts.py`. Agent calls continue to use the compatibility functions in `prompts/agent_prompts.py`, so prompts can evolve independently from the Agent transport and orchestration layers.

## 混合搜索

`POST /internal/knowledge/search` 默认执行以下链路：

1. Milvus COSINE dense recall（生产环境）与 PostgreSQL `search_vector`/`ILIKE` keyword recall 并行准备候选集；关键词路径对中文问题补充 2/3-gram，并使用受限查询变体提高实体召回。
2. 对各路候选按 chunk id 去重，再使用 `WEIGHTED_RRF` 融合（默认向量 0.55、关键词 0.45）；需要可解释分数时可将 `fusionMethod` 改为 `LINEAR`，系统会先对每路分数做 min-max 归一化。
3. 在融合候选上执行轻量 MMR，减少同一文件相邻 chunk 重复进入回答上下文；`useReranker=true` 时再执行廉价 lexical reranker。

请求可调 `candidateK`、`rankConstant`、`vectorWeight`、`keywordWeight`、`diversityLambda` 和 `rerankTopK`。响应中的 `rewrittenQueries` 与 `searchTrace` 用于调试召回与融合，不包含模型隐藏推理。设计依据包括 [Elastic hybrid search](https://www.elastic.co/docs/solutions/search/hybrid-search)、[Elastic RRF](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)、[OpenSearch hybrid search](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index/)、[RRF 原论文](https://doi.org/10.1145/1571941.1572114) 以及 [BGE-M3](https://arxiv.org/abs/2402.03216) 的 dense/sparse/multi-vector 检索思路。

## 自定义 Python 工具

核心注册表同时支持 MCP 和开发者自己编写的 Python 工具。把受信任的直接 `.py` 文件放到 `custom_tools/`，使用 `tools.custom.custom_tool` 声明名称、权限、超时和输入契约；服务启动时自动加载，修改后调用 `POST /internal/tools/custom/reload` 或重启服务。同步 handler 会自动在线程池执行，异步 handler 可直接使用 `async def`。

自定义工具目录只接受本地受信任代码，不提供通过 HTTP 上传并执行源码的能力。写工具必须声明 `permission="WRITE"`，并在调用时同时满足 `allowWrites=true` 和 `confirmed=true`。可通过 `CUSTOM_TOOLS_DIR`、`CUSTOM_TOOLS_MODULES` 和 `CUSTOM_TOOLS_STRICT` 控制加载范围与失败策略，完整示例见 `custom_tools/README.md`。

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
.\.venv\Scripts\python.exe server.py --host 0.0.0.0 --port 8003

# 开发时如需热重载，可显式使用 Uvicorn；Windows 生产/本地联调优先使用上面的 Selector 启动器。
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

### 工具执行器

核心工具注册表统一处理权限、输入契约、超时、每个运行的调用预算、并发限制和脱敏审计。同步 Agent 继续使用 `registry.execute(...)`；需要后台执行时使用以下接口，返回句柄后轮询即可，不会占住 HTTP 请求：

- `GET /internal/tools`：查看当前注册的内置工具和 MCP 工具。
- `POST /internal/tools/calls`、`GET /internal/tools/calls/{call_id}`、`POST /internal/tools/calls/{call_id}/cancel`：提交、查询、取消异步工具。
- `POST /internal/tools/chains`、`GET /internal/tools/chains/{chain_id}`、`POST /internal/tools/chains/{chain_id}/cancel`：提交、查询、取消工具链。

工具链是显式依赖 DAG；没有依赖的步骤并行执行，后续步骤通过 `{"$from":"stepId.field"}` 或 `"{{steps.stepId.field}}"` 读取已完成步骤的结果。链路不会执行字符串中的代码或隐式解析模型输出，并且所有步骤仍共享 `run_id` 的工具调用上限。

- `POST /internal/research/runs/{run_id}/execute`
- `POST /internal/research/runs/{run_id}/cancel`
- `PATCH /internal/research/runs/{run_id}/plan`
- `GET /internal/runtime/status`
- `POST /internal/cache/invalidate`（传入 `workspaceId`、`projectId`，递增该项目的检索缓存版本）
- `GET /internal/research/runs/{run_id}/events`
- `POST /internal/knowledge/search`
- `POST /internal/knowledge/answer`
- `POST /internal/llm/chat`
- `POST /internal/llm/test`
- `GET /internal/agents`
- `POST /internal/agents/{agent_name}/messages`

请求必须带 `X-Internal-Api-Key`。默认使用 `DATABASE_URL` 指向 PostgreSQL、`MILVUS_URI` 指向 Milvus，并从 Java 上传到 MinIO 的真实资产建立索引；只有显式设置 `RETRIEVER_MODE=memory` 才启用空的进程内存储。模型、联网搜索和 Embedding 的用户凭证都由前端项目设置保存并在单次请求中注入；项目创建者的配置优先。没有 Embedding 配置时使用本地 hash 向量兜底，生产环境应在“模型配置 → 知识库向量化 API”中填写与 Milvus 集合维度一致的 Embedding 配置。需要外部资料时，项目工具设置中的 `WEB_SEARCH` 连接器提供 API Key，研究请求还必须将 `allowWebSearch` 设为 `true`。

上线时 Java 后端会从项目配置表解析启用的模型和 `WEB_SEARCH` 连接器，将凭证仅注入当前运行请求；凭证不会进入前端响应或研究运行记录。模型和工具配置支持 `TEAM` 与 `PERSONAL` 作用域：默认按项目创建者个人配置、创建者共享配置、当前用户个人配置、其他共享配置的顺序选择；用户显式选择的可见配置仍可覆盖默认值。Agent 对话和研究任务共用同一套 Agent Registry 与消息契约，Java 只负责权限、持久化与 SSE 转发。
