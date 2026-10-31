# Shinkou Insight 全栈面试技术拆解

核对日期：2026-10-18。依据当前仓库源码、35 份 Flyway 迁移、Docker Compose、镜像构建文件与现有验收记录整理。

本轮另结合 51 项官方文档、规范与原始论文补充版本条件、协议细节和验证方法，问答扩充为 120 题。来源及适用范围见 [官方资料与版本核对](11-official-references.md)；在线资料描述的框架能力与本项目已经实现的能力分别说明。

本套材料面向 Java 后端、全栈和 AI Agent 应用工程面试。仓库没有提供具体公司的岗位 JD，因此按「能独立设计、实现、解释、验证并排查这个项目」的要求展开。学习目标不是记住框架名称，而是对每个技术点回答：解决什么问题、原理是什么、代码在哪里、为什么这样选、失败时怎么办、如何证明有效。

## 阅读目录

| 章节 | 内容 | 面试重点 |
| --- | --- | --- |
| [01 前端与浏览器](01-frontend.md) | Vue、TypeScript、路由、HTTP、认证、SSE、Markdown、性能 | 从点击按钮讲到页面更新，解释异步和状态一致性 |
| [02 Java 业务后端](02-java-backend.md) | Spring、MVC、Security、会话、RBAC、事务、虚拟线程、JVM | 业务边界、权限、并发、事务和接口设计 |
| [03 PostgreSQL 与数据建模](03-postgresql.md) | 全部业务表、约束、索引、MVCC、锁、SQL、迁移、恢复 | 让数据库维护不变量，说明查询和写入代价 |
| [04 Python 与 RAG](04-python-rag.md) | FastAPI、asyncio、解析、切片、Embedding、混合检索、引用 | 检索质量、模型边界、跨存储一致性 |
| [05 Agent、工具与评估](05-agent-evaluation.md) | 运行时、策略、消息总线、任务队列、恢复、Prompt、指标 | 受约束执行、幂等、取消、真实质量评估 |
| [06 Docker 与 Nginx](06-docker-nginx.md) | 所有服务、镜像、网络、存储、构建、健康、启动、代理 | 从源码到容器运行，解释每个容器为什么存在 |
| [07 Docker 中的数据系统](07-data-systems.md) | Redis、Milvus、etcd、两套 MinIO、Neo4j、MCP | 每个系统的内部原理、数据职责和故障影响 |
| [08 安全、可靠性与运维](08-reliability-security.md) | 一致性、恢复、安全、性能、容量、测试、上线和事故 | 从「能运行」走向「可验证、可恢复、可扩展」 |
| [09 面试问答与讲解](09-interview-questions.md) | 分岗位讲法、项目陈述、连续追问、练习路线 | 将源码知识组织为可信、可追问的回答 |
| [10 源码导航与练习](10-source-map.md) | 逐层可点击源码、关键方法、十项复现练习 | 从回答回到代码与可验证证据 |
| [11 官方资料与版本核对](11-official-references.md) | 51 项一手资料、版本矩阵与本轮补充点 | 避免照搬新版本机制或论文效果 |

## 1. 使用时区分三种证据

- **当前实现**：在本次读到的代码、配置或迁移中能定位。说明实现存在，不自动意味着所有部署环境都启用了它。
- **原理与推导**：解释框架机制，或由代码推导出的行为、风险。推导应通过测试或运行证据继续验证。
- **扩展方案**：面试官要求扩大规模或提高可靠性时可以提出的设计，不能直接写成已经落地的项目成果。

各章中的示例 SQL、伪代码、容量算式和排障命令用于学习；不代表本次已经对运行中的数据库执行过操作。

## 2. 先纠正旧材料中容易被追问的说法

| 容易照背的说法 | 当前源码证据 | 面试时应如何表达 |
| --- | --- | --- |
| Cookie + JWT + Redis 分布式会话 | SecurityConfig 使用 HttpSessionSecurityContextRepository 和 SessionRegistryImpl；pom 未引入 Spring Session Redis | 当前是服务端 HttpSession + Cookie；Redis 用于验证码、限流以及 AI 缓存、队列、快照，不能据此声称 Session 已共享 |
| 主链路由 LangGraph 持久化 Checkpoint 驱动 | qa_graph.py 标注为 legacy；AgentRuntime.execute 当前进入语义决策路径，代码中也保留 AgentCoordinator 和角色注册 | 讲清当前 Runtime / DecisionEngine、协调器与兼容图的分工；持久化图检查点属于需要单独证明的能力 |
| 前端已经采用 Pinia + TanStack Query | package 有 Pinia，main.ts 未注册 createPinia；当前业务状态主要在 composables；依赖没有 TanStack Query | 当前用 Vue Composition API 组合业务状态；Pinia 已声明但不能当成已经全面接入 |
| Java 使用 MyBatis-Plus | pom 实际是 mybatis-spring-boot-starter | 使用 MyBatis Mapper 与 SQL；没有证据就不讲 MyBatis-Plus 插件机制已经接入 |
| 关键词检索就是 BM25 | 生产适配器使用 PostgreSQL ts_rank_cd 与中文 n-gram 字面匹配；hybrid.py 有本地 BM25 实现 | 区分 PostgreSQL 关键词通道和内存回退的 BM25 |
| Rerank 使用神经网络 Cross Encoder | LexicalReranker 是确定性词法重排 | 当前是轻量词法重排；Cross Encoder 是可替换适配器方案 |
| 默认 Embedding 已经支持语义理解 | 基础 Provider 被设为 hash；Milvus 适配器遇到 hash 会将 VECTOR/HYBRID 有效模式降为 KEYWORD | 默认用于跑通流程；真实语义召回要配置外部模型并重新索引 |
| 启动了 Neo4j 就自动使用图数据库 | GRAPH_MODE 默认 memory；Neo4j 服务没有 Compose profile，完整 up 仍可能启动它 | 容器是否启动与应用是否选用它是两个判断 |
| Redis 队列保证 exactly once | 消费组、Pending 回收、心跳、终态检查提供恢复和去重措施 | 是需要幂等处理的至少一次投递思路；进程内防重和 Redis 快照不能证明分布式恰好一次 |
| 所有事件已经跨进程可靠持久化 | Python EventBus 是进程内历史与订阅；Java 有 agent_run_events，Redis 有 Run 快照 | 区分事件流、运行快照和业务落库，不把三者当成同一保证 |
| Compose 项目名不同就一定隔离 | 网络和多个 volume 显式设置 name | 做隔离验收时要另外覆盖网络和卷名，否则仍可能访问同一数据 |
| Docker 构建成功意味着完整业务验证通过 | Java Dockerfile 使用 -DskipTests；现有 Docker 验收使用 mock 模型 | 构建、自动测试、基础设施连通、真实模型端到端需要分别给出证据 |

## 3. 项目的一分钟结构

这是一个以工作区和项目为业务边界的证据驱动调研平台。用户上传资料，系统解析、切片和索引；研究运行从内部知识库及允许的外部来源收集证据，再生成带引用的报告，经过审查形成行动项和验收记录。

浏览器运行 Vue SPA，经 /api 访问 Java。Java 管理登录、权限、业务事务、运行记录、报告和审查；Python 执行文档处理、模型调用、RAG、Agent 和工具。PostgreSQL 保存业务事实和 Chunk 正文，Milvus 保存向量索引，MinIO 保存原文件与生成物，Redis 负责验证码、限流及 AI 缓存、队列和运行快照。图谱默认内存，可选择 Neo4j。Docker 中的 etcd 和另一套 MinIO 是 Milvus 的依赖。

~~~mermaid
flowchart LR
    U[浏览器 Vue] -->|同源 /api Cookie SSE| N[Nginx 或 Vite 代理]
    N --> J[Spring Boot 业务控制面]
    J --> P[(PostgreSQL)]
    J --> R[(Redis)]
    J --> O[(业务 MinIO)]
    J -->|内部 API Key| A[FastAPI AI Runtime]
    A --> P
    A --> R
    A --> O
    A --> V[Milvus standalone]
    V --> E[etcd 元数据]
    V --> M[(Milvus 专用 MinIO)]
    A -.可选.-> G[Neo4j]
    A -.可选.-> C[MCP Server]
    A --> L[外部模型与搜索 Provider]
~~~

## 4. 每层至少要回答到什么深度

| 层级 | 最低要求 | 深挖要求 | 验证方式 |
| --- | --- | --- | --- |
| 浏览器 | HTTP、Cookie、异步、渲染 | CSRF、SSE 重连、精度和竞态 | Network、Performance、断线与切项目 |
| Vue | ref/computed/watch、组件和组合函数 | 生命周期清理、流式渲染成本 | 组件状态变化与事件序列 |
| Java | MVC、DI、Security、MyBatis | 事务提交时机、并发和虚拟线程 | Mapper SQL、服务代码、异常和集成测试 |
| PostgreSQL | 主外键、索引、事务 | MVCC、锁、执行计划、恢复 | EXPLAIN、约束、并发事务、恢复演练 |
| Python | Schema、依赖注入、异步 | 阻塞卸载、资源生命周期和取消 | 超时、错误、并发与故障注入 |
| RAG | 切片、Embedding、召回、引用 | 融合、中文检索、版本与一致性 | 固定语料、Recall@K、引用检查 |
| Agent | 策略、工具、运行状态 | 幂等、任务回收、成本和恢复边界 | 重复投递、杀 Worker、取消和回调乱序 |
| Docker | 镜像、容器、网络、卷 | 依赖健康、缓存、持久化、回滚 | Compose 配置、健康接口、数据保留 |
| 数据系统 | 各自存什么 | 单点、持久化、重建、故障域 | 宕机影响和备份恢复矩阵 |

## 5. 面试中的回答结构

按「业务场景 → 不变量 → 当前实现 → 故障窗口 → 验证证据 → 下一步」回答。例如：资料上传后要让 Python 插入 Chunk，但 Java 的资产行尚未提交会导致外键或查询失败；因此索引派发放在事务 afterCommit，再用状态字段暴露失败。不过 afterCommit 到任务真正被接收仍有崩溃窗口，若需要可靠投递应引入事务 Outbox。这个回答同时体现了业务、事务、跨服务和边界意识。

## 6. 验证记录的正确使用

[2026-10-18 Docker 验收记录](../acceptance/2026-10-18/docker-validation.md)记载：前端测试 49 项通过，Python 339 项通过且 7 项数据库相关测试跳过，Java 61 项通过且 2 项数据库集成测试跳过，三个镜像构建及隔离基础设施冒烟通过。它同时说明使用 mock 模型，没有真实外部模型驱动的完整研究任务。

这些是历史记录，不是本轮重新执行测试得到的数字。文档与网络资料核对不代表完成运行期验证；新增实验和强化设计应在隔离环境验证后再报告结果。
