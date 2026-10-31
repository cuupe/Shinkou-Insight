# 02. Java 业务后端、认证、事务与并发

源码入口：apps/backend/pom.xml、src/main/resources/application.yml，以及 src/main/java/com/cuupe/backend 下的 config、common、modules、utils。当前声明 Java 21、Spring Boot 4.1.0、MyBatis starter 4.1.0。

## 1. 为什么拆成 Java 控制面与 Python 执行面

Java 维护用户、工作区、权限、项目、业务状态、报告、审查、配额和审计。Python 面向模型生态、文档转换、检索、Agent 和工具。拆分的收益是职责和依赖更清楚；代价是网络失败、协议兼容、状态同步和跨存储一致性。

面试不能停留在「Java 稳定、Python 生态好」。要补充：前端只访问 Java，用户身份由 Java 解析；Python 请求的 workspaceId、projectId、userId 和运行配置由可信业务链路组装，模型不能决定租户或凭据；AI 故障时历史业务数据应仍有独立读取路径。

## 2. Spring 应用如何启动

### 2.1 从 main 到可处理 HTTP

1. SpringApplication 创建应用上下文，读取环境变量与 application.yml。
2. 组件扫描发现 Controller、Service、Mapper 配置和安全 Bean。
3. 自动配置按 classpath、属性和条件创建 WebMVC、数据源、Redis、Flyway 等对象。
4. Hikari 初始化连接池，Flyway 按迁移顺序更新数据库。
5. SecurityFilterChain、DispatcherServlet 与路由映射准备好。
6. 应用对外监听 8080；Actuator /health 可响应。

自动配置不是「引依赖就必定启用全部功能」，还取决于条件、属性和自定义 Bean。Redis starter 的存在不会自动把 HttpSession 转成 Redis Session。

### 2.2 IoC / DI / Bean 生命周期

IoC 是对象构建和装配由容器管理；DI 是把依赖注入到对象中。项目常见 final 字段配合 RequiredArgsConstructor，本质是构造器注入：依赖显式、便于测试、对象创建后依赖稳定。

单例 Bean 是容器范围复用的实例，不等于线程安全。Service 中如果保存「当前用户」或可变请求对象字段，就可能让并发请求相互覆盖。当前用户上下文应随方法参数或正确管理的安全上下文流转。

Bean 可以经历构造、依赖注入、初始化回调、代理包装、销毁回调。SecurityConfig 的 PostConstruct 会验证生产配置，说明「启动即校验不变量」比收到第一笔请求才发现默认密码更早暴露问题。

## 3. 一次业务 API 请求的完整路径

~~~text
浏览器 /api/workspaces/W/projects/P/...
→ Nginx 去掉 /api
→ Servlet Filter / Spring Security
→ DispatcherServlet
→ Controller：路径、请求体、身份、参数校验
→ Service：业务规则、事务和外部调用安排
→ Mapper：参数化 SQL
→ Hikari Connection → PostgreSQL
→ DTO / Result → JSON
→ 前端 unwrap / 渲染
~~~

Filter 位于 Servlet 链，适合认证、安全头和请求级处理；Interceptor 位于 MVC 层，适合控制器前后扩展；AOP 拦截符合切点的 Bean 方法，常用于事务。三者不能混称为同一种拦截器。

## 4. 分层、DTO 与错误契约

### 4.1 分层解决什么

- Controller 定义 HTTP 语义，不宜承载大量跨表状态机。
- Service 维护可复用的业务不变量和事务边界。
- Mapper 负责数据访问，查询要包含可验证的权限范围。
- DTO 表达输入和输出，避免把数据库字段全部暴露。
- Entity 反映持久化结构，不能直接决定用户能修改什么。

当前部分模块的 Controller 仍承担业务编排；可以诚实指出这是可继续重构的地方，不要把实际结构描述成完美分层架构。

### 4.2 参数与状态校验

Bean Validation 适合长度、非空、格式等局部规则；「项目属于该工作区」「操作者有写权限」「报告版本未变化」「行动项只能从待验收转为已完成」必须访问业务上下文。

请求中的 createdBy、workspaceId、role、storageKey、model endpoint 都不能按表单原样信任。要区分可以由用户选择的业务参数和必须由服务端派生的安全上下文。

### 4.3 统一错误

Result 提供 code/message/data；ApiException 和 GlobalExceptionHandler 组织业务异常。HTTP 状态应保持含义：400 参数错误，401 未认证，403 无权限，404 资源不存在或有意隐藏，409 冲突，429 限流，502/504 上游失败或超时。

不能为了「前端统一处理」把所有错误变成 200；也不能把内部堆栈、SQL、密钥或模型响应原文直接给用户。

## 5. 认证：当前实际是 HttpSession

### 5.1 密码登录链路

1. 接收手机号/密码、验证码等输入并校验。
2. AuthRateLimiter 检查 IP 与账号维度请求/失败频率。
3. 当前 AuthServiceImpl 直接查询登录用户，用 PasswordEncoder.matches 校验密码，并检查账号状态；不存在的账号也使用占位哈希执行比较。
4. 创建 Authentication 与 SecurityContext。
5. 通过 HttpSessionSecurityContextRepository 保存到会话。
6. 浏览器持有 HttpOnly 的 JSESSIONID，后续请求由服务端还原身份。
7. SessionSecurityService 维护活跃会话上限及其他会话过期。

AuthServiceImpl 对不存在账号仍做 BCrypt 比较，目的在于减小明显的时间差；这并不等于完全消除所有账号枚举信道。

SecurityConfig 虽然配置了 AuthenticationManager 和 DaoAuthenticationProvider，但当前手工密码登录路径不经它们完成校验；校验后由 authenticateAndPersist 创建已认证 Token、changeSessionId 并保存上下文。面试要区分「配置的通用认证组件」与「实际被调用的路径」。

### 5.2 BCrypt、加密和哈希区别

密码使用带盐、自适应成本的哈希验证，系统通常无需恢复原密码。模型 API Key 必须在调用时恢复，因此用 SecretCipher 的 AES/GCM/NoPadding 加密；Base64 只是编码，不能代替任何一种保护。

BCrypt 成本越高，攻击者猜测越贵，同时登录 CPU 代价也越高；应结合限流和真实硬件评估。AES-GCM 需要正确的随机 IV 与认证标签，主密钥必须稳定保管，轮换要设计旧密文迁移，而不是直接换环境变量。

### 5.3 会话固定、退出和多设备

配置启用 sessionFixation.migrateSession，手工登录路径还显式执行 changeSessionId 轮换会话 ID。退出会清认证、使会话失效并删除相关 Cookie；修改密码可使其他会话失效。

SessionRegistryImpl 是进程内注册表。多实例部署需要同时解决：会话内容共享、会话注册/过期协调、实例故障和负载均衡路由。仅增加 Redis 连接配置不够。

扩展方案可以选择 Spring Session Redis，并验证序列化、TTL、并发会话控制、登出传播和兼容升级；粘性会话只把用户尽量路由回同实例，不能替代共享会话的故障恢复能力。

### 5.4 JWT 是可比较方案

JWT 可以在服务间传递签名声明，减少逐请求读取会话的需求，但撤销、踢设备、密钥轮换、刷新 token 和权限变更依然需要设计。当前项目选择会话更便于退出和主动控制，不能把未使用的 JWT 写成已实现。

## 6. CSRF、CORS 与内部回调

SecurityConfig 为 SPA 配置 CookieCsrfTokenRepository，允许前端读 XSRF Cookie 并通过 Header 提交。CORS 允许明确 Origin、允许凭据、限定方法和 Header。

三者边界：身份认证决定「谁在请求」，授权决定「能操作什么」，CSRF 判断「这个浏览器写请求是否由允许的页面上下文发起」。CORS 是浏览器访问控制机制，不能拦住任意脚本或 curl。

/internal/ai/** 在用户会话认证和 CSRF 上有例外，因为调用方是 Python；AiCallbackController 会独立验证 X-Internal-Api-Key。permitAll 只表示不过这一层用户认证，不能把该内部路由描述为无认证。

Java 使用 MessageDigest.isEqual，Python 使用 secrets.compare_digest 比较内部密钥。静态 Key 是服务身份凭据，不是每个用户的权限证明；仍需校验 runKey、projectId、userId 与持久化运行的归属。

## 7. 多租户授权：要校验完整关系

核心关系是 user → workspace_members → workspace → project → resource。仅检查「user 在某工作区」不足以证明路径中的 projectId 真的属于该工作区。

项目 Mapper 提供可访问项目和写权限查询；资产、报告、Run、附件等读取要绑定 projectId，必要时再绑定 createdBy。前端隐藏按钮只能配合体验，不能充当授权。

面试可按四层讲：

1. API 层取得服务端身份，并限制工作区、项目和资源关联。
2. SQL 使用 JOIN/EXISTS 或范围条件约束资源。
3. Python 继续携带租户上下文，Milvus 过滤并回 PostgreSQL 二次校验。
4. 缓存、对象存储、图谱和工具调用也带租户范围。

角色级别只是策略的一部分。项目可见性、作者/成员范围、写权限、报告签署与行动验收可能不同，必须以具体 Mapper 和 Service 分支为准，不能凭角色名猜能力。

## 8. Spring 事务必须讲清的细节

### 8.1 @Transactional 的有效边界

常见实现通过代理在方法进入时取得连接并开启事务，正常完成时提交，符合回滚规则的异常发生时回滚。默认对 RuntimeException 和 Error 回滚，受检异常需要按业务指定 rollbackFor。

同类内部通过 this 调用带事务的方法可能绕开代理；private、final 等场景要结合代理类型判断，不能看到注解就认定有效。事务上下文通常与执行线程绑定，手工新线程不会自动继承父线程事务。

### 8.2 不要在长事务里等待模型

模型调用可能持续数十秒甚至更久。事务内等待会长期占用数据库连接，可能持有锁并放大故障。比较合理的边界是先短事务写入 QUEUED/INDEXING 状态，再派发异步执行，最后用短事务保存结果和终态。

### 8.3 本项目的 afterCommit 案例

AssetIndexingService.schedule 使用 TransactionSynchronization.afterCommit，再 Thread.startVirtualThread 调用 Python 索引。原因是 Python 用独立数据库连接，如果 Java 资产行尚未提交，Python 可能看不到父记录，插入 Chunk 会失败。

这是比「我用了事务」更值得讲的工程细节：保证异步消费者看到已提交事实，同时不让外部调用占住业务事务。

但 afterCommit 不能保证可靠投递：数据库提交后、线程真正派发前进程可能退出。若业务要求提交后一定被处理，可在同一事务插入 Outbox 记录，由独立派发器重试发送，消费者按业务 ID 幂等。当前仓库不能声称已完整实现 Outbox。

### 8.4 事务不能跨 PostgreSQL、MinIO、Milvus

Java @Transactional 只能覆盖参与其事务管理器的数据库操作。上传文件成功后数据库插入失败，必须补偿删除对象；补偿也可能失败，需要定期对账。代码中附件插入失败会尝试移除对象，这是局部补偿，不是分布式原子事务。

## 9. MyBatis 与数据库访问

MyBatis 把方法与 SQL 映射，当前既有 XML Mapper 也有注解 SQL。#{} 使用参数绑定；动态结构如表名、排序字段不能直接接受用户字符串拼接，应使用固定白名单。

不要把「用了 ORM」当作 SQL 性能保证。面试应能指出过滤列、JOIN 路径、排序、LIMIT、索引和返回字段。每条资源查询还要检查租户条件是否存在。

事务与连接池关系：请求从池中借连接，事务期间通常持续持有，结束后归还。最大池 20 是 Java 本实例上限，AI 服务还有独立的 PostgreSQL 连接池；所有副本的上限需要相加后与数据库连接预算比较。

常见问题：N+1 查询、列表查全部 TEXT/JSONB、无界分页、统计全表扫描、错误使用动态 SQL、连接泄漏和长事务。连接池扩大不能修复低效查询，还可能把压力推给数据库。

## 10. 并发控制的实际例子

### 10.1 存储配额的行锁

StorageQuotaMapper 使用 INSERT ... ON CONFLICT DO NOTHING 初始化用户统计行，再 SELECT used_bytes ... FOR UPDATE。Service 在事务内核对配额并更新计数，以避免两份并发上传都看到「剩余足够」而超额。

锁必须覆盖「读取当前量 → 判定 → 更新」；锁了行却在事务外做更新没有同样保证。文件对象与计数仍跨系统，需要异常补偿和周期性实际大小对账。

### 10.2 行动项导入幂等

V35 建立 source_report_id/source_key 非空时的部分唯一索引，数据库可阻止同一报告来源被重复导入。Service 预查询只改善体验，唯一索引才处理两个并发请求都认为不存在的竞态。

状态迁移还需检查操作者、当前状态、来源报告版本和完成证据。若扩展多实例并发编辑，可采用带原状态或 version 的条件 UPDATE；必须明确是方案，不能把所有实体都说成已经有乐观锁。

### 10.3 JVM 锁不是分布式锁

synchronized、ConcurrentHashMap、CopyOnWriteArrayList 和按 runKey 的进程内互斥只能协调一个 JVM。扩成两个 backend 后，同一 Run 的事件和取消可能命中不同实例，需要共享状态、数据库条件更新及跨实例消息机制。

## 11. Java 21 虚拟线程

项目多处使用 Thread.startVirtualThread 来派发索引、运行或取消请求。虚拟线程由 JVM 调度到少量载体线程，适合大量等待网络/数据库的任务。

必须说清：

- 它提高的是阻塞等待场景的并发组织能力，不让 CPU 密集模型推理或压缩自动更快。
- 数据库连接池、HTTP 连接、外部 API 配额仍是硬限制，虚拟线程不能代替限流。
- ThreadLocal、安全上下文、事务和日志上下文需要检查传播，手工创建线程不能假设继承全部请求状态。
- 针对 Java 21 的同步阻塞与 native 调用场景，要关注载体线程被长时间占用的可能，通过 JFR/线程转储验证，避免套用其他 JDK 版本结论。
- 任务需要生命周期管理、异常捕获和关机策略；「创建线程后不管」不等于可靠后台作业系统。

## 12. 雪花 ID 与序列

SnowflakeIdGenerator 采用 41 位时间、10 位 worker、12 位序列，单 JVM synchronized 保证该生成器的并发互斥。当前 worker ID 随机分配，只降低不同进程相同 worker 的概率，不能严格保证多实例唯一。

时钟回拨时复用上次时间戳，序列耗尽等待下个毫秒；大回拨可能导致等待和吞吐异常。多节点应明确 worker 分配策略、时间同步、重启行为；也可选择数据库序列、UUID 或有序 ID 方案。

数据库表使用 BIGSERIAL 并不阻止应用显式插入雪花 ID。混用时要关注序列是否落后、迁移回填是否调整 setval、主键数量与前端精度。ID 应视为标识而非精确创建时间。

## 13. Java / JVM 基础与项目性能

### 13.1 集合

HashMap 适合无并发共享的映射；ConcurrentHashMap 支持并发操作但不能把多个操作自动组成事务；CopyOnWriteArrayList 读多写少时适合订阅者遍历，频繁写入会复制数组。AgentService 的订阅集合应结合 SSE 的读写比例理解。

### 13.2 内存与 GC

堆保存对象，线程栈保存调用帧，元空间保存类元数据；直接缓冲和 native 库还可能使用堆外内存。容器内存不是只有 Java -Xmx，需为线程、metaspace、直接内存和系统库留空间。

长时间运行的事件历史、未关闭的 SseEmitter、缓存集合和大文件 byte[] 都可能增加内存。排查需先看存活对象和保留链，再判断泄漏；GC 次数高不自动等于泄漏。

### 13.3 超时体系

前端普通请求 10 秒、Hikari 等待 30 秒、AI 索引默认 600 秒、Nginx SSE 3600 秒各自约束不同阶段。要把短请求与长任务分离：短请求返回接受状态，随后读运行进度。不能单纯把所有 timeout 调大来掩盖阻塞。

### 13.4 日志与可观测性

日志应可关联 requestId、workspaceId、projectId、runId、工具和阶段，并隐藏密钥。指标需要连接池等待、HTTP 超时、业务失败、队列积压、SSE 连接数和外部模型延迟。当前 Actuator 依赖和 health 接口存在，不代表 Prometheus/Grafana/完整分布式 Trace 已部署。

## 14. 本章面试追问

1. 为什么在 afterCommit 才调用 Python？答：避免独立连接看不到未提交资产；仍有派发丢失窗口。
2. 为什么不是一个大事务？答：外部模型和对象/向量存储不参与本地事务，长事务还占连接和锁。
3. Redis 已部署，为何后端不能直接横向扩容？答：会话注册、Session 内容、SSE 订阅和进程锁仍有本地状态。
4. 虚拟线程能支撑多少并发？答：要依据模型限额、连接池、CPU/内存和排队时间实测，不能只给线程数量。
5. 哪个约束防止重复行动项？答：V35 的报告来源部分唯一索引，应用层配合冲突处理。
6. 为什么 API Key 要加密，密码却哈希？答：前者调用时需恢复，后者只需验证。
7. 生产启动为什么主动失败？答：提前拒绝默认密钥、非 Secure Cookie 和不合理 Origin，避免带错误安全配置上线。

## 15. 官方事务补充：逻辑事务、物理事务与连接预算

REQUIRED 的内外调用通常共享物理事务，内层标记 rollback-only 后，外层即使吞掉异常也可能在提交时收到 UnexpectedRollbackException。REQUIRES_NEW 暂停外层并取得独立连接；所有线程都占着外层连接再等待内层连接时可耗尽连接池。NESTED 的保存点语义也不同。依据 [Spring 事务传播](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html)。

项目应用：StorageQuotaService 的 MANDATORY 明确要求调用者已有事务；这不是「自动创建事务」。配额和资产插入若需要一起回滚，应检查它们是否共享同一有效事务。不要为了让错误处理「肯定保存」就到处加入 REQUIRES_NEW，否则连接开销和提交语义都改变。

afterCommit 被调用时，部分事务资源可能尚未解绑，但原事务已经提交；若在该回调里做需要新提交的数据库操作，应另建合适事务。当前 AssetIndexingService 是从回调启动新虚拟线程，不能把它误认为原事务继续延伸到 Python。见 [TransactionSynchronization.afterCommit](https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/transaction/support/TransactionSynchronization.html#afterCommit%28%29)。

可复现练习：外层插资产，内层失败并标回滚，外层捕获后提交；再改为独立事务观察两份记录与连接占用。实验必须在隔离数据库进行，并说明事务行为来自代理路径、传播设置与异常规则，而不是方法名字。

## 16. 虚拟线程的版本陷阱：本项目是 Java 21

| 版本依据 | 必须说准的结论 | 本项目怎么用 |
| --- | --- | --- |
| Java 21 | synchronized 内发生阻塞等场景可 pin 住 carrier，影响扩展性 | 关注持锁 I/O，结合 JFR，而非盲目替换全部锁 |
| JDK 24 的变更 | JEP 491 改善 synchronized 导致的 pinning | 不能把后续 JDK 结论套到当前 JRE 21 镜像 |

Java 21 的虚拟线程适合大量等待任务，不能让一段 CPU 运算变快；线程局部缓存也会随大量线程放大内存。可用 jdk.VirtualThreadPinned 事件定位，参见 [Java 21 虚拟线程](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html)。后续行为变化参见 [JDK 24 变更说明](https://docs.oracle.com/en/java/javase/24/migrate/significant-changes-jdk-24.html)。

当前手工创建虚拟线程，不代表 Spring MVC 所有请求都已自动切到虚拟线程。还应分别统计入口请求、异步派发、HTTP 连接和数据库连接的等待，防止把线程机制与真正的资源瓶颈混淆。

## 17. 共享会话的官方接入条件与验证范围

Spring Session Redis 需要相应 Session 集成与配置，使 HttpSession 由存储实现管理；仅有 RedisTemplate 不够，见 [Spring Session 与 Boot/Redis](https://docs.spring.io/spring-session/reference/guides/boot-redis.html)。迁移方案至少验证跨实例 /auth/me、退出传播、TTL、并发修改、序列化兼容与 Redis 故障。

手工认证还要显式保存 SecurityContext，并正确处理会话固定与并发会话策略；不能以「配置了某个 Filter」推断所有手工认证路径自动调用策略。当前 authenticateAndPersist 已保存上下文并轮换 ID，SessionSecurityService 另做上限管理。参考 [Spring Security 会话持久化](https://docs.spring.io/spring-security/reference/servlet/authentication/session-management.html)。
