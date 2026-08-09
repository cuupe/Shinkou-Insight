# 05. API 设计

## 1. 通用约定

Base Path：

```text
/api
```

统一响应：

```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {}
}
```

分页：

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 100
}
```

认证：浏览器自动携带 `access_token` HttpOnly Cookie。

## 2. 错误码

```text
AUTH_UNAUTHORIZED
AUTH_TOKEN_INVALID
AUTH_TOKEN_EXPIRED
WORKSPACE_ACCESS_DENIED
PROJECT_NOT_FOUND
ASSET_NOT_FOUND
ASSET_PARSE_FAILED
ASSET_INDEX_FAILED
KNOWLEDGE_SEARCH_FAILED
RESEARCH_RUN_NOT_FOUND
RESEARCH_RUN_ALREADY_FINISHED
RESEARCH_RUN_CANCELLED
AGENT_SERVICE_UNAVAILABLE
AGENT_NODE_FAILED
AGENT_TOOL_CALL_FAILED
MODEL_UNAVAILABLE
MODEL_OUTPUT_INVALID
PROMPT_VERSION_NOT_FOUND
CITATION_INVALID
RATE_LIMITED
VALIDATION_ERROR
INTERNAL_SERVER_ERROR
```

## 3. Auth

```http
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/logout
GET  /api/invitations/{token}
POST /api/auth/activate
```

登录成功通过响应头写 Cookie，响应体不暴露 Token。

## 4. Workspace

```http
GET   /api/workspaces/my
GET   /api/workspaces/{workspaceId}
PATCH /api/workspaces/{workspaceId}
GET   /api/workspaces/{workspaceId}/members
POST  /api/workspaces/{workspaceId}/invitations
PATCH /api/workspaces/{workspaceId}/archive
PATCH /api/workspaces/{workspaceId}/restore
```

## 5. Project

```http
GET    /api/workspaces/{workspaceId}/projects
POST   /api/workspaces/{workspaceId}/projects
GET    /api/workspaces/{workspaceId}/projects/{projectId}
PATCH  /api/workspaces/{workspaceId}/projects/{projectId}
DELETE /api/workspaces/{workspaceId}/projects/{projectId}
PATCH  /api/workspaces/{workspaceId}/projects/{projectId}/archive
PATCH  /api/workspaces/{workspaceId}/projects/{projectId}/restore
```

创建：

```json
{
  "name": "消息队列技术选型",
  "code": "mq-selection",
  "description": "结合内部业务约束完成选型调研"
}
```

## 6. Knowledge Asset

### 6.1 上传

```http
POST /api/workspaces/{workspaceId}/projects/{projectId}/assets
Content-Type: multipart/form-data
```

字段：

```text
file
name（可选）
language（可选）
```

返回：

```json
{
  "id": 101,
  "name": "业务流量说明.pdf",
  "assetType": "PDF",
  "parseStatus": "PENDING",
  "indexStatus": "PENDING"
}
```

### 6.2 管理

```http
GET    /api/workspaces/{workspaceId}/projects/{projectId}/assets
GET    /api/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}
DELETE /api/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}
POST   /api/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}/reindex
GET    /api/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}/chunks
GET    /api/workspaces/{workspaceId}/projects/{projectId}/assets/{assetId}/content
```

## 7. Knowledge Search

### 7.1 检索 Playground

```http
POST /api/workspaces/{workspaceId}/projects/{projectId}/knowledge/search
```

请求：

```json
{
  "query": "订单系统峰值 TPS 是多少？",
  "topK": 8,
  "retrievalMode": "HYBRID",
  "useReranker": true,
  "filters": {
    "assetIds": []
  }
}
```

返回：

```json
{
  "query": "订单系统峰值 TPS 是多少？",
  "rewrittenQueries": [],
  "items": [
    {
      "chunkId": 1001,
      "assetId": 101,
      "assetName": "业务流量说明.pdf",
      "pageNumber": 8,
      "sectionTitle": "峰值流量",
      "content": "促销期间订单服务峰值 TPS 约为 3500。",
      "vectorScore": 0.86,
      "keywordScore": 0.72,
      "fusionScore": 0.81,
      "rerankScore": 0.93
    }
  ]
}
```

### 7.2 普通 RAG 回答

```http
POST /api/workspaces/{workspaceId}/projects/{projectId}/knowledge/answer
```

请求：

```json
{
  "question": "订单系统目前的峰值吞吐量是多少？",
  "topK": 8,
  "answerLanguage": "zh-CN"
}
```

返回：

```json
{
  "answer": "根据内部资料，促销期间订单服务峰值 TPS 约为 3500。[E1]",
  "citations": [
    {
      "evidenceId": "E1",
      "chunkId": 1001,
      "assetName": "业务流量说明.pdf",
      "pageNumber": 8,
      "quote": "促销期间订单服务峰值 TPS 约为 3500。"
    }
  ],
  "insufficientEvidence": false
}
```

## 8. Research Run

### 8.1 创建

```http
POST /api/workspaces/{workspaceId}/projects/{projectId}/runs
```

```json
{
  "goal": "比较 Kafka、RabbitMQ 和 RocketMQ，并给出当前阶段推荐方案",
  "allowWebSearch": true,
  "maxResearchRounds": 3,
  "reportTemplate": "TECH_SELECTION",
  "outputLanguage": "zh-CN"
}
```

返回 `202 Accepted`：

```json
{
  "runId": 3001,
  "runNo": "run_20260805_xxx",
  "status": "PENDING",
  "eventsUrl": "/api/workspaces/1/projects/10/runs/3001/events"
}
```

### 8.2 查询与操作

```http
GET  /api/workspaces/{workspaceId}/projects/{projectId}/runs
GET  /api/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}
POST /api/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/cancel
POST /api/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/retry
GET  /api/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/steps
GET  /api/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/tools
GET  /api/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/evidences
```

## 9. SSE

```http
GET /api/workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/events
Accept: text/event-stream
```

事件格式：

```text
event: node.started
data: {"runId":3001,"stepId":10,"node":"RETRIEVE_INTERNAL","timestamp":"..."}

```

事件类型：

```text
run.started
run.progress
node.started
node.completed
node.failed
tool.started
tool.completed
tool.failed
evidence.added
finding.added
report.generated
run.completed
run.failed
run.cancelled
heartbeat
```

要求：

- 每个事件带 `eventId`，支持前端去重。
- 断线重连可通过 `Last-Event-ID` 补发有限事件，或重新读取数据库状态。
- SSE 不传输完整超长文档，只传摘要和资源 ID。

## 10. Report

```http
GET    /api/workspaces/{workspaceId}/projects/{projectId}/reports
GET    /api/workspaces/{workspaceId}/projects/{projectId}/reports/{reportId}
PATCH  /api/workspaces/{workspaceId}/projects/{projectId}/reports/{reportId}
DELETE /api/workspaces/{workspaceId}/projects/{projectId}/reports/{reportId}
GET    /api/workspaces/{workspaceId}/projects/{projectId}/reports/{reportId}/export?format=markdown
```

## 11. Action Item

```http
GET   /api/workspaces/{workspaceId}/projects/{projectId}/action-items
PATCH /api/workspaces/{workspaceId}/projects/{projectId}/action-items/{id}
POST  /api/workspaces/{workspaceId}/projects/{projectId}/action-items/{id}/accept
POST  /api/workspaces/{workspaceId}/projects/{projectId}/action-items/{id}/reject
```

## 12. 配置与评估

```http
GET/POST/PATCH /api/workspaces/{workspaceId}/settings/models
GET/POST/PATCH /api/workspaces/{workspaceId}/settings/tools
GET/POST/PATCH /api/workspaces/{workspaceId}/settings/prompts
POST           /api/workspaces/{workspaceId}/evaluation-runs
GET            /api/workspaces/{workspaceId}/evaluation-runs/{id}
```

## 13. Java → Python 内部 API

内部请求必须带服务身份和可信租户上下文，不接受浏览器直接访问。

```http
POST /internal/indexing/assets/{assetId}
POST /internal/research/runs/{runId}/execute
POST /internal/research/runs/{runId}/cancel
POST /internal/knowledge/search
GET  /internal/health
```

内部请求示例：

```json
{
  "runId": 3001,
  "workspaceId": 1,
  "projectId": 10,
  "goal": "...",
  "config": {},
  "callback": {
    "eventEndpoint": "/internal/callback/runs/3001/events"
  }
}
```

Python 不信任 Prompt 中的工作区 ID，只信任服务端签名或内部网络传入的上下文。
