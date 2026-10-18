# 全部接口逐项验收

147 行，含 108 个 Java Controller 路由、34 个 AI 路由与 5 个框架入口。每行必须分别记录正常、鉴权、越权/不存在、参数四个子结果，不能只记录接口能返回。

## 1. 调用方式与身份

浏览器业务接口以 http://localhost:5173/api 为根；直接 Java 以 http://localhost:8080 为根；AI 以 http://localhost:8003 为根。预发布替换为实际地址。
业务请求使用真实测试账号登录 Cookie；修改请求由正常前端流程获取 CSRF，再保留对应 token。内部路由仅由隔离 QA 的技术执行者带 X-Internal-Api-Key 调用，不把真实 key 放在报告或命令输出。
取得请求体：有 UI 的接口在 Network 找到该操作的合法请求并复制为已脱敏样本，使用 QA 对象重放；没有 UI 的 AI 接口查 /docs 或 /openapi.json 的 requestBody Schema；没有 UI 的 Java 接口查列出的 Controller 方法、Request DTO/record 与 05-api.md，按实际代码而非旧文档填写。
缺少实体或权限时记录阻塞，不随意伪造生产 ID。必要时将对应编号交给我执行。只对 QA 对象重放写入/删除；涉及真实模型费用的接口限制次数。

## 2. 路径参数与输入准备

| 参数 | 取值来源 |
|---|---|
| workspaceId / 项目 projectId | QA-A/QA-B 与 P1/P2/PP 创建响应或页面 URL |
| assetId / chunkId | 上传成功响应、资产详情与 Chunk 列表 |
| threadId / messageId / agent runId | 合法对话提交响应与线程列表 |
| research runId | 合法研究创建响应，终态/计划以该 ID 查询 |
| reportId / action id / caseId | 本轮真实报告、行动、评估响应 |
| model/tool/member/invitation id | 对应 QA 配置/成员/邀请列表 |
| callId / chainId | 内部工具提交接受响应 |
| storageKey | 测试上传的真实对象，不能指向目录外或生产文件 |

所有整数/字符串 ID 使用接口实际类型，雪花 ID 不随意转浮点造成精度丢失。URL 中工作区、项目与对象 ID 都要做合法、错配、跨权限和不存在的对照。

## 3. 关键请求范例

下列 JSON 仅给结构；替换为 QA ID 和实际模型配置，完整 Schema 以当前源码/OpenAPI 为准。

项目创建：`{"name":"QA 消息队列选型","description":"验收用，可销毁","visibility":"WORKSPACE"}`。
规划保存：`{"objective":"比较消息队列方案","problem":"订单事件异步处理","successMetrics":"验证目标 12000 QPS 和 99.95% SLA","constraints":"预算 26 万元，6 周，3 人","owner":"QAOwner","deadline":null}`。
业务检索：`{"query":"首期预算和周期","topK":5,"retrievalMode":"HYBRID","useReranker":true}`，精确字段按 retrieval.ts/KnowledgeController 取得合法请求。
业务研究：`{"goal":"结合 P1 资料比较方案，区分事实、建议和缺口","allowWebSearch":false,"topK":5,"retrievalMode":"HYBRID"}`。ResearchRunController 从顶层字段收集配置，不能把这些字段放进 config 后假称已生效。
评估：`{"projectId":123,"query":"首期预算是多少","expectedAnswer":"26 万元","expectedAsset":"01-business.md","expectedChunkIds":[],"requiredFacts":["26 万元"],"forbiddenFacts":["已经实测达标"]}`。
计划修改：`{"mode":"APPEND","expectedVersion":1,"steps":[{"id":"qa-step-1","objective":"补充核对试点周期","action":"SEARCH_INTERNAL","query":"试点周期"}]}`。
工具调用：`{"runId":"qa-tools-1","tool":"search_knowledge","inputData":{"workspace_id":123,"project_id":456,"question":"预算","top_k":5},"allowWrites":false,"confirmed":false}`，123/456 替换为合法 QA 整数 ID；该注册工具要求 question，区别于 HTTP 检索接口的 query；其他 inputData 按 GET /internal/tools 返回 Schema 填写。
文档写工具：tool 为 `generate_document_bundle`，inputData 至少 title/markdown/formats/output_dir；仅 QA 允许目录，授权后 `allowWrites=true` 与 `confirmed=true`，格式逐个 markdown/docx/pdf/pptx 验证。
工具链：`{"runId":"qa-chain-1","steps":[{"id":"s1","tool":"search_knowledge","inputData":{},"dependsOn":[]}],"allowWrites":false,"confirmed":false}`，先填合法 Schema，再追加依赖/变量/失败/取消测试。
回调必须由已接受的 QA run 及其合法回调结构生成；重放同一事件和旧进度用于幂等验证，不能伪造任意生产完成数据。

## 4. 每行判定细则

正常项：状态码、业务 code 与响应 Schema 正确；GET 内容真实，写入能回读，文件能打开，SSE 能逐条解析并续传，后台接受能查终态。失败项：未登录、错误 key、非法输入、不存在 ID 与错配权限均无副作用；不因返回 200/空列表而自动判权限隔离通过。
公开认证接口的鉴权子项改为验证码/参数/限流；内部接口改为 key 校验，不能误套浏览器 Cookie。CSRF/CORS 的 OPTIONS 是安全链分支，由 SEC-007/008 验证。
archive/restore、Thread 删除、重载、取消、回调、删除等仅操作新 QA 副本。反复调用不天然都要求同一 HTTP 返回；重要的是业务幂等、无重复费用/产物或状态回退。
生产 /docs /redoc /openapi.json 的可访问范围按部署决策核验，不把开发环境公开当成生产已保护。

## 5. 逐项接口清单

| 编号 | 服务 | 方法 | 路径 | 动作 | 身份 | 源码位置 |
|---|---|---|---|---|---|---|
| API-B-001 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/action-items` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/actionitem/controller/ActionItemController.java:24` |
| API-B-002 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/action-items` | create | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/actionitem/controller/ActionItemController.java:26` |
| API-B-003 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}/action-items/{id}` | update | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/actionitem/controller/ActionItemController.java:38` |
| API-B-004 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/agent/messages` | sendMessage | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:44` |
| API-B-005 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/agent/threads` | threads | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:57` |
| API-B-006 | Java | DELETE | `/workspaces/{workspaceId}/projects/{projectId}/agent/threads/{threadId}` | deleteThread | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:65` |
| API-B-007 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/agent/runs/{runId}/events` | events | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:78` |
| API-B-008 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/agent/runs/{runId}` | runSnapshot | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:91` |
| API-B-009 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/agent/runs/{runId}/cancel` | cancel | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:99` |
| API-B-010 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/agent/attachments` | listAttachments | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:112` |
| API-B-011 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/agent/attachments` | uploadAttachment | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:121` |
| API-B-012 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/agent/attachments/{attachmentId}/content` | attachmentContent | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:134` |
| API-B-013 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/agent/attachments/{attachmentId}/preview` | attachmentPreview | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/agent/controller/AgentController.java:158` |
| API-B-014 | Java | POST | `/internal/ai/runs/{runId}/callback` | callback | X-Internal-Api-Key；限制内部网络 | `apps/backend/src/main/java/com/cuupe/backend/modules/ai/AiCallbackController.java:25` |
| API-B-015 | Java | POST | `/internal/ai/agent-runs/{runKey}/callback` | agentCallback | X-Internal-Api-Key；限制内部网络 | `apps/backend/src/main/java/com/cuupe/backend/modules/ai/AiCallbackController.java:34` |
| API-B-016 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/assets` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/asset/controller/KnowledgeAssetController.java:49` |
| API-B-017 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}` | detail | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/asset/controller/KnowledgeAssetController.java:50` |
| API-B-018 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/assets` | upload | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/asset/controller/KnowledgeAssetController.java:52` |
| API-B-019 | Java | DELETE | `/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}` | remove | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/asset/controller/KnowledgeAssetController.java:113` |
| API-B-020 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}/reindex` | reindex | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/asset/controller/KnowledgeAssetController.java:123` |
| API-B-021 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}/chunks` | chunks | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/asset/controller/KnowledgeAssetController.java:138` |
| API-B-022 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}/content` | content | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/asset/controller/KnowledgeAssetController.java:154` |
| API-B-023 | Java | GET | `/workspaces/{workspaceId}/audit-logs` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/audit/controller/AuditLogController.java:22` |
| API-B-024 | Java | POST | `/auth/login/password` | loginByPassword | 公开入口；仍校验输入与限流 | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:35` |
| API-B-025 | Java | POST | `/auth/login/sms` | loginBySms | 公开入口；仍校验输入与限流 | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:44` |
| API-B-026 | Java | POST | `/auth/sms` | getSms | 公开入口；仍校验输入与限流 | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:57` |
| API-B-027 | Java | POST | `/auth/register` | register | 公开入口；仍校验输入与限流 | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:85` |
| API-B-028 | Java | POST | `/auth/password/reset` | resetPassword | 公开入口；仍校验输入与限流 | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:92` |
| API-B-029 | Java | GET | `/auth/me` | me | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:100` |
| API-B-030 | Java | PATCH | `/auth/me` | updateProfile | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:106` |
| API-B-031 | Java | PATCH | `/auth/me/preferences` | updatePreferences | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:113` |
| API-B-032 | Java | PUT | `/auth/me/password` | updatePassword | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:120` |
| API-B-033 | Java | PUT | `/auth/me/phone` | updatePhone | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/AuthController.java:129` |
| API-B-034 | Java | GET | `/auth/captcha` | captcha | 公开入口；仍校验输入与限流 | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/CaptchaController.java:21` |
| API-B-035 | Java | GET | `/auth/csrf` | csrf | 公开入口；仍校验输入与限流 | `apps/backend/src/main/java/com/cuupe/backend/modules/auth/controller/CsrfController.java:12` |
| API-B-036 | Java | GET | `/workspaces/{workspaceId}/evaluation-cases` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/evaluation/controller/EvaluationCaseController.java:48` |
| API-B-037 | Java | POST | `/workspaces/{workspaceId}/evaluation-cases` | create | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/evaluation/controller/EvaluationCaseController.java:56` |
| API-B-038 | Java | PATCH | `/workspaces/{workspaceId}/evaluation-cases/{caseId}` | update | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/evaluation/controller/EvaluationCaseController.java:85` |
| API-B-039 | Java | POST | `/workspaces/{workspaceId}/evaluation-cases/{caseId}/run` | runRetrievalEvaluation | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/evaluation/controller/EvaluationCaseController.java:120` |
| API-B-040 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/knowledge/search` | search | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/knowledge/controller/KnowledgeController.java:26` |
| API-B-041 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/knowledge/answer` | answer | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/knowledge/controller/KnowledgeController.java:40` |
| API-B-042 | Java | GET | `/workspaces/{workspaceId}/notifications` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/notification/controller/NotificationController.java:19` |
| API-B-043 | Java | PATCH | `/workspaces/{workspaceId}/notifications/{id}/read` | markRead | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/notification/controller/NotificationController.java:27` |
| API-B-044 | Java | PATCH | `/workspaces/{workspaceId}/notifications/read-all` | markAllRead | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/notification/controller/NotificationController.java:37` |
| API-B-045 | Java | GET | `/workspaces/{workspaceId}/projects` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:24` |
| API-B-046 | Java | POST | `/workspaces/{workspaceId}/projects` | create | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:29` |
| API-B-047 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}` | detail | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:37` |
| API-B-048 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}` | update | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:42` |
| API-B-049 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}/chunking` | updateChunking | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:50` |
| API-B-050 | Java | DELETE | `/workspaces/{workspaceId}/projects/{projectId}` | delete | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:57` |
| API-B-051 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}/archive` | archive | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:65` |
| API-B-052 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}/restore` | restore | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectController.java:73` |
| API-B-053 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/planning` | detail | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectPlanController.java:28` |
| API-B-054 | Java | PUT | `/workspaces/{workspaceId}/projects/{projectId}/planning` | save | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectPlanController.java:44` |
| API-B-055 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/review/policy` | policy | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectReviewController.java:28` |
| API-B-056 | Java | PUT | `/workspaces/{workspaceId}/projects/{projectId}/review/policy` | savePolicy | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectReviewController.java:37` |
| API-B-057 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/review/latest` | latest | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectReviewController.java:59` |
| API-B-058 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/review/runs` | run | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/project/controller/ProjectReviewController.java:67` |
| API-B-059 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/reports` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/report/controller/ReportController.java:27` |
| API-B-060 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/reports/{reportId}` | detail | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/report/controller/ReportController.java:32` |
| API-B-061 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}/reports/{reportId}` | update | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/report/controller/ReportController.java:37` |
| API-B-062 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/reports/{reportId}/export` | export | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/report/controller/ReportController.java:62` |
| API-B-063 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/runs` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/research/controller/ResearchRunController.java:42` |
| API-B-064 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/runs` | create | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/research/controller/ResearchRunController.java:47` |
| API-B-065 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}` | detail | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/research/controller/ResearchRunController.java:81` |
| API-B-066 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/cancel` | cancel | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/research/controller/ResearchRunController.java:99` |
| API-B-067 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/retry` | retry | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/research/controller/ResearchRunController.java:113` |
| API-B-068 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/plan` | updatePlan | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/research/controller/ResearchRunController.java:127` |
| API-B-069 | Java | GET | `/workspaces/{workspaceId}/security-harness/cases` | cases | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/security/controller/SecurityHarnessController.java:48` |
| API-B-070 | Java | POST | `/workspaces/{workspaceId}/security-harness/runs` | start | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/security/controller/SecurityHarnessController.java:54` |
| API-B-071 | Java | GET | `/workspaces/{workspaceId}/security-harness/runs` | runs | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/security/controller/SecurityHarnessController.java:73` |
| API-B-072 | Java | GET | `/workspaces/{workspaceId}/security-harness/runs/{runId}` | detail | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/security/controller/SecurityHarnessController.java:79` |
| API-B-073 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/settings/models` | models | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/ProjectSettingsController.java:38` |
| API-B-074 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/settings/tools` | tools | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/ProjectSettingsController.java:45` |
| API-B-075 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/settings/local-tools` | localTools | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/ProjectSettingsController.java:50` |
| API-B-076 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/settings/local-tools/reload` | reloadLocalTools | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/ProjectSettingsController.java:62` |
| API-B-077 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/settings/tools` | createTool | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/ProjectSettingsController.java:74` |
| API-B-078 | Java | PATCH | `/workspaces/{workspaceId}/projects/{projectId}/settings/tools/{id}` | updateTool | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/ProjectSettingsController.java:98` |
| API-B-079 | Java | DELETE | `/workspaces/{workspaceId}/projects/{projectId}/settings/tools/{id}` | deleteTool | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/ProjectSettingsController.java:121` |
| API-B-080 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/settings/web-search` | get | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WebSearchSettingsController.java:34` |
| API-B-081 | Java | PUT | `/workspaces/{workspaceId}/projects/{projectId}/settings/web-search` | save | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WebSearchSettingsController.java:42` |
| API-B-082 | Java | POST | `/workspaces/{workspaceId}/projects/{projectId}/settings/web-search/test` | test | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WebSearchSettingsController.java:85` |
| API-B-083 | Java | GET | `/workspaces/{workspaceId}/settings/models` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:39` |
| API-B-084 | Java | POST | `/workspaces/{workspaceId}/settings/models` | create | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:46` |
| API-B-085 | Java | PATCH | `/workspaces/{workspaceId}/settings/models/{id}` | update | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:70` |
| API-B-086 | Java | DELETE | `/workspaces/{workspaceId}/settings/models/{id}` | delete | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:94` |
| API-B-087 | Java | PUT | `/workspaces/{workspaceId}/settings/models/default` | setDefault | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:103` |
| API-B-088 | Java | POST | `/workspaces/{workspaceId}/settings/models/{id}/test` | test | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:123` |
| API-B-089 | Java | POST | `/workspaces/{workspaceId}/settings/models/{id}/context` | context | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:141` |
| API-B-090 | Java | POST | `/workspaces/{workspaceId}/settings/models/{id}/test-embedding` | testEmbedding | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/settings/controller/WorkspaceModelSettingsController.java:159` |
| API-B-091 | Java | GET | `/workspaces/{workspaceId}/statistics` | workspace | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/statistics/controller/StatisticsController.java:27` |
| API-B-092 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/statistics` | project | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/statistics/controller/StatisticsController.java:36` |
| API-B-093 | Java | GET | `/workspaces/{workspaceId}/projects/{projectId}/storage/quota` | quota | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/storage/controller/StorageQuotaController.java:24` |
| API-B-094 | Java | GET | `/workspaces/my` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:4` |
| API-B-095 | Java | POST | `/workspaces` | create | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:5` |
| API-B-096 | Java | GET | `/workspaces/{id}` | detail | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:6` |
| API-B-097 | Java | PATCH | `/workspaces/{id}` | update | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:7` |
| API-B-098 | Java | DELETE | `/workspaces/{id}` | delete | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:8` |
| API-B-099 | Java | PATCH | `/workspaces/{id}/archive` | archive | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:9` |
| API-B-100 | Java | PATCH | `/workspaces/{id}/restore` | restore | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:10` |
| API-B-101 | Java | PATCH | `/workspaces/{id}/preferences` | preferences | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceController.java:11` |
| API-B-102 | Java | POST | `/workspaces/{workspaceId}/invitations` | create | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceInvitationController.java:28` |
| API-B-103 | Java | GET | `/workspace-invitations/me` | mine | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceInvitationController.java:42` |
| API-B-104 | Java | POST | `/workspace-invitations/{id}/accept` | accept | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceInvitationController.java:47` |
| API-B-105 | Java | POST | `/workspace-invitations/{id}/decline` | decline | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceInvitationController.java:57` |
| API-B-106 | Java | DELETE | `/workspaces/{workspaceId}/invitations/{invitationId}` | revoke | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceInvitationController.java:64` |
| API-B-107 | Java | GET | `/workspaces/{workspaceId}/members` | list | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceMemberController.java:3` |
| API-B-108 | Java | PATCH | `/workspaces/{workspaceId}/members/{memberId}` | role | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/modules/workspace/controller/WorkspaceMemberController.java:3` |
| API-A-001 | AI | POST | `/internal/knowledge/search` | search_knowledge | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/knowledge.py:57` |
| API-A-002 | AI | POST | `/internal/knowledge/answer` | answer_knowledge | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/knowledge.py:116` |
| API-A-003 | AI | POST | `/internal/indexing/assets/{asset_id}` | index_asset | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/knowledge.py:179` |
| API-A-004 | AI | POST | `/internal/knowledge/graph/search` | search_graph | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/knowledge.py:224` |
| API-A-005 | AI | POST | `/internal/research/runs/{run_id}/execute` | execute_run | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/research.py:16` |
| API-A-006 | AI | POST | `/internal/research/runs/{run_id}/cancel` | cancel_run | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/research.py:48` |
| API-A-007 | AI | GET | `/internal/research/runs/{run_id}` | get_run | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/research.py:55` |
| API-A-008 | AI | PATCH | `/internal/research/runs/{run_id}/plan` | update_plan | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/research.py:114` |
| API-A-009 | AI | GET | `/internal/research/runs/{run_id}/events` | run_events | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/research.py:157` |
| API-A-010 | AI | GET | `/internal/security-harness/cases` | cases | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/security.py:24` |
| API-A-011 | AI | POST | `/internal/security-harness/run` | run | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/security.py:29` |
| API-A-012 | AI | GET | `/health` | health | 公开入口；仍校验输入与限流 | `apps/ai-service/api/routes/system.py:47` |
| API-A-013 | AI | GET | `/internal/health` | internal_health | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:54` |
| API-A-014 | AI | GET | `/internal/runtime/status` | runtime_status | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:63` |
| API-A-015 | AI | POST | `/internal/cache/invalidate` | invalidate_cache | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:74` |
| API-A-016 | AI | GET | `/internal/files/tools` | file_tools | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:87` |
| API-A-017 | AI | POST | `/internal/files/preview` | file_preview | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:110` |
| API-A-018 | AI | GET | `/internal/mcp/tools` | mcp_tools | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:140` |
| API-A-019 | AI | GET | `/internal/agents` | agents | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:149` |
| API-A-020 | AI | POST | `/internal/agents/{agent_name}/messages` | agent_message | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:160` |
| API-A-021 | AI | POST | `/internal/llm/chat` | llm_chat | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:185` |
| API-A-022 | AI | POST | `/internal/llm/test` | test_llm | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:201` |
| API-A-023 | AI | POST | `/internal/llm/context` | llm_context | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:226` |
| API-A-024 | AI | POST | `/internal/embedding/test` | test_embedding | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:240` |
| API-A-025 | AI | POST | `/internal/web-search/test` | test_web_search | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:256` |
| API-A-026 | AI | POST | `/internal/web-source/validate` | validate_external_source | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/system.py:288` |
| API-A-027 | AI | GET | `/internal/tools` | list_tools | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:38` |
| API-A-028 | AI | POST | `/internal/tools/custom/reload` | reload_custom_tools | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:50` |
| API-A-029 | AI | POST | `/internal/tools/calls` | submit_tool_call | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:63` |
| API-A-030 | AI | GET | `/internal/tools/calls/{call_id}` | get_tool_call | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:87` |
| API-A-031 | AI | POST | `/internal/tools/calls/{call_id}/cancel` | cancel_tool_call | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:98` |
| API-A-032 | AI | POST | `/internal/tools/chains` | submit_tool_chain | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:110` |
| API-A-033 | AI | GET | `/internal/tools/chains/{chain_id}` | get_tool_chain | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:144` |
| API-A-034 | AI | POST | `/internal/tools/chains/{chain_id}/cancel` | cancel_tool_chain | X-Internal-Api-Key；限制内部网络 | `apps/ai-service/api/routes/tools.py:155` |
| API-F-001 | Java | POST | `/auth/logout` | Spring Security logout | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/java/com/cuupe/backend/config/security/SecurityConfig.java:193` |
| API-F-002 | Java | GET | `/actuator/health` | Actuator health | Cookie 会话；写入需要有效 CSRF | `apps/backend/src/main/resources/application.yml:1` |
| API-F-003 | AI | GET | `/docs` | Swagger UI | 公开入口；仍校验输入与限流 | `apps/ai-service/api/application.py:58` |
| API-F-004 | AI | GET | `/redoc` | ReDoc | 公开入口；仍校验输入与限流 | `apps/ai-service/api/application.py:58` |
| API-F-005 | AI | GET | `/openapi.json` | OpenAPI schema | 公开入口；仍校验输入与限流 | `apps/ai-service/api/application.py:58` |
