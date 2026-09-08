# 02. 系统架构设计

## 1. 架构目标

```text
前后端分离
Java 业务控制面与 Python AI Runtime 分离
多工作区数据隔离
RAG 检索和引用可追踪
Agent 工作流可恢复、可取消、可观察
模型、Prompt、工具可替换
报告和运行结果长期可访问
```

## 2. 总体架构

```text
┌──────────────────────────────────────────────────────────┐
│ Browser                                                  │
│ Vue 3 / TypeScript / Vite / Pinia / TanStack Query       │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS / REST / SSE / Cookie
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Spring Boot Control Plane                                │
│ Auth / Workspace / Project / Knowledge / Research        │
│ Report / Action Item / Config / Audit / SSE Gateway      │
└───────────────┬──────────────────┬───────────────────────┘
                │                  │ internal HTTP
                ▼                  ▼
┌────────────────────────┐   ┌─────────────────────────────┐
│ PostgreSQL             │   │ Python FastAPI AI Runtime   │
│ Business + Chunks + FTS│   │ Parser / RAG / Agent Workers │
│ Runs + Evidence        │   │ Models / Tools / Evaluation │
└───────────────┬────────┘   └──────────────┬──────────────┘
                │                           │
                ▼                           ▼
┌────────────────────────┐   ┌─────────────────────────────┐
│ Redis                  │   │ Model / Embedding / Search  │
│ Auth / Cache / Locks   │   │ providers or local models   │
└────────────────────────┘   └─────────────────────────────┘
```

## 3. 组件职责

### 3.1 Vue 前端

负责：

- 登录、激活和工作区选择。
- 项目、知识资产和报告管理。
- 检索测试和引用查看。
- Agent 工作台和 SSE 事件渲染。
- 模型、工具和 Prompt 配置页面。

不负责：

- Token 存储。
- 权限最终判定。
- 文档解析和向量检索。
- Agent 路由决策。

### 3.2 Spring Boot

负责：

```text
认证与 Cookie
工作区和 RBAC
项目和知识资产元数据
文件上传、下载和存储路径
创建与管理 Research Run
报告、行动项和审计
统一外部 API
内部工具权限和参数校验
SSE 事件代理或读取
```

Spring Boot 是外部系统唯一入口。前端不直接访问 Python 服务。

### 3.3 Python FastAPI

负责：

```text
文档解析和切片
Embedding 和检索
Reranker
模型适配
Agent Coordinator + Message Bus
Prompt 渲染和结构化输出
工具执行编排
离线评估
可选 LoRA 推理
```

Python 不负责用户登录、工作区成员 CRUD 和普通后台分页。

### 3.4 PostgreSQL

保存：

- 企业业务数据。
- 文档 Chunk 原文、元数据和 PostgreSQL Full Text Search 索引。
- 运行、节点、工具、证据和报告。
- Prompt、评估和模型版本元数据。

PostgreSQL 是业务数据和 Chunk 元数据的事实源；向量不进入业务库，避免向量索引与事务型数据耦合。

### 3.5 Milvus

Milvus 只保存向量检索所需的数据：`chunk_id`、`workspace_id`、`project_id`、`asset_id` 和 Embedding 向量。索引时先写 PostgreSQL Chunk，再写 Milvus；重建资产时按 `asset_id` 删除旧向量并重新插入。检索时先在 Milvus 做带租户过滤的 ANN 召回，再回 PostgreSQL 补齐原文和引用元数据，最后与 PostgreSQL FTS 结果执行 RRF。

### 3.6 Redis

MVP 用途：

```text
登录会话
登录失败锁定
幂等锁
短期状态缓存
运行取消标记
可选 SSE 事件发布订阅
```

不将 Redis 作为最终运行记录数据库。

## 4. 核心流程

### 4.1 文档入库

```text
Browser 上传文件
→ Java 校验权限、文件类型和大小
→ Java 保存原文件并创建 knowledge_asset
→ Java 创建 embedding_job
→ Python Worker 拉取任务或由 Java 调用索引 API
→ 解析、清洗、切片、Embedding
→ 写 document_chunks
→ 更新 asset 和 job 状态
→ 前端轮询或 SSE 展示进度
```

### 4.2 普通 RAG

```text
Browser 提问
→ Java 校验项目权限
→ Python 执行查询改写、混合检索、Rerank
→ LLM 基于证据生成结构化回答
→ Java 保存可选问答记录
→ 返回答案和 Citation DTO
```

### 4.3 Agent 调研

```text
Browser 创建 Run
→ Java 创建 PENDING 记录
→ Python Coordinator 通过 AgentMessageBus 分派 Planner / Researcher / Analyst / Writer / Reviewer
→ 各 Agent 通过 AgentMessage / AgentResult 契约交互
→ Coordinator 持续写 run_steps / tool_calls / evidence
→ Java SSE 向前端发送事件
→ Python 生成报告草稿并审核
→ Java 保存最终报告和行动项
→ Run 进入 COMPLETED
```

Agent 默认运行在同一个 AI Service 的独立队列 worker 中；设置 `AGENT_TRANSPORT=http` 和 `AGENT_WORKER_URLS` 后，可将指定 Agent 路由到独立进程。Coordinator、Agent Registry、消息契约和传输层彼此隔离，后续可以替换为 Redis Streams 或 NATS。

## 5. 同步与异步边界

同步：

- 登录、工作区、项目和资产元数据 CRUD。
- 检索 Playground。
- 小型普通 RAG 问答可先同步。

异步：

- 文档解析和 Embedding。
- 多轮 Agent 调研。
- 批量评估。
- LoRA 训练。

MVP 可用 Spring `@Async` 或轻量 Worker；若任务可靠性成为瓶颈，再引入消息队列。个人项目首版不强制部署 Kafka/RabbitMQ。

当前业务任务选型：不立即引入 Kafka/RabbitMQ。`research_runs` 作为 PostgreSQL 中的任务事实表，Worker 使用短事务和 `FOR UPDATE SKIP LOCKED` 抢占 `PENDING` 任务；任务状态、重试次数和租约写回数据库。Agent 消息默认使用进程内队列，跨进程部署时通过 HTTP Worker transport 过渡，后续再引入可靠消息队列。

当出现多实例高吞吐、跨服务解耦或外部任务积压时，再引入消息队列。优先评估已有 Redis 的 Streams/Consumer Group；如果需要更强的投递确认、死信队列和独立消费治理，再使用 RabbitMQ。Kafka 适合事件流和大规模日志，不是当前任务队列的首选。

## 6. Agent 运行持久化

建议同时持久化两层状态：

```text
Agent Message：跨 Agent 的可追踪输入输出契约
Agent Event：Agent 生命周期、工具调用和审核事件
业务数据库：前端、审计、统计所需的稳定业务记录
```

不能只依赖进程内队列，因为报告和审计需要独立于 Agent 运行时长期访问；跨进程 transport 也必须保留 `run_id`、`trace_id` 和 `message_id`。

## 7. 工具边界

Agent 工具必须注册并配置：

```text
search_knowledge
read_document_chunk
search_web
fetch_web_page
save_evidence
save_finding
create_action_item
save_report_draft
```

每个工具包含：

- JSON Schema。
- READ / WRITE 权限。
- 超时。
- 最大结果长度。
- 是否需要人工确认。
- 审计和敏感参数脱敏策略。

## 8. 模型边界

按任务选择模型，而不是全局只有一个模型：

| 任务 | 模型类型 |
|---|---|
| Planner / Writer | 通用对话模型 |
| Query Rewrite | 小型结构化输出模型即可 |
| Embedding | 独立 Embedding 模型 |
| Rerank | Cross-encoder 或远程 Reranker |
| Evidence Review | 通用模型或后期 LoRA 模型 |

## 9. 多工作区隔离

强制规则：

1. 所有项目级表包含 `workspace_id`。
2. 外部 API 路径包含 `workspaceId`。
3. Java 校验用户是 ACTIVE 成员。
4. Java 校验资源属于当前工作区和项目。
5. Python 调用必须携带不可由 LLM 修改的租户上下文。
6. SQL 检索必须显式过滤 `workspace_id`、`project_id`。
7. 日志不得混淆不同工作区的文本内容。

## 10. 部署架构

MVP Docker Compose：

```text
frontend
backend
ai-service
postgres
milvus-etcd
milvus-minio
milvus
redis
```

生产演示建议：

- 前后端同站点反向代理，减少 Cookie 跨域问题。
- HTTPS + Secure Cookie。
- PostgreSQL 和 Redis 不开放公网。
- 原始文件和模型 Adapter 使用挂载卷或对象存储。
- Python 服务只允许后端内部访问。

## 11. 关键技术决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 向量数据库 | Milvus | 向量索引与业务事务解耦，支持标量过滤和独立扩展 |
| Agent 编排 | AgentCoordinator + AgentMessageBus | 需要分支、循环、状态、Streaming、恢复和跨 Agent 路由 |
| LangChain | 只用 Core/适配组件 | 避免业务被黑盒 Chain 绑定 |
| 外部 API 入口 | Spring Boot | 保留传统后端优势和安全控制 |
| 实时更新 | SSE | 单向事件足够，复杂度低于 WebSocket |
| 微调 | 后期 QLoRA | 先获得数据和基线，再证明增益 |
