# 07. Docker 内各数据系统的原理与职责

这一章回答「为什么有这么多容器」「每个组件里面发生什么」「坏一个会影响什么」。PostgreSQL 业务表与 SQL 详见第 03 章，任务队列协议详见第 05 章。

## 1. 先画数据归属，避免重复存储概念混乱

| 数据 | 主要归属 | 能否轻易重建 | 丢失影响 |
| --- | --- | --- | --- |
| 用户、成员、项目、业务状态 | PostgreSQL | 通常不能从其他系统恢复 | 权限与业务事实丢失 |
| 原文件、附件、生成报告文件 | 业务 MinIO | 有原始上传者副本才可能 | 原始证据或交付物丢失 |
| Chunk 正文/定位/版本 | PostgreSQL | 可从原文件重新解析，但版本可能变化 | 引用和检索受影响 |
| 向量及标量索引数据 | Milvus 及其底层存储 | 在模型/数据/版本可复现时可重建 | 向量召回停用或不完整 |
| Milvus 元数据 | milvus-etcd | 不应假设只靠向量对象自动恢复 | Collection/segment 等管理信息受损 |
| Milvus 对象文件 | milvus-minio | 需按 Milvus 恢复/重建流程 | 索引/持久数据不可读 |
| 检索/Embedding/搜索缓存 | Redis 或内存 | 多数可重算 | 延迟/外部成本上升 |
| 队列 Pending、运行快照 | Redis | 不能都当成可丢缓存 | 任务恢复和进度受影响 |
| 图实体关系 | 内存或 Neo4j | 取决于抽取可复现和来源保留 | 图检索能力丢失 |

同一份文件可能存在原文件、解析文本、Chunk 和向量，它们是不同表示，并非无意义复制。每种表示需要独立版本、权限与生命周期策略。

## 2. PostgreSQL 引擎内部补充

### 2.1 查询路径

连接收到 SQL → 解析/分析 → 重写与规划 → 执行器按计划访问表和索引 → shared buffers/操作系统缓存/磁盘 → 结果返回。慢查询可能发生在连接等待、锁等待、执行、磁盘或结果网络传输，不能只看 SQL 文本长度。

### 2.2 写入路径

修改内存页并生成 WAL，提交持久化规则影响何时确认成功，后台逐步将脏页写入数据文件。Checkpoint、WAL、autovacuum、索引维护都影响延迟和磁盘。

### 2.3 与本项目相关的压力

大量小事件增加写入频率；大报告 TEXT/JSONB 影响 I/O 和膨胀；索引时逐 Chunk 插入增加 round trip；统计全表聚合消耗读取。可选优化分别是事件批量、保留期、批量写、正确索引和预聚合，不宜混成一个「加缓存」方案。

## 3. Redis：一个服务承担多个不同等级职责

当前镜像 Redis 7.4-alpine，命令启用 requirepass 与 appendonly yes，数据卷挂到 /data。没有配置 Sentinel/Cluster、独立持久队列实例或明确 maxmemory-policy。

### 3.1 数据结构与项目映射

| Redis 能力 | 本项目用途/可比较方案 | 关键原理 |
| --- | --- | --- |
| String / JSON 字符串 | 验证码、计数、快照、序列化缓存 | 简单键值，支持 TTL 和原子增量 |
| Stream | 研究任务队列 | 有序消息 ID、消费者组、Pending、ACK/claim |
| Lua | 限流计数与首次过期、验证码验证后删除 | 在 Redis 内原子执行一段逻辑 |
| INCR | 缓存版本、限流计数 | 单个命令原子，复合步骤需脚本/事务 |
| TTL | 验证码有效期、缓存、30 天运行快照 | 过期时间不等于备份保留策略 |
| 本地 asyncio.Lock | AI 同键缓存加载合并 | 仅本进程有效，不是 Redis 分布式锁 |

不应为了覆盖八股文而说项目已经使用 Hash、ZSet、Bitmap、HyperLogLog。可以解释它们适合什么，但要标注为知识扩展。

### 3.2 Redis 为什么快

主要数据在内存，命令处理路径紧凑，网络使用事件驱动，并尽量避免传统关系 JOIN 和磁盘随机读。不能简单概括为「所有功能永远只有一个线程」；现代 Redis 的网络等工作可以有额外线程，命令主执行的串行语义也不代表不会阻塞。

大 key、长 Lua、大范围扫描、巨量返回和持久化开销都会抬高尾延迟。生产不要对大实例随意执行 KEYS *，诊断应优先按具体前缀与 SCAN 分批。

### 3.3 原子限流

AuthRateLimiter 的 Lua 先 INCR，第一次计数时 EXPIRE，避免「计数成功后进程崩溃，过期没设置」留下永久限流键。登录同时使用 IP 请求数、账号/IP 失败次数；短信还有手机号与冷却时间维度。

它属于时间窗口计数思路，不是严格平滑令牌桶。窗口边界可能短时放过较多请求；如果需要更平滑的速率，可以设计滑动窗口或令牌桶，但需衡量存储/计算代价。

验证码验证与删除也需要原子，避免同验证码被并发使用两次。失败次数和正确结果不能在多个独立 GET/DEL 请求之间留下竞态。

### 3.4 缓存穿透、击穿、雪崩

- 穿透：频繁查询不存在内容。先校验范围，可短暂缓存空结果，但权限错误不要缓存成跨用户共享结果。
- 击穿：热点键过期，很多请求同时重建。当前 get_or_set 用同进程锁合并；多进程仍可能各自向 Provider 请求。
- 雪崩：大量键同时失效或 Redis 不可用。可用 TTL 抖动、限流、分层降级和容量预留。

AI 默认检索 TTL 300 秒、网页 900 秒、Embedding 86400 秒、本地缓存上限 2000 条。上限是条数，不是总字节，长文缓存可能仍占较大内存。

### 3.5 内存淘汰与队列不能混为一谈

如果 Redis 同时存可丢缓存和不可轻易丢的任务/快照，随意使用 allkeys-lru 等淘汰策略可能淘汰关键状态；noeviction 则可能使新写失败。生产可拆实例或建立明确资源/持久化策略。

选择不同逻辑 DB 不会隔离内存、CPU 和故障域。当前 Java 配置使用 database 0，其他客户端也要核对实际连接配置。

### 3.6 RDB、AOF、复制

RDB 保存时间点快照，AOF 记录写命令并可重写压缩。appendonly yes 只表示启用 AOF，仍应检查实际 fsync 策略和恢复行为；常见 everysec 策略不是零数据丢失承诺。参见 [Redis 持久化说明](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)。

复制、Sentinel 和 Cluster 解决不同问题：副本复制数据，Sentinel 参与主节点故障切换，Cluster 主要分片并管理其拓扑。当前只有单实例，不能把这些说成已经部署。

### 3.7 故障后的业务影响

Java 验证码/限流可能失败；AI 缓存/队列/快照部分可回退内存，但可靠性降低。原本在 JVM 的 HttpSession 不会因为 Redis 重启就被「共享 Session 全量清空」，因为当前并没有该集成。对不同职责要按代码逐条判断。

## 4. Milvus：向量数据库到底做了什么

### 4.1 向量检索与数据库过滤

输入向量 q，在大量文档向量中找近邻，再按租户、项目、资产条件筛选或在索引执行中结合过滤。ANN 牺牲部分精确性换取吞吐和延迟；最终命中还需回 PostgreSQL 验证正文和权限。

Milvus 不负责用户登录、报告审批或原始文档语义解释。它返回相似候选，不判断事实真假。

### 4.2 为什么不扫描全部向量

暴力比较复杂度近似与 N×D 成正比，数据和维度增长后成本明显。常见 ANN 算法知识：

| 索引 | 核心思路 | 主要取舍 |
| --- | --- | --- |
| FLAT | 精确扫描 | 召回基准好，数据大时慢 |
| IVF | 聚类分桶，只查部分桶 | 桶数/探测数影响训练、召回和延迟 |
| HNSW | 多层近邻图导航 | 查询快，但建图与内存有代价 |
| PQ/量化 | 压缩向量近似距离 | 降内存，可能损失精度 |
| AUTOINDEX | 交给当前引擎自动选择/管理 | 仍需看版本、环境和实际性能 |

本项目明确创建 AUTOINDEX + COSINE，以上其他索引仅是面试算法扩展。

### 4.3 standalone 架构

Compose 执行 milvus run standalone，把主要引擎组件集中部署；配套 etcd 维护元数据，MinIO 存持久对象文件，Milvus 自己也有数据卷。分布式版本的控制、查询、数据与索引职责可独立扩展，但当前不是多节点集群。参见 [Milvus 2.4 架构](https://milvus.io/docs/v2.4.x/architecture_overview.md)。

不要因为容器有三个就认为 Milvus 有三个副本：它们承担不同职责，任何一个关键依赖失效都可能影响向量能力。

### 4.4 Segment 与内存

向量数据进入写入缓冲/增长中的 segment，后续封存、持久化和构建索引，查询按当前加载状态访问数据。load_collection 会影响内存和启动时间，索引构建与 compaction 也占 CPU、内存和 I/O。

因此「Milvus 端口通了」不代表集合已加载或数据立即可见；需要检查集合 schema、实体数量、索引与加载状态、实际 search。

### 4.5 一致性与 flush

当前集合使用 Bounded 一致性，允许受控的可见性滞后；Strong、Session、Eventually 等有不同读取语义。flush 与读取一致性是不同机制，调用 flush 不能被解释为「PostgreSQL 和 Milvus 一起原子提交」。见 [Milvus 2.4 一致性](https://milvus.io/docs/v2.4.x/consistency.md)。

### 4.6 容量估算

float32 原始向量约 N×D×4 字节。假设 100 万条、1536 维，仅原始数值约 6.144 GB，未含索引、标量、元数据、副本与内存运行开销。这个是算式示例，不是项目已经测过百万向量。

Chunk overlap、版本保留和重复索引会增加 N；压缩降低空间可能影响召回。应同时观察召回、查询尾延迟、插入速率和重建耗时。

### 4.7 与 pgvector/Elasticsearch 的取舍

把向量放 PostgreSQL 可减少组件和双写，但会与业务负载共享资源；Milvus 能独立扩展向量能力，同时带来运维与一致性成本。Elasticsearch 的倒排与全文能力强，是否引入取决于真实检索需求；本项目当前没有部署它。

这里说明设计权衡，不应把组件数量多直接当作技术更先进。

## 5. etcd：为什么不是另一个 Redis

### 5.1 数据性质

etcd 面向少量关键配置、元数据与协调，强调一致性和 watch/版本语义；Redis 面向低延迟数据操作，项目中用于缓存和任务。Milvus 需要可靠地维护其元信息，才引入 etcd，而不是把向量正文存进去。

### 5.2 Raft 原理

Raft 集群通过 leader 和多数派确认维护复制日志。多数派不可用时不能继续安全提交新写入。3 节点可容忍 1 节点失效，5 节点可容忍 2 节点，但需考虑独立故障域和延迟。当前只有一个 etcd 进程，不能容忍该节点丢失。参考 [etcd 的设计定位](https://etcd.io/docs/v3.5/learning/why/)。

### 5.3 revision、compaction、snapshot、defrag

- revision 表达键空间修改的版本，可用于 watch 和比较。
- compaction 清理旧历史版本，避免无限增长；太旧的 watch 起点可能需要全量重读。
- snapshot 是恢复用备份概念，不能与自动清理历史混为一谈。
- defrag 回收后端文件内可回收空间，操作时要考虑版本和可用性。

当前配置 revision 模式自动压缩、保留 1000 revisions、后端配额 4 GiB、snapshot count 50000。最后一项是内部快照触发相关参数，不等于已经设置每 50000 条做可离机备份。

### 5.4 失效如何处理

先确认磁盘、配额、日志和服务状态，不能只删除 /etcd 重新启动。清空 etcd 而保留 Milvus 对象文件会破坏元数据对应关系。恢复需要符合 Milvus 与 etcd 的配套备份策略，或有计划地从业务原始数据重新建向量库。

## 6. MinIO：两套对象存储必须分开讲

### 6.1 业务 MinIO

保存原文件、Agent 附件和生成物；Java/Python 使用 S3 兼容 SDK，通过 bucket 和 object key 定位。业务键中带 workspaces/projects 等层级前缀，方便归属、审计和生命周期。

前缀只是命名，不会自动执行成员权限。浏览器下载走有权限检查的业务接口，或由后端签发受时限约束的 URL；不应把私有文件永久设为匿名公开。

### 6.2 Milvus 专用 MinIO

只供 Milvus 持久化内部对象使用。它的 bucket、文件组织和生命周期应由 Milvus 管理，业务代码不应随意删除这些对象或把普通上传混进去。

同样的 9000 是各自容器内部端口，不冲突；只有业务 MinIO 默认发布宿主 9000/9001。两个服务的数据卷、凭据和故障影响分别分析。

### 6.3 对象存储与文件系统

对象以 key + metadata + bytes 组织，不具备通用 POSIX 文件系统的所有操作语义；「目录」通常是前缀。改名一般不能假设与本地原子 rename 相同，上传/下载/删除要按 API 行为设计。

大文件可用流式或 multipart，避免 Java/Python 把整个文件装进内存；上传完成后的 metadata 与配额仍要和数据库协调。ETag 不应普遍当成原文件 MD5，尤其涉及 multipart 等情况，项目自行保存 SHA checksum 更明确。

### 6.4 minio-init 做了什么

设置连接别名 → mc mb --ignore-existing 创建 bucket → mc anonymous set none 关闭匿名访问。它是可重复的初始化任务，成功退出码 0 是预期。

ignore-existing 只处理 bucket 已存在，不代表所有权限和数据状态都自动修复。root 账号方便开发，生产可为应用建立最小权限账号；当前 Compose 没有配置完整的独立 IAM 策略。

### 6.5 持久化、高可用和备份

当前是单容器、单数据路径，不能声称部署了多节点纠删码集群。MinIO 产品支持的容错能力取决于实际拓扑，挂了一个 volume 不等于具有多盘/多节点容错。

业务文件备份要保留 object key、内容与必要 metadata，并和 PostgreSQL storage_key 对应；凭据加密密钥也要独立保管。版本控制和生命周期策略是可选方案，当前配置没有证据表明已启用。

## 7. Neo4j：图数据库与图谱质量

### 7.1 图模型

节点表达实体，关系表达连接，属性保存类型、来源和其他信息。与关系库 JOIN 相比，图遍历适合多跳关系探索；它不会自动把自然语言中的关系变成可信事实。

当前 GraphNode/GraphEdge 都带 workspace_id/project_id。内存存储以复合键隔离；Neo4j 适配器用参数化 Cypher，MERGE 节点、MATCH 端点并 MERGE RELATED 关系。

### 7.2 MERGE 与唯一约束

MERGE 表达匹配或创建，但并发下的数据唯一性仍应结合适当约束验证。实体同名、别名、大小写和跨文档共指会影响去重；不能只按自然名称合并所有对象。

本次未见部署完整图谱 schema/索引管理流程的证据；可提出对租户+项目+实体 key 建约束作为增强，并用 EXPLAIN/PROFILE 检查查询。

### 7.3 当前检索边界

适配器按工作区/项目、查询词和有限关系范围检索，不是任意路径推理引擎。知识抽取支持 heuristic 或 LLM，默认 GRAPH_MODE=memory，GRAPH_EXTRACTION_MODE=heuristic。

图谱必须保留边的来源、置信/冲突和时间，否则「A 依赖 B」可能是过期、否定或模型误抽取。图结果应作为证据入口，关键结论仍回到文档。

### 7.4 资源和协议

7687 是 Bolt，7474 是 Browser/HTTP 入口。heap 管对象与执行，page cache 用于数据页，操作系统也需要内存。当前默认 heap initial 512m/max 1G、pagecache 512m，不能把这些简单相加后就认定容器总内存足够。

Compose 的 advertised address 为 localhost 的宿主映射，适合本地交互；跨机器客户端需要重新核对对外通告地址。配置 apoc.* unrestricted 不代表 APOC 插件 jar 必然已经安装，plugins 卷也需要检查实际内容。

## 8. MCP Server：协议边界

MCP 用统一方式发现/调用工具，但不自动解决用户身份、租户授权、工具可信度和副作用。项目的 mcp-server 复用 AI 镜像，使用 streamable-http 监听 8001，只在 mcp profile 中启动。

AI 侧默认 MCP_ENABLED=false，允许工具默认 search_knowledge/search_graph；MCP profile 启动成功不等于 AI 侧已开启调用。MCP_API_KEY 与内部 API Key 要按各入口验证。

面试要能解释四层：工具发现得到描述和 Schema → 客户端映射到本地注册表 → 调用时注入可信作用域 → 结果按不可信数据处理。远程工具返回的文本不能改系统规则。

当前服务禁用继承自 Uvicorn 的健康探针，因为监听进程不同；运行状态需用专门 MCP 协议调用验证。扩展时还要管理协议兼容、超时、断连、远程版本和秘密分发。

## 9. 故障域对照表

| 故障组件 | 主要用户症状 | 可保留能力 | 恢复核心 |
| --- | --- | --- | --- |
| PostgreSQL | 登录查询、项目、报告等广泛失败 | 已加载页面短时可见 | 数据恢复、连接、迁移和权限 |
| Redis | 验证码/限流异常，AI 回退/排队异常 | 已持久化业务报告可能可读 | 持久化、Pending、幂等与状态协调 |
| Milvus | 向量检索失败/慢 | 关键词路径能否继续以实际异常处理为准 | 集合、索引、依赖和模型一致性 |
| etcd | Milvus 元数据操作异常 | Java 基础业务可能仍正常 | 配套恢复，避免清空元数据 |
| Milvus MinIO | 向量底层对象不可读 | 业务原文件仍在另一 MinIO | 对象与元数据对应关系 |
| 业务 MinIO | 上传、下载、解析文件失败 | 已落库文本报告可能仍可读 | 原文件与 storage_key 对账 |
| Neo4j | 图查询失败 | 常规 RAG 路径依策略可用 | graph mode、图数据和来源 |
| MCP | 扩展工具不可用 | 内置工具可继续的范围依策略 | 连接、认证、工具白名单 |

注意启动依赖比运行期耦合更强：backend 在 Compose 里等待 ai-service 健康才能首次启动；这与「AI 已启动后宕机，历史报告 API 是否仍可读」是两个场景。检索错误是否自动回退也必须看当前分支，不能只因存在关键词代码就承诺所有向量故障都会透明降级。

## 10. 面试官要求删组件时怎么答

先问约束：语料规模、检索质量、故障目标、团队维护成本。如果只做小规模单机演示，可讨论减少图谱/MCP、向量内存实现或合并存储；如果强调独立扩展向量检索，则保留 Milvus 的收益更明确。

回答要证明知道每个组件的成本与替代关系。真正成熟的设计不是组件最多，而是用证据说明当前复杂度解决了哪些真实问题。

## 11. Redis 锁补充：安全释放与旧持有者写入是两个问题

带过期的锁需要唯一持有者标识，释放时原子比较后再删除，避免 A 超时后删掉 B 的锁。当前 Redis 7.4 不能照搬最新文档里的 DELEX，需用该版本支持的机制。参考 [Redis 分布式锁说明](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)。

但安全释放不阻止 A 在长暂停后继续完成外部调用。可为每次认领分配单调 execution_epoch，并要求结果提交核对 epoch；数据库拒绝旧执行者提交，这通常称为 fencing 思路。它仍不能撤销 Provider 已完成的计费。

~~~text
A 认领 Run，epoch=41
→ A 长暂停，租约过期
→ B 重新认领，epoch=42
→ A 恢复并返回结果
→ 提交阶段发现 41 不是当前 epoch，拒绝覆盖
~~~

当前项目没有完整的共享 epoch 协议，这里是扩展设计。评审时要继续问：epoch 在哪里原子递增、认领是否持久化、所有写入是否校验、重复完成是否幂等，以及无 fencing 能力的外部系统怎么办。

## 12. Milvus 可见性与 etcd 维护的精确边界

Milvus 用 GuaranteeTs 表达查询等待到哪个可见性水位；Strong、Bounded、Session、Eventually 的差异是读取语义，不是「准确率高低」。Session 的写入可见性与客户端写时间有关，也不是浏览器登录 Session。见 [Milvus 2.4 一致性机制](https://milvus.io/docs/v2.4.x/consistency.md)。

项目实验应分别测：写成功后立刻检索、跨客户端检索、删除后立刻查询、重建期间回表过滤。即使 Milvus 达到 Strong，也不会让 PostgreSQL、MinIO 和缓存一起变成强一致。

etcd 压缩旧 revision 后，空洞可被自身复用，但文件系统占用不一定下降；defrag 才处理后端碎片，在线执行还会暂时阻塞该成员读写。见 [etcd 3.5 维护文档](https://etcd.io/docs/v3.5/op-guide/maintenance/)。当前是单成员依赖，维护阻塞没有其他成员兜底，需把窗口与 Milvus 行为一起验证。

## 13. Neo4j 的 MERGE 需要区分节点和关系

MERGE 一个节点模式并不自动提供任意并发唯一性，应结合标识属性约束；但两个已绑定端点之间的特定关系 MERGE 有锁与再次匹配行为，不能反过来声称所有关系 MERGE 都必然并发重复。参见 [Neo4j 5 MERGE](https://neo4j.com/docs/cypher-manual/5/clauses/merge/)。

当前节点键含 workspace/project/key，可考虑相应组合唯一约束，并核对具体版本和发行类型的功能；Community 与 Enterprise 的约束能力要分清，不把 Enterprise 的 Node Key 功能默认写到当前 Community 镜像。

## 14. 对象 ETag、内容 checksum 与具体版本

S3 的 ETag 在 multipart 等情况下不是完整文件 MD5，因此不能通用地拿它替代内容校验。该行为可参考 [S3 对象完整性说明](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html)。这是一份 S3 API 参考，不代表本项目使用 AWS，也不证明每个 MinIO 版本实现细节完全一致。

本项目用业务 checksum 表达内容去重更明确；仍需统一 checksum 算法、基于原始 bytes 还是解析后文本、大小写/编码以及重复文件处理。产品功能应核对 [仓库使用的 MinIO 发布标签](https://github.com/minio/minio/tree/RELEASE.2025-04-22T22-12-26Z)，不要把后续 AIStor 文档中的能力默认当成此镜像已经启用。

## 15. MCP：传输规范与当前无状态服务

Streamable HTTP 规范要求考虑 Origin 验证和认证，并允许服务分配 MCP-Session-Id；若分配，客户端需按约定携带并处理会话终止。参见 [MCP 2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)。这是明确选定的参考版本，不是声称仓库 SDK 支持全部该版本能力。

当前 mcp_server.py 设置 stateless_http=True、json_response=True，不能要求它必然分配有状态会话 ID。容器内监听 0.0.0.0 用于网络互通，与是否把宿主机 8001 对外公开是两个问题；部署审查需要分别看 bind、ports、认证与来源校验。
