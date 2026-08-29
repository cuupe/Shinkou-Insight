# Agent 任务队列接口约定

Agent 任务队列统一使用调研运行资源承载，行动项不进入该队列。

## 状态模型

```text
queued → running → completed
             ├── paused → running
             ├── failed → queued
             └── cancelled
```

前端任务字段至少包含：

```ts
{
  id,
  runId,
  projectId,
  title,
  source: "agent-chat" | "research",
  status: "queued" | "running" | "paused" | "completed" | "failed" | "cancelled",
  priority: "low" | "normal" | "high",
  progress,
  currentStep,
  threadId,
  time,
  duration,
  tokens
}
```

## 现有接口映射

```text
POST /workspaces/{workspaceId}/projects/{projectId}/runs
GET  /workspaces/{workspaceId}/projects/{projectId}/runs
GET  /workspaces/{workspaceId}/projects/{projectId}/runs/{runId}
GET  /workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/steps
GET  /workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/tools
GET  /workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/evidences
GET  /workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/events
POST /workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/cancel
POST /workspaces/{workspaceId}/projects/{projectId}/runs/{runId}/retry
```

Agent 对话创建的任务使用同一套 `runId` 关联队列；`threadId` 用于回到对应对话。后端接入后，前端可以把本地队列存储替换为 `runsApi` 和事件流，不需要改动队列页面结构。
