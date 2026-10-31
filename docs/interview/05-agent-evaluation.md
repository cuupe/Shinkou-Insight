# 05. Agent 运行时、工具、队列、恢复与评估

源码重点：agents/runtime.py、decision_engine.py、decisions.py、coordinator.py、contracts.py、bus.py、registry.py、remote.py、tools/registry.py、core/task_queue.py、core/repository.py、core/events.py、prompts、models/llm.py。

## 1. 先把三个运行概念分开

| 概念 | 职责 | 不应混淆成什么 |
| --- | --- | --- |
| RAG | 从资料中取回证据并供模型使用 | 不负责整个业务状态机 |
| Agent 决策 | 根据目标、证据和预算选择下一步 | 不是无限循环，也不是模型拥有系统权限 |
| Workflow / Coordinator | 管执行顺序、状态、预算和结果 | 不意味着每个节点都必须调用模型 |

### 当前真实入口

AgentRuntime.execute → _execute_semantic → DecisionEngine.run_loop 是当前源码主执行路径。Runtime 同时装配 AgentCoordinator、AgentRegistry 与消息总线，支持角色 Agent 和兼容接口；workflows/qa_graph.py 明确标注 legacy，保留 LangGraph 实验和旧集成。

因此「本项目目前所有研究都由持久化 LangGraph Checkpoint 驱动」不准确。早期文档中的直接回答、ReAct、Plan-and-Solve、Reflection 可以作为策略背景，当前要结合语义决策、运行预算、独立复核的实际入口解释。

## 2. 一次 Run 的生命周期

1. Java 验证用户、项目和请求，创建消息/运行记录。
2. 组装运行策略、个人/工作区模型配置、允许工具、可信上下文和回调地址。
3. Python accept 创建 RunRecord，保存 Prompt 快照与 QUEUED 状态。
4. 入 Redis Stream 或本地回退队列，由 Worker 执行。
5. Runtime 检查终态与进程内活跃运行，进入 RUNNING。
6. 分析附件，选择/压缩历史上下文，创建 DecisionEngine。
7. 有限循环中判断目标、证据需求、允许能力和下一工具。
8. 生成答案并执行引用、事实、计算或复核规则。
9. 记录 usage、耗时、审查和生成物，进入 COMPLETED/FAILED/CANCELLED。
10. 通过事件和回调同步 Java，前端展示持久化内容和 SSE 轨迹。

Run、Thread、Message、Task、ToolCall 需要各自标识：一个线程多条消息，一条用户输入可对应一次 Run，一个 Run 可含多个工具调用和角色任务。混用 ID 会导致重试、统计和审计难以解释。

## 3. DecisionEngine 如何约束模型

引擎快照包含 goal、clock、能力清单、剩余工具数、剩余决策次数、证据、需求、评估、工具收据、可信项目/用户来源和计划版本。模型只在给定结构中建议下一动作，实际执行由代码检查。

### 3.1 终止条件

- 已有足够证据，可以回答。
- 资料不足且没有获准补充来源，应表达缺口。
- 工具/决策次数或总时间预算耗尽，停止扩大搜索并整理结果。
- 用户取消，进入取消流程。
- Schema、上游模型或工具失败达到本次允许边界，保存失败。

这样能把成本上限放在程序中，而不是让 Prompt 写一句「请不要无限研究」。

### 3.2 可信来源与不可信文本

项目目标、服务端作用域、时钟和工具结果各有来源；用户上传文档可以提供事实，但不因写有「忽略系统指令」而升级为策略。模型返回的 workspaceId、工具名或文件路径必须经过服务端限制。

时钟由服务端提供，当前引擎保留实际供给模型的时间上下文用于校验。问题涉及「今天」时不能依赖模型训练时间，也不能在完成后用新的时钟替代最初的引用依据。

## 4. 角色 Agent 与消息契约

项目包含 planner、researcher、analyst、writer、reviewer、query_rewriter、web_researcher 等角色。角色拆分的价值是职责和输出契约，而非数量本身。

AgentMessage 包含 message_id、run_id、sender、recipient、intent、payload、trace_id、workspace_id、project_id、user_id、attempt。AgentResult 使用 agent/status/payload/error，AgentContext 为每次运行注入模型路由、工具、仓储和事件。

这种设计避免角色直接任意修改协调器共享状态。若需要并发研究多个子问题，协调器收集返回结果后统一合并、去重和检查预算。

### 4.1 进程内总线

AgentMessageBus 按角色维护 asyncio.Queue 与 Worker，当前每角色有固定并发槽。它与研究任务队列不同：前者分发角色消息，后者派发整个研究 Run。

进程内队列低延迟、部署简单，但进程退出后队列和 Future 丢失。类注释提到可替换 Redis Streams/NATS，不表示已经部署对应总线。

### 4.2 HTTP Worker

RemoteAgentTransport 允许把指定角色映射到远程 Worker。拆进程后必须处理内部认证、Schema 版本、超时、重试、上下文传递、重复消息和返回结果归属。默认 AGENT_TRANSPORT=in-process，Compose 没有自动为每个角色创建一组独立 Worker 容器。

### 4.3 多 Agent 的代价

增加输入重复、调用次数、延迟、故障路径和协调成本；多个角色可能共享同一模型的偏差，不能因为有「Reviewer」就声称客观独立。适合明确可分解、有独立证据和稳定协议的任务，简单问答直接回答更经济。

## 5. ToolRegistry：工具不是任意函数调用

ToolSpec 声明 name、version、description、READ/WRITE、timeout、max_concurrency、requires_confirmation 和 input_schema。Registry 记录调用、脱敏参数、状态、耗时和错误，并管理每次运行的禁用列表与调用预算。

| 约束 | 作用 | 不能替代什么 |
| --- | --- | --- |
| 工具名白名单/注册表 | 阻止模型调用任意不存在能力 | 具体资源授权 |
| 输入 Schema | 限制字段结构与范围 | 参数的租户归属检查 |
| READ/WRITE 分类 | 表达副作用能力 | 用户本人是否有写权限 |
| 调用上限 | 约束成本与循环 | Provider 账单精确结算 |
| semaphore | 限制工具同时执行数 | 跨进程分布式并发限制 |
| timeout | 避免无限等待 | 已执行外部副作用的回滚 |
| confirmation | 为需要的写操作提供决策点 | 防重复执行、签署与审计 |

工具可以提交异步任务和显式 depends_on 的 DAG chain。链的边来自程序，不应任由模型构造无限依赖；要拒绝循环、未知依赖和越权步骤。继续执行失败分支应由 continue_on_error 明确表达。

## 6. 模型网关与结构化输出

ModelGateway 屏蔽 Provider 细节，支持 HTTP/兼容接口、LangChain 或测试实现。结构化输出用 JSON Schema/Pydantic 约束计划、决策、证据评估与报告。

失败要区分：

- Auth：Key 或权限错误，通常不能靠立即重试修复。
- RateLimit：429，需要退避并遵守服务约束。
- Request：模型名、参数或上下文错误。
- Server：上游暂时不可用，考虑有界重试。
- Timeout：连接、首响应、流中空闲或总预算分别处理。
- Response：格式、Schema 或内容缺失，不能把坏 JSON 当正常答案。

结构化输出成功率要独立评估；不能把「JSON 合法」当作「事实正确」。repair 或重试会新增成本，必须纳入 usage 和延迟。

### 流式超时

持续有内容的长响应与完全卡死不同。代码区分首响应、空闲和完成宽限，并在等待时发布进度。总任务预算仍限制无限延长；只收到 reasoning 进度而没有可用内容时，也需要按策略结束或有限恢复。

## 7. 上下文预算与压缩

模型窗口要分配给系统规则、可信项目背景、历史消息、附件、证据和预留输出。不能把所有 Chunk 直接拼进去。

当前 Runtime 会选择历史消息并压缩上下文，记录压缩 Token、消息数等信息。应保留目标、约束、证据引用和最近任务状态；摘要可能丢掉否定、数值和用户修正，所以压缩后仍应能回到原始持久化消息。

优化顺序可为：过滤无关历史 → 去重 → 截断低价值工具原文 → 保留证据摘要和 ID → 必要时摘要。压缩不应把多个租户上下文混在一起，也不能让旧摘要覆盖新指令。

## 8. Redis Streams 任务队列详解

### 8.1 投递与消费

默认 Stream=shinkou:research-tasks，Group=ai-service，并发 8，max_retries=3。入队用 XADD，消费用 XREADGROUP，未确认消息保存在消费者组的 Pending Entries List，完成后 XACK。

XACK 只确认组内处理状态，不直接删除 Stream 中的消息；Stream 清理与 Pending 保留需要单独规划。当前有近似 maxlen 裁剪，不应把队列当永久审计账本。

### 8.2 崩溃回收

Worker 先 XAUTOCLAIM 回收 idle 达 30 秒的 Pending，再读新消息。它把未完成消息转移所有权，使崩溃消费者留下的任务有机会重新执行。[Redis XAUTOCLAIM 官方说明](https://redis.io/docs/latest/commands/xautoclaim/)可用于核对命令语义。

但是模型调用很可能超过 30 秒，因此当前每 10 秒 XCLAIM 自己的消息刷新 idle，避免活跃任务被另一 Worker 抢走。这个心跳解决了「长任务误判为死亡」的重要问题。

### 8.3 为什么还不是 exactly once

如果 Provider 已计费但 Worker 在保存结果前崩溃，消息会再次执行；Redis 心跳网络抖动也可能造成两个进程同时认为自己可以执行。Runtime 的 _active_runs 只在本进程有效，终态快照也不是跨进程原子占用锁。

增强方案：以 runId 为业务幂等键、数据库条件认领/带 fencing token 的租约、幂等结果提交、外部请求幂等能力、步骤级持久化收据。仍需承认外部模型在某些失败窗口下无法证明零重复计费。

### 8.4 重试的两种含义

队列 handler 抛异常时，可以用新的消息 attempt 重新入队；Runtime 对预期模型/工具失败会保存 FAILED 终态并正常结束，队列不会因此自动重跑整个分析。用户显式重试应创建新 Run，以保留历史和成本归因。

这比「失败一律重试三次」更准确。超出次数后的当前实现主要保留失败统计/运行状态，不能声称已有完整死信队列和管理面板。

### 8.5 本地回退

队列初始化连接 Redis 失败时可退到进程内。开发便利性提高，但持久化与跨进程能力下降；生产是否允许静默回退应明确，否则界面显示「已接受」但重启后任务丢失会违背预期。已经连接 Redis 后再发生运行期断连，不等于自动把 Pending 和新任务无损迁移到内存，必须按实际异常处理另测。

## 9. 快照、事件和 Checkpoint 的区别

| 机制 | 当前实现 | 保证及限制 |
| --- | --- | --- |
| Python EventBus | 进程内历史与订阅 | 实时通知与有限回放；重启不等于事件全恢复 |
| DurableRunRepository | 内存热状态，镜像到 Redis JSON，TTL 30 天 | 冷读可恢复快照；不自动恢复全部协程/执行栈 |
| Java agent_run_events | PostgreSQL 事件记录 | 支持已落库业务事件回放；依赖回调正确到达和处理 |
| PostgreSQL 业务 Run/报告 | 长期业务状态与结果 | 与 Python 快照可能短暂不一致，需要协调 |
| LangGraph checkpointer | legacy 图可注入参数 | 当前主路径不能据此声称有持久化节点级续跑 |

「可查看历史」「能从快照重建页面」「能重新执行任务」「从上次工具调用之后精确续跑」是四种不同能力。面试必须明确演示的是哪一种。

Redis 快照本地命中优先也会带来多进程缓存新鲜度问题；共享 Redis 不自动让每个进程的热对象实时同步。分布式取消/暂停应验证路由、刷新和状态版本。

当前 Runtime._callback 发送失败会记录日志，未见该函数内持久化重投递或有界重试；因此事件到达 Java 的可靠性不能由 Python 本地 EventBus 或 Redis 快照代为保证。若需要可靠回调，应增加发送收据、重试/补拉和幂等消费，而不是只把 HTTP timeout 调大。

## 10. 取消、暂停、计划修改与终态

取消通常是协作式：设置取消状态，在决策/工具/等待检查点检查，再取消可中断任务。前端断开 SSE 不等于取消；已发送的模型请求可能仍产生费用，外部写入也可能已完成。

暂停意味着不再启动后续步骤，是否立即中断当前步骤需要明确。计划修改要有 plan_version，运行时读取新计划并判断已完成步骤，避免修改后重复执行同一副作用。

终态保护要防止「取消后迟到的 completed 回调又改回成功」。Java 代码中已有部分终态协调逻辑，但多实例/乱序消息还应通过条件更新和故障测试验证，不能只依赖事件到达顺序。

## 11. Prompt 工程的面试深度

Prompt 应清楚声明角色、输入来源、任务边界、输出 Schema、证据规则、不确定性表达与工具限制。程序强制的规则不能只留在 Prompt。

版本记录至少包含 Prompt 内容或哈希、Schema、模型与生成参数、检索/切片版本、工具版本和数据集版本。Runtime accept 保存 Prompt 快照，并对决策 Prompt 与 Schema 生成指纹，有利于结果复现。

比较 Prompt v1/v2 应固定模型、语料、检索、评估集和预算；模型服务更新仍可能造成差异，要记录调用日期与版本。不能只挑一条看起来更好的回答。

## 12. 评估指标与计算

| 指标 | 定义 | 常见误区 |
| --- | --- | --- |
| Recall@K | Top K 中召回的相关证据数 / 标注相关证据总数 | 只命中资产不等于命中关键 Chunk |
| Precision@K | Top K 相关证据数 / 实际返回数或约定 K | 必须统一不足 K 时分母 |
| MRR | 每个问题首个相关结果排名的倒数，再取平均 | 只能强调首命中，不能衡量全部事实覆盖 |
| nDCG@K | 分级相关收益按排名折损并归一 | 需有可靠分级标签 |
| 引用正确率 | 被引用证据真正支持断言的比例 | 引用 ID 存在不等于支持 |
| 事实覆盖率 | 应回答事实中有证据支持并表达的比例 | 长答案不一定覆盖更全 |
| 无证据事实率 | 缺乏支持的事实断言占比 | 需要定义断言单位并审阅 |
| JSON/Schema 成功率 | 直接输出及修复后成功率分别统计 | 只统计最终成功会隐藏大量修复成本 |
| 任务成功率 | 达成任务验收目标的运行比例 | HTTP 200 / Run COMPLETED 不等于业务正确 |
| P50/P95/P99 延迟 | 延迟分布不同分位 | 平均值掩盖尾延迟 |
| 工具失败率 | 失败调用 / 总调用，按工具与原因分组 | 空检索不总是工具失败 |
| 成本 | 模型、Embedding、搜索和计算开销 | 只记最终一次回答会漏掉重试与审查 |

一个问题可能有多个合理答案，评估应围绕 required_facts、forbidden_facts、引用与条件，而不是严格字符串匹配整段答案。

## 13. 数据集设计与 LoRA 边界

评估集应覆盖中文/英文、数字、否定、同名实体、跨文档证据、冲突、过期资料、无答案、指定文件、权限负例、提示注入和长上下文。开发/测试集分离，避免针对少数样例过拟合。

LoRA/QLoRA 在当前材料中是可选窄任务实验，不能说已训练并上线。企业资料记忆优先用 RAG，便于更新和权限隔离；微调更适合稳定的输出习惯或证据支持性分类。

若做证据分类微调：先定义支持/反驳/不足等标签，固定 Prompt 基线与测试集，去重防泄漏，比较 Macro-F1、各类 Recall、冲突召回、校准、延迟和成本。QLoRA 减少训练资源的原理与实际模型精度收益是两件事。

## 14. 最有说服力的演示

准备同一问题的四组运行：无资料时明确缺口；有正确证据时给引用；两份资料冲突时保留冲突；恶意文档试图改工具权限时仍被程序限制。再演示断线重连、取消、Worker 重投递和报告版本变化后的重新审查。

每次保存输入、配置、数据版本、事件、结果、指标和失败原因。这样的证据比「用了多个 Agent，所以更智能」更能经受追问。

## 15. 队列保留：消费者组不保护消息正文免于裁剪

Redis 允许删掉/裁剪仍在 PEL 的消息，留下 Pending ID 却没有 payload。当前 XADD 使用近似 maxlen=10000；积压时，未完成任务也可能落到裁剪范围。因此这里只能说具备恢复机制，不能保证无条件至少一次交付。见 [XREADGROUP 的删除语义](https://redis.io/docs/latest/commands/xreadgroup/)。

| 设计问题 | 当前情况 | 需要验证/改进 |
| --- | --- | --- |
| 裁剪上限是否覆盖最长积压 | 固定约 10000 条 | 根据入队/重试率、最长任务和故障停机估算 |
| 被裁剪 Pending 怎么发现 | 需要检查 XAUTOCLAIM 返回信息 | 记录丢失正文 ID，协调业务状态并告警 |
| 重试耗尽如何交接 | 运行失败与统计，不是完整死信系统 | 持久失败收据、可审阅重派和成本归因 |
| 多组消费是否都可安全裁剪 | 当前主要一组 | 扩组后重新定义保留水位 |

若每秒新入队 5 条，10000 条只约覆盖 2000 秒的写入历史，还未计重试；这是容量算例，不是实测。近似裁剪不会保证精确只保留该条数，也不会按某条任务的业务重要性保留。

官方 XAUTOCLAIM 返回后续扫描游标；单次扫描量也有边界。当前 _next 每次 start_id=0-0、count=1，未推进返回游标；当靠前 PEL 长期不满足回收时，后面条目回收可能延迟，这是应以大 PEL 场景验证的代码推导。见 [XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/)。

Redis 最新文档中的 ACKED/DELREF 等裁剪引用策略是后续版本能力，不能直接写进当前 Redis 7.4 配置。应核对命令的 since/version 标注，见 [XTRIM](https://redis.io/docs/latest/commands/xtrim/) 与 [Redis 7.4 命令表](https://redis.io/docs/latest/commands/redis-7-4-commands/)。

## 16. 真正接入图检查点，还需要哪些条件

LangGraph 的 checkpointer 按 thread 保存图状态，store 则表达跨 thread 的应用数据；框架级 thread 与本项目的数据库 Thread/Run 不是自动一一绑定。见 [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。

官方检查点在 super-step 边界保存状态，并区分成功节点的 pending writes；内存 Saver 与持久化 Saver 的重启能力不同。不能把一个 RunRecord JSON 当同等的图执行检查点。参考 [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)。

若将来把兼容图切到主链路，应验证：持久化后端、thread/run 映射、执行配置兼容、计划修改、工具收据、重复副作用、Schema 迁移和恢复测试。即使能恢复状态，也无法凭空撤销已经发出的模型/搜索费用。

## 17. 把可靠性承诺改成可测试的命题

「可恢复」应改成具体命题，例如：Worker 被终止后，未 ACK 且正文仍保留的任务，在租约超时后被其他 Worker 认领；终态任务不重开；中间外部调用可能需要成本对账。分别验证，不合并成一句「exactly once」。

安全关闭还应先停止接受新任务，再处理当前任务与 Pending 归属、保存必要状态、关闭事件和连接。超过停止期限被强制结束时，要明确哪些状态可回收，不能只在 finally 中写几行 close 就宣称完成优雅下线。
