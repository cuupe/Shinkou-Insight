# 11. 官方资料、论文与版本核对

联网核对日期：2026-10-18。以下来源用于补充原理与版本条件；项目是否实现某能力，仍以源码、实际安装版本和验收记录为准。框架文档给出的能力，不能自动算作本项目成果。

## 1. 本轮具体完善了什么

| 内容 | 完善点 | 对应章节 |
| --- | --- | --- |
| Vue 异步监听 | cleanup 注册时机、过期请求的 finally、DOM 更新时机 | [前端](01-frontend.md) |
| SSE 协议 | 空行、具名事件、游标生命周期、204、连接数 | [前端](01-frontend.md) |
| Spring 事务 | 逻辑/物理事务、传播与连接预算、afterCommit 资源边界 | [Java](02-java-backend.md) |
| Java 版本 | Java 21 pinning 与 JDK 24 变更分开解释 | [Java](02-java-backend.md) |
| 数据库 | NULL 约束、Index Only Scan、在线索引、SQLSTATE、PITR | [PostgreSQL](03-postgresql.md) |
| Python | 同步辅助函数、取消传播、Schema 转换、连接上下文 | [Python/RAG](04-python-rag.md) |
| 论文与评估 | RRF 参数背景、RAG 概念与工程实现区别、消融实验 | [Python/RAG](04-python-rag.md) |
| Redis 队列 | Pending 不保护 payload、裁剪与版本、扫描游标 | [Agent](05-agent-evaluation.md) |
| Docker/Nginx | 插值/注入、构建秘密、恢复机制、超时方向、DNS 版本 | [Docker](06-docker-nginx.md) |
| 数据系统 | 租约与 fencing、可见性、碎片、MERGE、ETag、MCP 无状态 | [数据系统](07-data-systems.md) |
| 安全与观测 | OWASP 入口验收、清洗顺序、分位聚合和指标基数 | [可靠性](08-reliability-security.md) |
| 面试训练 | 追加 Q101—Q120，覆盖本轮版本与协议追问 | [问答](09-interview-questions.md) |

## 2. 版本读取原则

| 技术 | 仓库边界 | 使用网络资料时的限制 |
| --- | --- | --- |
| Java | pom 与 Docker JRE 都是 21 | 不能把 JDK 24+ 的锁行为直接套用 |
| Spring | Boot 声明 4.1.0，实际依赖由 BOM 解析 | Spring current 文档会变化，升级前查有效依赖树和对应版本 API |
| Vue | package 声明 ^3.5.40 | 锁文件/安装结果才是精确版本；示例涉及 3.5 cleanup 条件 |
| PostgreSQL | Compose 16-alpine | 本轮主要使用 /docs/16/，不默认新主版本优化已存在 |
| Redis | Compose 7.4-alpine | latest 页面包含 8.x 命令，必须看 since；客户端库 redis>=5,<6 是另一版本维度 |
| Milvus | 服务 2.4.23、客户端 pymilvus 2.4.x 范围 | 架构/一致性使用 2.4.x 文档，SDK 与服务端要分别核对 |
| Python | 镜像 3.11 | asyncio 以 3.11 为基准；requirements 范围不是完整锁定清单 |
| Neo4j | 5.26-community | 文档选择 5，并区分 Community/Enterprise |
| MinIO | 固定 2025-04-22 发布标签 | 不默认后续 AIStor 功能已在该标签可用 |
| MCP | SDK 范围与传输配置是本地事实 | 2025-11-25 是本轮参考规范，实际要看初始化协商版本 |
| Nginx | stable-alpine 浮动标签 | 动态 upstream 解析有版本条件，应记录镜像 digest 与 nginx -v |

## 3. 前端与协议来源

| 编号 | 一手资料 | 用于核对 |
| --- | --- | --- |
| S01 | [Vue Watchers](https://vuejs.org/guide/essentials/watchers.html) | cleanup、flush、依赖收集 |
| S02 | [Vue Performance](https://vuejs.org/guide/best-practices/performance.html) | 分包、虚拟列表、浅层响应式 |
| S03 | [WHATWG Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html) | 事件格式、重连与游标 |
| S04 | [MDN Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) | 浏览器使用与连接限制 |

## 4. Java 与 Spring 来源

| 编号 | 一手资料 | 用于核对 |
| --- | --- | --- |
| S05 | [Spring Transaction Propagation](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html) | 传播和连接池占用 |
| S06 | [Spring TransactionSynchronization API](https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/transaction/support/TransactionSynchronization.html) | 提交后回调语义 |
| S07 | [Oracle Java 21 Virtual Threads](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html) | 等待、pinning、JFR |
| S08 | [Oracle JDK 24 Significant Changes](https://docs.oracle.com/en/java/javase/24/migrate/significant-changes-jdk-24.html) | JEP 491 行为变化 |
| S09 | [Spring Session with Boot/Redis](https://docs.spring.io/spring-session/reference/guides/boot-redis.html) | 共享 HttpSession 接入 |
| S10 | [Spring Security Session Management](https://docs.spring.io/spring-security/reference/servlet/authentication/session-management.html) | 手工认证、上下文持久化 |

## 5. PostgreSQL 16 来源

| 编号 | 一手资料 | 用于核对 |
| --- | --- | --- |
| S11 | [Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html) | NULL、唯一、CHECK 与外键 |
| S12 | [Multicolumn Indexes](https://www.postgresql.org/docs/16/indexes-multicolumn.html) | 复合 B-tree 扫描条件 |
| S13 | [Index-Only Scans](https://www.postgresql.org/docs/16/indexes-index-only-scans.html) | 可见性与 Heap Fetch |
| S14 | [CREATE INDEX](https://www.postgresql.org/docs/16/sql-createindex.html) | 并发建索引限制 |
| S15 | [Explicit Locking](https://www.postgresql.org/docs/16/explicit-locking.html) | 行锁、表锁与阻塞 |
| S16 | [Using EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html) | cost、执行统计 |
| S17 | [Error Codes](https://www.postgresql.org/docs/16/errcodes-appendix.html) | 事务失败分类 |
| S18 | [Continuous Archiving and PITR](https://www.postgresql.org/docs/16/continuous-archiving.html) | 基础备份与连续 WAL |

## 6. Python、RAG 与工作流来源

| 编号 | 一手资料 | 用于核对 |
| --- | --- | --- |
| S19 | [FastAPI Concurrency](https://fastapi.tiangolo.com/async/) | 路由/依赖与辅助函数区别 |
| S20 | [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) | 同进程后台工作边界 |
| S21 | [Python 3.11 Coroutines and Tasks](https://docs.python.org/3.11/library/asyncio-task.html) | 并发原语与取消 |
| S22 | [Pydantic Strict Mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/) | 转换与严格校验 |
| S23 | [psycopg Connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html) | 连接上下文与事务 |
| S24 | [RRF，SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) | 排名融合原始论文 |
| S25 | [RAG，2020](https://arxiv.org/abs/2005.11401) | 检索与生成研究背景 |
| S26 | [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | checkpointer 与 store |
| S27 | [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | 状态快照与恢复边界 |

## 7. Redis 来源

| 编号 | 一手资料 | 用于核对 |
| --- | --- | --- |
| S28 | [XREADGROUP](https://redis.io/docs/latest/commands/xreadgroup/) | 组消费、Pending 和正文删除 |
| S29 | [XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/) | 扫描游标、回收与缺失正文 |
| S30 | [XTRIM](https://redis.io/docs/latest/commands/xtrim/) | 裁剪与版本限定 |
| S31 | [Redis 7.4 Commands](https://redis.io/docs/latest/commands/redis-7-4-commands/) | 当前服务器命令范围 |
| S32 | [Distributed Locks](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/) | 持有者标识与安全释放 |
| S33 | [Redis Persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/) | AOF/RDB 与恢复 |

## 8. Docker、代理和数据基础设施来源

| 编号 | 一手资料 | 用于核对 |
| --- | --- | --- |
| S34 | [Compose Environment Precedence](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/) | 插值来源与最终容器变量 |
| S35 | [Docker Build Secrets](https://docs.docker.com/build/building/secrets/) | 构建期秘密传入 |
| S36 | [Compose Startup Order](https://docs.docker.com/compose/how-tos/startup-order/) | 健康/完成条件 |
| S37 | [Docker Running Containers](https://docs.docker.com/engine/containers/run/) | 运行与重启策略 |
| S38 | [Nginx Upstream Module](https://nginx.org/en/docs/http/ngx_http_upstream_module.html) | 动态解析与版本 |
| S39 | [Nginx Proxy Module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) | 缓冲与超时方向 |
| S40 | [Milvus 2.4 Architecture](https://milvus.io/docs/v2.4.x/architecture_overview.md) | 组件职责与存算分工 |
| S41 | [Milvus 2.4 Consistency](https://milvus.io/docs/v2.4.x/consistency.md) | GuaranteeTs 与读取语义 |
| S42 | [etcd 3.5 Maintenance](https://etcd.io/docs/v3.5/op-guide/maintenance/) | 压缩、碎片与维护阻塞 |
| S43 | [Neo4j 5 MERGE](https://neo4j.com/docs/cypher-manual/5/clauses/merge/) | 模式、并发和约束 |
| S44 | [MinIO 仓库对应发布标签](https://github.com/minio/minio/tree/RELEASE.2025-04-22T22-12-26Z) | 实际发行版本背景 |
| S45 | [S3 Upload Integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html) | ETag 与完整内容校验区别 |
| S46 | [MCP 2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | Origin、会话与传输条件 |

## 9. 安全与可观测性来源

| 编号 | 一手资料 | 用于核对 |
| --- | --- | --- |
| S47 | [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) | 目标、重定向和网络层 |
| S48 | [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html) | 清洗后的修改风险 |
| S49 | [OWASP File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | 多信号与资源限制 |
| S50 | [OWASP LLM Prompt Injection](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | 工具授权与 Guardrail 边界 |
| S51 | [OpenTelemetry Metrics Data Model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/) | 分布聚合与指标属性 |

## 10. 如何使用这些来源

先读对应章节的项目例子，再查官方条目的版本和前提，最后回源码定位。发现不一致时，分别记录「官方机制」「代码采用方式」「实测结果」，不能用其中一个代替另外两个。官网 current/latest 链接今后可能变化，正式面试或升级前应再次核对。
