# 03. PostgreSQL、业务建模、索引与事务

当前 Compose 使用 PostgreSQL 16-alpine，宿主机默认 15432，容器内 5432。数据库结构以 apps/backend/src/main/resources/db/migration 的 V1—V35 为依据。早期数据库设计文档可提供背景，最终表结构必须叠加后续 ALTER、RENAME 和 DROP 后理解。

## 1. 数据库在系统中的地位

PostgreSQL 保存用户与租户关系、业务状态、文档 Chunk 正文、报告、审查、行动项和事件。Milvus 是可由原文件/Chunk/Embedding 配置重建的向量索引，MinIO 保存二进制文件，Redis 保存运行中的辅助状态与部分恢复信息。

「数据库是真实来源」要进一步拆解：原文件的真实来源在 MinIO，业务权限和资源关系在 PostgreSQL，向量在 Milvus，瞬时进度可能先在 Python 内存。不存在一个数据库事务覆盖全部这些系统。

## 2. 关系图与基数

~~~mermaid
erDiagram
    USERS ||--o{ WORKSPACE_MEMBERS : joins
    WORKSPACES ||--o{ WORKSPACE_MEMBERS : has
    WORKSPACES ||--o{ PROJECTS : owns
    PROJECTS ||--o{ KNOWLEDGE_ASSETS : contains
    KNOWLEDGE_ASSETS ||--o{ ASSET_CHUNKS : splits
    PROJECTS ||--o{ RESEARCH_RUNS : executes
    RESEARCH_RUNS ||--o{ REPORTS : produces
    PROJECTS ||--o{ AGENT_THREADS : contains
    AGENT_THREADS ||--o{ AGENT_MESSAGES : contains
    AGENT_THREADS ||--o{ AGENT_RUNS : executes
    AGENT_RUNS ||--o{ AGENT_RUN_EVENTS : emits
    REPORTS ||--o{ PROJECT_REVIEW_RUNS : reviews
    REPORTS ||--o{ ACTION_ITEMS : derives
    USERS ||--o| USER_STORAGE_USAGE : accounts
~~~

这是关键关系示意；外键中还包括创建者、负责人、验收人等多个用户角色，不是完整物理 ER 图。

## 3. 全部业务表按领域拆解

### 3.1 身份、工作区与项目

| 表 | 关键字段/约束 | 设计意图与追问 |
| --- | --- | --- |
| users | id、user_name、phone_number UNIQUE、password、status、password_changed_at | 唯一手机号阻止并发重复注册；密码不能明文；修改密码后的会话失效还要应用处理 |
| workspaces | id、code UNIQUE、name、status、preferences JSONB | 工作区是组织与租户边界；偏好字段适合低频、可扩展配置 |
| workspace_members | workspace_id、user_id、role、status、部门/职位；UNIQUE(workspace_id,user_id) | 用户与工作区多对多；同一人不能重复成为同工作区的多条成员 |
| workspace_invitations | 工作区、手机号、状态及邀请附加信息 | 邀请状态和成员关系是两个阶段，要处理重复邀请、过期、激活和并发接受 |
| projects | workspace_id、code、visibility、status、created_by、chunking_config JSONB | UNIQUE(workspace_id,code) 表达租户内编码唯一；项目不应仅按 id 判权限 |
| project_plans | project_id 为主键；workspace_id、objective、problem、success_metrics、constraints、deadline | 当前每项目一份规划；需要历史版本时应另建版本结构，不能把更新时间当版本历史 |

### 3.2 资料与检索

| 表 | 关键字段/约束 | 设计意图与追问 |
| --- | --- | --- |
| knowledge_assets | project_id、checksum、storage_key、source_url、content、parse_status、index_status、error_message | UNIQUE(project_id,checksum) 用于项目内内容去重；原文件存储和索引内容分离 |
| asset_chunks | asset_id、chunk_index、content、page_number、section_title、offset、parser/chunking version、checksum、embedding_model | UNIQUE(asset_id,chunk_index) 保证同资产切片顺序唯一；外键 ON DELETE CASCADE |
| asset_chunks.search_vector | to_tsvector('simple',content) 的生成列，GIN 索引 | 对正文维护关键词检索结构；不是向量 Embedding |

V16 补充切片定位和模型元数据，V17 明确移除旧 embedding 列，向量转移到 Milvus。不要说当前仍在 PostgreSQL 用 pgvector 做主向量检索。

### 3.3 研究、报告、审查与行动闭环

| 表 | 核心数据 | 关键约束/业务含义 |
| --- | --- | --- |
| research_runs | goal、status、config JSONB、progress、current_step、Token 与耗时 | progress 有 0—100 检查；重试和取消要保留终态语义 |
| reports | run_id、content、version_no、summary、recommendation、citations | 历史报告不应依赖当前模型在线；引用计数不是引用正确性的证明 |
| project_review_policies | require_citations、verify_numbers、escalate_conflicts、label_external | 每项目策略；策略变更不应悄悄改变既有签署含义 |
| project_review_runs | 运行计数、检查、报告 ID/版本、snapshot_hash、report_snapshot、confirmations、签署者和时间 | 审查绑定内容快照；避免新报告沿用旧审批 |
| action_items | owner、due_at、priority、status、来源报告/审查、source_key、完成证据、提交/验收人 | V35 的来源部分唯一索引防重复导入；完成与验收是不同业务事件 |

### 3.4 对话 Agent

| 表 | 核心数据 | 与其他表的分工 |
| --- | --- | --- |
| agent_threads | workspace_id、project_id、created_by、thread_key、title | 一个对话上下文；UNIQUE(project_id,created_by,thread_key) |
| agent_messages | thread_id、client_message_id、role、content、status、attachments JSONB、model_name | 一条消息的稳定内容与展示状态；UNIQUE(thread_id,client_message_id) |
| agent_runs | run_key UNIQUE、thread_id、输入/回答消息 ID、status、error、起止时间 | 一次实际执行；一个线程可多次执行 |
| agent_run_events | run_id、event_type、payload JSONB、顺序 ID | 可用于 SSE 回放；事件表与最终消息正文不能互相替代 |
| agent_attachments | 租户、项目、上传者、文件名、类型、大小、storage_key | V12 后使用对象存储键；不能只按 V10 的 BYTEA 字段讲当前文件存储 |
| agent_token_usage | run_key UNIQUE、项目/用户、输入/输出/总 Token、压缩上下文、model_name | 支持归因和防重复统计；真实账单仍以 Provider 计费口径核对 |

### 3.5 配置、评估、通知与审计

| 表 | 用途 | 面试需要注意 |
| --- | --- | --- |
| workspace_model_configs | 工作区模型、加密凭据、默认模型、创建者、JSONB 配置 | V29 从项目配置迁移；可见性不等于所有用户都能读取明文 Key |
| legacy_project_model_configs | 历史项目模型配置归档 | V29 重命名保留历史，不是运行时主配置表 |
| project_tool_configs | 项目工具连接与凭据 | 工具配置不能让模型自行修改授权边界 |
| project_web_search_configs | 项目与创建者维度的搜索配置 | V26 从通用工具配置分离；UNIQUE(project_id,created_by) |
| prompt_versions | 场景、版本、系统 Prompt、状态 | UNIQUE(workspace_id,scene,version_no)；表存在不代表所有运行都从此动态加载 |
| evaluation_cases | query、expected_answer、期望资产/Chunk、required/forbidden facts、结果 JSONB | 用于固定评估；评分字段的百分制/小数制必须统一 |
| notifications | 接收者、工作区、内容和已读时间 | 未读部分索引支持高频查询 |
| audit_logs | 操作者、作用域、动作、对象、详情、时间 | 记录安全关键变更；普通日志与审计账本的保留目标不同 |
| security_harness_runs | 安全检查批次与汇总 | 检查通过不等于系统不存在漏洞 |
| security_harness_results | 用例、类别、严重度、状态、证据 JSONB | 需要能回溯具体失败证据 |
| user_storage_usage | user_id 主键、used_bytes 非负 | 支持行锁配额；计数与实际对象需对账 |

## 4. 数据类型为什么这样选

- BIGINT 适合大量主键和计数，但浏览器需注意精度。
- VARCHAR 明确约束长度；TEXT 适合 Chunk、报告和描述。
- JSONB 适合变化较多的配置、事件 payload、审查快照；核心关联、状态、经常过滤的列仍宜结构化。
- DATE 表示截止日期，不应混用成有时区的瞬间。
- 当前大量列使用 TIMESTAMP，未带时区；应用和数据库必须明确时区约定。面向多时区扩展时，可评估 TIMESTAMPTZ 表示真实瞬间，API 统一 ISO 8601。
- 金额、价格、比例需要精确计算时使用 NUMERIC；浮点用于相似度等允许近似的量。

追问：JSONB 为什么不把所有字段都塞进去？因为约束、索引、JOIN、迁移可读性和统计都更复杂；JSONB 索引也有写放大，不能无条件给所有 JSONB 建 GIN。

## 5. 数据库维护哪些不变量

| 不变量 | 适合的数据库约束 | 应用还要做什么 |
| --- | --- | --- |
| 手机号不重复 | UNIQUE(phone_number) | 格式校验、冲突错误转换 |
| 同一工作区成员不重复 | 复合 UNIQUE | 邀请和角色业务规则 |
| Chunk 不脱离资产 | 外键、级联删除 | 同步删除向量与缓存 |
| 文件大小非负 | CHECK | 上传边界与计数补偿 |
| 进度范围合法 | CHECK 0—100 | 进度单调/阶段语义 |
| 同来源行动不重复 | 部分 UNIQUE | 幂等返回和版本检查 |
| 审查对应具体报告 | 外键 + snapshot/version 字段 | 签署前重新核对快照 |

注意：同时存在 workspace_id 和 project_id 不会自动保证二者互相匹配。各自外键只能证明两个 ID 分别存在；二者的归属一致性需要查询约束、复合外键或其他明确机制。租户安全也不会因建了外键而自动成立。

## 6. 索引逐项理解

### 6.1 B-tree 复合索引

例如 projects(workspace_id,status,updated_at DESC)：在指定工作区与状态时，可以缩小范围并按更新时间读取。是否能直接满足排序取决于过滤条件、排序列和扫描方式，不能简单说「最左匹配所以任何后缀查询都快」。

agent_run_events(run_id,id) 贴合「某 Run 中 id 大于游标，按 id 返回」；workspace_members(user_id,workspace_id) 支持某用户的工作区关联；统计索引支持项目与时间范围。

### 6.2 GIN 与全文检索

asset_chunks 的 search_vector 是生成列，GIN 可支持词项匹配。生产关键词 SQL 将租户候选物化后计算 ts_rank_cd 与中文子串分数，并非所有执行计划都直接走 GIN。

重要追问：建了 GIN 为什么还慢？因为查询可能没有可用的 @@ 条件、CTE 物化改变优化空间、中文分词不理想，或候选集合过大。要看真实执行计划，不能把「索引存在」等同于「索引被用」。

### 6.3 部分索引

notifications 的 WHERE read_at IS NULL 只包含未读数据，减少索引大小；行动项来源唯一索引仅在来源字段非空时生效。查询条件必须能让优化器证明符合部分条件，才有机会使用它。

### 6.4 冗余索引

V15 删除手机号重复唯一索引、与(asset_id,chunk_index)唯一约束重复的普通索引，并调整配置列表索引。每增加一份索引都增加写入、WAL、磁盘和维护成本；索引不是越多越好。

PostgreSQL 外键不会自动为所有引用端列创建索引。被引用主键已有索引，但对子表按外键查找及删除检查的代价仍需评估。

## 7. SQL：能写、能解释、能看执行计划

以下均为学习示例，不代表本次已执行。

### 7.1 带租户范围与游标的事件回放

~~~sql
SELECT e.id, e.event_type, e.payload
FROM agent_run_events e
JOIN agent_runs r ON r.id = e.run_id
JOIN agent_threads t ON t.id = r.thread_id
WHERE t.workspace_id = :workspace_id
  AND t.project_id = :project_id
  AND t.created_by = :user_id
  AND r.run_key = :run_key
  AND e.id > :after_id
ORDER BY e.id
LIMIT :page_size;
~~~

解释：权限条件跟资源关联一起执行；分页按稳定递增 ID。实际 Mapper 的权限可能允许更广角色范围，不能直接用这份示例替换而改变业务。

### 7.2 Seek 分页替代深 OFFSET

~~~sql
SELECT id, title, status, created_at
FROM research_runs
WHERE project_id = :project_id
  AND (created_at, id) < (:last_created_at, :last_id)
ORDER BY created_at DESC, id DESC
LIMIT :page_size;
~~~

重复时间戳用 id 打破平局。若高频修改 updated_at，翻页期间记录可能移动，需按业务选择稳定排序或快照。Seek 不适合任意跳到第 500 页的需求，不能只讲优点。

### 7.3 未读计数与 N+1

可按 workspace_id 对用户的未读通知聚合，而不是每个工作区再发一个计数查询。JOIN 多个一对多关系时计数可能被乘法放大，应先分组再 JOIN 或明确 COUNT DISTINCT 的代价。

### 7.4 执行计划步骤

1. 先记录真实 SQL、参数分布、数据量和耗时。
2. 用 EXPLAIN 看预估计划；必要时在可控环境执行 EXPLAIN (ANALYZE,BUFFERS)。ANALYZE 会真的运行语句。
3. 对比 estimated rows 与 actual rows，看统计信息是否偏差。
4. 看 Seq Scan/Index Scan/Bitmap、JOIN 方法、loops、排序是否落盘、shared hit/read。
5. 修改索引或 SQL 后用同一数据分布对比，而非只看空库速度。

## 8. MVCC 与隔离级别

MVCC 让事务按可见性规则读取行版本，减少读写直接互相阻塞；不代表所有读都无锁，也不代表写写不会冲突。

PostgreSQL 默认 Read Committed，每条语句读取开始时可见的已提交快照；同一事务两次查询可能看到不同结果。Repeatable Read 使用更稳定的事务快照，PostgreSQL 实现还避免幻读，但仍可能出现序列化异常；Serializable 提供更强隔离并可能要求失败后重试。Read Uncommitted 在 PostgreSQL 中按 Read Committed 处理。参见 [PostgreSQL 16 隔离说明](https://www.postgresql.org/docs/16/transaction-iso.html)。

应用例子：读到「剩余额度足够」后再更新不是自动安全。两个 Read Committed 事务都可能读到同一旧额度，因此使用 FOR UPDATE 或原子条件 UPDATE 维护额度不变量。

## 9. 锁、死锁、丢失更新

### 9.1 行锁与条件更新

悲观方案：在短事务中锁用户配额行，核对并更新。乐观方案：UPDATE ... SET used_bytes=used_bytes+:size WHERE used_bytes+:size<=:quota，通过受影响行数判断是否成功。选择要看配额规则、初始化和异常补偿。

状态机可采用 WHERE status=:expected_status 的条件更新防止旧请求覆盖新终态。读后无条件覆盖整个实体会形成丢失更新，尤其多个用户同时编辑不同字段时。

### 9.2 死锁

事务 A 先锁项目再锁用户，B 先锁用户再锁项目，可能互相等待。统一资源加锁顺序、缩短事务、设置合理超时，并对数据库明确可重试错误做有界重试。重试前要确认外部副作用不会重复。

### 9.3 连接池耗尽

Java 最大 20、AI 最大 10 是默认单实例池上限；两个服务共用数据库。应加总所有副本、维护连接和管理员保留连接。连接池满时请求等待并不是数据库 CPU 一定满，也可能是长事务、慢外部调用或泄漏。

## 10. Flyway 与结构演进

V1—V35 体现多轮演进：业务底座 → 对话 → 索引优化 → Embedding 元数据与 Milvus 拆分 → 凭据范围 → 规划审查 → Token → 工作区模型配置 → 配额 → 评估 → 签署 → 行动交付。

Flyway 记录已执行版本与校验信息。已在共享环境执行的迁移不应随意改写；新变化通常追加迁移。校验失败不应直接 repair 掩盖原因，先确认是文件变化、环境漂移还是错误操作。

V29 迁移时复制旧配置、为每工作区选默认、调整序列，再保留旧表归档，是可讲的数据迁移案例。后续要检查：数据是否完整、默认模型是否符合权限、旧服务与新结构是否兼容、失败能否恢复。

上线扩展可用 expand/contract：先增加兼容字段，双读/回填验证，再切新逻辑，最后删除旧结构。一次删除旧列可能让旧镜像无法回滚。

## 11. WAL、VACUUM 与备份

WAL 先记录变更，支持崩溃恢复，也可用于复制和时间点恢复。主从复制是可扩展方案，当前 Compose 只有单 PostgreSQL，不是高可用集群。

MVCC 产生旧行版本，需要 VACUUM 处理可回收空间并维护可见性信息；长事务会阻碍清理，频繁更新大文本或 JSONB 可能造成膨胀。看磁盘增长时也要区分表、索引、WAL 和日志。

备份不能只说「用了 Docker volume」：

- volume 让容器重建后数据仍在，不能抵御误删、损坏和磁盘丢失。
- pg_dump 适合逻辑备份；物理备份和 WAL 归档适合更明确的恢复目标。
- 备份需要同时考虑业务文件、加密密钥、配置和向量模型版本。
- 恢复成功的证据是导入后能登录、访问权限正确、原文件可读、Chunk 可检索、报告引用能解释。
- RPO 是可接受丢失的数据时间，RTO 是恢复服务的目标时间，二者应由业务要求决定。

## 12. 数据一致性专题

| 故障窗口 | 可能结果 | 当前思路/后续方案 |
| --- | --- | --- |
| 文件写入成功，资产插入失败 | 孤儿对象 | 补偿删除，定期对象对账 |
| 资产提交后，派发前崩溃 | INDEXING 长期不动 | afterCommit 解决可见性；Outbox/扫描重派解决投递 |
| Chunk 提交后，Milvus 插入失败 | 有正文无向量 | 失败状态、可重建索引、重试；版本化切换可减少空窗 |
| 删除资产但向量没删 | 残留向量 | 回 PostgreSQL 校验过滤；后台清理和对账 |
| 缓存未失效 | 搜索返回旧内容 | 项目级版本 bump + TTL；权限变化也要纳入 |
| 报告改了但签署仍保留 | 旧结论误用于新版本 | snapshot_hash 与版本检查，要求重新审查 |

## 13. 面试练习

能够现场解释四个索引：事件回放复合索引、Chunk 全文 GIN、通知未读部分索引、行动项来源部分唯一索引。能够用两个并发事务画出配额超额和行锁修复；能够说明为什么默认隔离级别不能代替业务约束；能够讲出 V29 的迁移过程及回滚限制。

## 14. 官方补充：覆盖索引、NULL 与在线建索引

### 14.1 INCLUDE 不保证完全不回表

Index Only Scan 除了要求所需列可由索引提供，还要根据 visibility map 判断可见性；页面不满足条件时仍可能 Heap Fetch。INCLUDE 增加索引大小，频繁更新的事件表未必受益。验证时看执行计划中的 Heap Fetches 与 buffers，参见 [PostgreSQL 16 索引仅扫描](https://www.postgresql.org/docs/16/indexes-index-only-scans.html)。

复合 B-tree 的前导等值条件和随后范围条件决定能有效缩小哪些扫描区间；缺前导列不等于任何情况下绝不会用索引，但可能扫描较大范围。不要把更新版本的索引优化能力默认套到 PostgreSQL 16，见 [16 版复合索引](https://www.postgresql.org/docs/16/indexes-multicolumn.html)。

### 14.2 UNIQUE 与 CHECK 的 NULL 语义

PostgreSQL 默认唯一约束允许多个 NULL，NULLS NOT DISTINCT 可表达另一种要求；CHECK 的结果为 NULL 也不视为违反，非空要另用 NOT NULL。外键引用端索引不会自动全建。见 [PostgreSQL 16 约束](https://www.postgresql.org/docs/16/ddl-constraints.html)。

项目联系：行动项来源键只有非空时才参与部分唯一；用户配额非负检查还结合 NOT NULL；同时存在 workspace_id/project_id 两个外键仍不证明它们相互匹配。面试应从业务不变量推导约束，而不是只背数据库默认行为。

### 14.3 CREATE INDEX CONCURRENTLY 不是零代价变更

CONCURRENTLY 减少对常规写入的阻塞，但需要更多阶段和等待，失败可能留下无效索引，而且不能放在事务块中。给 Flyway 追加该语句时，要安排兼容的非事务执行及失败清理流程。依据 [PostgreSQL 16 CREATE INDEX](https://www.postgresql.org/docs/16/sql-createindex.html)。

当前 V11/V13/V15 主要是普通索引迁移；本节属于上线迁移设计补充。不能因为把语句改成 CONCURRENTLY，就声称已验证大表在线升级。

## 15. 从「SQL 慢」进一步定位到锁与事务

行锁主要阻塞其他写入/加锁，不阻止普通 MVCC 读取；SELECT 本身仍会获得表级锁，并可能被冲突的 DDL 阻塞。FOR UPDATE 不是「只有这一条 SELECT 能读取该行」。参见 [PostgreSQL 16 显式锁](https://www.postgresql.org/docs/16/explicit-locking.html)。

只读诊断示意，需有相应查看权限：

~~~sql
SELECT pid, state, wait_event_type, wait_event,
       clock_timestamp() - xact_start AS transaction_age,
       pg_blocking_pids(pid) AS blockers
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
ORDER BY xact_start NULLS LAST;
~~~

再结合连接池等待和具体执行计划区分：没拿到连接、拿到连接后等锁、正在执行扫描、返回大量结果。EXPLAIN 的 cost 是规划器单位，不能直接当毫秒；ANALYZE 的实测还需考虑缓存与执行开销。参考 [PostgreSQL 16 EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html)。

错误处理可按 SQLSTATE 分类：40001 是序列化失败，40P01 是死锁，23505 是唯一冲突。前两类可在确认幂等后有界重试整个事务，唯一冲突通常需要业务协调；连接中断还可能处于提交结果未知状态。代码不要依赖英文错误字符串匹配，见 [PostgreSQL 错误码](https://www.postgresql.org/docs/16/errcodes-appendix.html)。

## 16. PITR 能恢复什么

时间点恢复需要可用基础备份及覆盖目标时段的连续 WAL，不是单独保存若干 WAL 文件即可。它也不会同时恢复 Redis、MinIO 和 Milvus 的业务一致性。依据 [PostgreSQL 16 连续归档/PITR](https://www.postgresql.org/docs/16/continuous-archiving.html)。

项目恢复方案应说明：选择哪个业务时间点 → 恢复数据库 → 对应原文件是否仍存在 → 失配索引是否重建 → 未完成任务是继续、重试还是人工处理。练习中记录这些决策与真实耗时，避免把数据库能启动当成完整恢复。
