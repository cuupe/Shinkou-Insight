# 10. 源码导航与可复现讲解练习

本章用于面试前从文档跳回真实实现。路径相对本文件，链接指向当前仓库；方法名帮助定位，后续重构时应重新确认调用关系。

框架机制、协议和论文的对应来源见 [官方资料与版本核对](11-official-references.md)。源码用于判断当前采用方式，官方文档用于判断机制与版本前提，两者都不能替代运行证据。

## 1. 前端证据

| 文件 | 定位内容 | 应能解释 |
| --- | --- | --- |
| [package.json](../../apps/web/package.json) | dependencies / scripts | 声明版本、lockfile、测试与构建区别 |
| [main.ts](../../apps/web/src/main.ts) | createApp / auth failure handler | 实际注册哪些插件，401 跳转在哪里 |
| [路由](../../apps/web/src/router/index.ts) | createWebHistory / beforeEach | 工作区层级、缓存、无权限导航 |
| [HTTP 客户端](../../apps/web/src/utils/request.ts) | anet / ensureCsrfToken / handleAuthFailure | Cookie、CSRF、共享 Promise、401/502 区别 |
| [API 核心](../../apps/web/src/api/core.ts) | unwrap / ApiError | 业务错误与 HTTP 错误契约 |
| [SSE 观察器](../../apps/web/src/utils/agentStream.ts) | watchAgentStream | 去重、游标、轮询、终态与资源清理 |
| [Agent 状态](../../apps/web/src/composables/useAgentWorkspace.ts) | EventSource / 消息处理 | 页面如何订阅并更新对话 |
| [研究状态](../../apps/web/src/composables/useResearchRun.ts) | AbortController / onUnmounted | 切项目竞态、取消网络与清理 |
| [Markdown 规范化](../../apps/web/src/utils/agentMarkdown.ts) | protectFencedCode 等 | 流式代码围栏、公式和标题 |
| [Agent 页面](../../apps/web/src/views/project/AgentWorkspaceView.vue) | Markdown 与消息展示 | 输出增强、清洗和重渲染代价 |
| [研究详情](../../apps/web/src/views/project/RunDetailView.vue) | MarkdownIt / DOMPurify | 一处可核对的清洗链路 |
| [Vite](../../apps/web/vite.config.ts) | server.proxy | /api 改写与开发/生产一致性 |

## 2. Java 证据

| 文件 | 定位内容 | 应能解释 |
| --- | --- | --- |
| [pom.xml](../../apps/backend/pom.xml) | Boot/MyBatis/Redis/Security 依赖 | 真正技术栈，不把依赖当成功能启用证明 |
| [application.yml](../../apps/backend/src/main/resources/application.yml) | datasource / session / multipart / security | 池、超时、环境变量和本地端口 |
| [SecurityConfig](../../apps/backend/src/main/java/com/cuupe/backend/config/security/SecurityConfig.java) | securityFilterChain / securityContextRepository | HttpSession、CSRF、CORS、内部路由例外 |
| [AuthServiceImpl](../../apps/backend/src/main/java/com/cuupe/backend/modules/auth/service/impl/AuthServiceImpl.java) | loginByPassword / authenticateAndPersist | 手工密码校验、changeSessionId、保存上下文 |
| [SessionSecurityService](../../apps/backend/src/main/java/com/cuupe/backend/modules/auth/service/SessionSecurityService.java) | register / expireOtherSessions | 内存会话注册及多实例限制 |
| [AuthRateLimiter](../../apps/backend/src/main/java/com/cuupe/backend/modules/auth/service/AuthRateLimiter.java) | Lua / clientAddress | 原子过期、多个限流维度和可信代理 |
| [SecretCipher](../../apps/backend/src/main/java/com/cuupe/backend/config/security/SecretCipher.java) | encrypt / decrypt | AES-GCM 与密钥生命周期 |
| [资产索引派发](../../apps/backend/src/main/java/com/cuupe/backend/modules/asset/service/AssetIndexingService.java) | schedule / afterCommit | 独立连接可见性、虚拟线程与派发窗口 |
| [AI 客户端](../../apps/backend/src/main/java/com/cuupe/backend/modules/ai/AiIndexingClient.java) | 请求组装与 HTTP 调用 | 跨服务协议、内部认证和超时 |
| [AI 回调](../../apps/backend/src/main/java/com/cuupe/backend/modules/ai/AiCallbackController.java) | verify / agentCallback | 为什么 permitAll 仍有内部认证 |
| [AgentService](../../apps/backend/src/main/java/com/cuupe/backend/modules/agent/service/AgentService.java) | runPipeline / handleAiCallback / send | 消息、事件、订阅、终态与持久化 |
| [研究运行入口](../../apps/backend/src/main/java/com/cuupe/backend/modules/research/controller/ResearchRunController.java) | create / cancel / retry | 接受任务、取消协调与新 Run 重试 |
| [配额 Service](../../apps/backend/src/main/java/com/cuupe/backend/modules/storage/service/StorageQuotaService.java) | reserve / release | MANDATORY 事务、256 MiB/512 MiB 边界 |
| [配额 Mapper](../../apps/backend/src/main/java/com/cuupe/backend/modules/storage/mapper/StorageQuotaMapper.java) | lockUsedBytes | FOR UPDATE 与实际计数对账 |
| [行动项 Service](../../apps/backend/src/main/java/com/cuupe/backend/modules/actionitem/service/ActionItemService.java) | 导入、提交与验收 | 幂等来源、操作者和状态迁移 |
| [报告审查](../../apps/backend/src/main/java/com/cuupe/backend/modules/project/service/ProjectReviewService.java) | 报告快照与决定 | 旧报告签署如何失效 |
| [ID 生成器](../../apps/backend/src/main/java/com/cuupe/backend/utils/SnowflakeIdGenerator.java) | nextId / WORKER_ID | 时间/序列、回拨、单节点与多进程 |

## 3. 数据库迁移证据

| 文件 | 重要内容 | 面试练习 |
| --- | --- | --- |
| [V1](../../apps/backend/src/main/resources/db/migration/V1__workspace_project.sql) | 用户、成员、项目 | 画多租户关系，解释复合唯一 |
| [V2](../../apps/backend/src/main/resources/db/migration/V2__knowledge_research_business.sql) | 资产、Chunk、运行、报告、行动 | 说明每种数据为何单独建表 |
| [V10](../../apps/backend/src/main/resources/db/migration/V10__agent_workspace.sql) | Thread/Message/Run/Event | 解释四者基数与唯一键 |
| [V11](../../apps/backend/src/main/resources/db/migration/V11__search_and_query_indexes.sql) | GIN、复合/部分索引与检查约束 | 根据实际 SQL 判断能否用到索引 |
| [V15](../../apps/backend/src/main/resources/db/migration/V15__optimize_redundant_indexes.sql) | 删除冗余索引 | 解释索引的写入和空间成本 |
| [V17](../../apps/backend/src/main/resources/db/migration/V17__move_embeddings_to_milvus.sql) | 去掉旧 embedding 列 | 解释存储拆分及双写 |
| [V29](../../apps/backend/src/main/resources/db/migration/V29__workspace_model_configs.sql) | 模型配置迁移与旧表归档 | 讲数据复制、默认值、序列与回滚兼容 |
| [V31](../../apps/backend/src/main/resources/db/migration/V31__user_storage_quotas.sql) | 配额表及历史回填 | 解释聚合、计数、行锁和对账 |
| [V34](../../apps/backend/src/main/resources/db/migration/V34__report_review_signoff.sql) | 审查快照与签署字段 | 说明审批绑定版本 |
| [V35](../../apps/backend/src/main/resources/db/migration/V35__action_item_delivery_workflow.sql) | 来源部分唯一与交付字段 | 说明并发幂等与验收闭环 |

## 4. Python / RAG / Agent 证据

| 文件 | 重要入口 | 应能解释 |
| --- | --- | --- |
| [应用生命周期](../../apps/ai-service/api/application.py) | lifespan | 启动装配、队列 Worker、关闭资源 |
| [服务容器](../../apps/ai-service/core/container.py) | build / close | Provider 装配、hash 基础模式与配置注入 |
| [内部认证](../../apps/ai-service/api/dependencies.py) | verify_internal_api_key | 独立服务认证与错误映射 |
| [解析器](../../apps/ai-service/documents/parser.py) | 各格式解析与 _run_external | OCR、转换、媒体、超时和警告 |
| [切片器](../../apps/ai-service/documents/chunker.py) | split / from_config | 字符边界、overlap、元数据和位置限制 |
| [Embedding](../../apps/ai-service/embeddings/providers.py) | build_embedding_provider | hash 与真实语义模型的区别 |
| [Embedding 缓存](../../apps/ai-service/embeddings/cached.py) | _identity | 内容寻址与模型指纹边界 |
| [Milvus 适配器](../../apps/ai-service/rag/milvus_store.py) | index / retrieve / _milvus_filter | schema、hash 降级、双写顺序、回表 |
| [关键词](../../apps/ai-service/rag/keyword.py) | fetch_keyword_rows | 中文 n-gram、范围物化、排名与文件约束 |
| [融合](../../apps/ai-service/rag/hybrid.py) | fuse_ranked_candidates / diversify_candidates | RRF、归一化与多样性 |
| [重排](../../apps/ai-service/rag/reranker.py) | LexicalReranker | 词法能力及误删边界 |
| [检索缓存](../../apps/ai-service/rag/cached.py) | identity / revision | 作用域、参数和版本失效 |
| [Agent Runtime](../../apps/ai-service/agents/runtime.py) | execute / _execute_semantic | 当前主链路、活跃防重、终态和回调 |
| [DecisionEngine](../../apps/ai-service/agents/decision_engine.py) | run_loop / cancellable / snapshot | 预算、证据、等待、取消与收据 |
| [协调器](../../apps/ai-service/agents/coordinator.py) | run / _dispatch | 角色协作与流程策略 |
| [角色消息总线](../../apps/ai-service/agents/bus.py) | start / request | 进程内队列、角色 Worker、远程传输边界 |
| [消息契约](../../apps/ai-service/agents/contracts.py) | AgentMessage / AgentContext | 作用域、追踪和依赖注入 |
| [工具注册表](../../apps/ai-service/tools/registry.py) | ToolSpec / configure_run | 工具预算、权限、异步任务和 DAG |
| [研究队列](../../apps/ai-service/core/task_queue.py) | _worker_loop / _heartbeat / _next | ACK、Pending、claim、重试与回退 |
| [运行仓储](../../apps/ai-service/core/repository.py) | DurableRunRepository | Redis 快照、30 天 TTL 与热状态 |
| [事件总线](../../apps/ai-service/core/events.py) | publish / subscribe | 进程内历史，不等于可靠跨进程事件日志 |
| [审查规则](../../apps/ai-service/agents/reviewer.py) | apply_review_guards | ID/数字/词法支撑检查及局限 |
| [URL 与范围策略](../../apps/ai-service/security/policy.py) | validate_external_url / enforce_scope | 应用第一道检查与 DNS/出站边界 |
| [图存储](../../apps/ai-service/graph/store.py) | Neo4jGraphStore | 参数化 MERGE、租户属性与图谱质量 |
| [兼容 LangGraph](../../apps/ai-service/workflows/qa_graph.py) | build_qa_graph / 文件说明 | 兼容图与当前主链路的区别 |
| [Prompt 注册](../../apps/ai-service/prompts/registry.py) | 版本与快照 | 可复现性与评估条件 |

## 5. 部署和验证证据

| 文件 | 要解释的内容 |
| --- | --- |
| [Compose](../../docker-compose.yml) | 12 个服务、依赖条件、默认地址、显式卷/网络名 |
| [Web Dockerfile](../../apps/web/Dockerfile) | Node 构建与 Nginx 运行分离 |
| [Nginx](../../apps/web/nginx.conf) | API 改写、Docker DNS、SSE、上传和 SPA |
| [Backend Dockerfile](../../apps/backend/Dockerfile) | Maven 缓存、多阶段、普通用户与跳过测试 |
| [AI Dockerfile](../../apps/ai-service/Dockerfile) | OCR/Office/媒体依赖、模型缓存与普通用户 |
| [Docker 验收](../acceptance/2026-10-18/docker-validation.md) | 历史测试、隔离运行、mock 和未覆盖部分 |
| [前端流测试](../../apps/web/test/agentStream.test.mjs) | 事件与快照的逻辑边界 |
| [Python 基础设施测试](../../apps/ai-service/test/test_runtime_infrastructure.py) | 队列、缓存、运行机制的测试范围 |
| [资产派发测试](../../apps/backend/src/test/java/com/cuupe/backend/modules/asset/service/AssetIndexingServiceTest.java) | 提交时机的逻辑验证 |
| [行动数据库测试](../../apps/backend/src/test/java/com/cuupe/backend/modules/actionitem/service/ActionWorkflowDatabaseTest.java) | 真数据库约束的可选集成验证 |

## 6. 十个可复现的讲解练习

1. **请求链路**：在浏览器找一条 API，定位前端 API 模块、Java 路由和 SQL；说明每层身份从哪里来。
2. **上传**：用自己创建的测试文件，记录对象键、资产状态与 Chunk，解释 afterCommit。不要拿真实敏感资料做演示。
3. **关键词**：用一个明确文件名提问，解释提词、租户范围、排名和文件结果约束。
4. **混合召回**：在已获准的模型配置下分别比较通道；若仍是 hash，明确演示的是关键词有效模式。
5. **引用**：挑一个事实逐项核对 ID、Quote、位置、主体、时间和数字。
6. **前端恢复**：运行中刷新与短时断线，记录已有 Run 是否保持、事件是否去重、终态是否恢复。
7. **队列恢复**：只在隔离测试环境模拟 Worker 故障，核对 Pending、重投递和重复调用；没有做过就把它列为待验证。
8. **并发配额**：隔离数据库中用两个事务说明 FOR UPDATE；不要在实际用户数据上制造超额。
9. **报告变更**：修改测试报告后检查旧审查/行动来源版本行为，说明快照作用。
10. **容器定位**：给定 502 或 unhealthy，从 web→backend→AI→依赖逐层检查，解释「存活、就绪、业务正确」三种证据。

## 7. 自测标准

能在 2 分钟内找到对应代码，并解释正常路径、一个并发/故障窗口、一条验证方法，算掌握；只能重复文档结论但找不到调用入口，算仍需复习。对未完成的能力，说明下一步如何验证，比给出没有依据的保证更可靠。
