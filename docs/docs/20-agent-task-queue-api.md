# 智能分析记录接口约定

项目规划提交后进入智能分析详情，使用调研运行资源承载。分析记录列表用于查看历史运行；行动项不进入该列表。

## 状态模型

```text
queued → running → completed
             ├── paused → running
             ├── failed
             └── cancelled
```

完成、失败、取消是终态，后续进度回调不能重新打开运行。`retry` 仅接受失败或取消的记录，并返回新的运行 ID；调用方应跳转到返回的 ID，旧记录与失败原因保留。

## 进度与结果

详情接口返回 `currentNode`、`currentStep`、`progress`、`startedAt`、`finishedAt`、`durationSeconds`、`lastActivityAt` 和最近 100 条可观察的 `events`。事件可包含子任务的标题、状态、摘要和错误；不包含模型内部推理。`plan` 始终是含 `summary`、`steps` 的对象。

当前页面每 2 秒读取详情，终态停止轮询；切换运行和离开页面时取消旧请求。读取失败或 `runtimeAvailable=false` 时保留最近数据并显示重连提示，不将断连当成任务失败。进度是阶段进度；等待时间不转换为虚构进度。Token 未返回时显示“暂未返回”。

输入 `goal` 只用于目标展示。结论来自 `report.executive_summary`，完成回调在同一事务中更新终态并保存报告草稿供审查。回调忽略不改变运行状态的普通事件，重复完成回调不重复生成报告。

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

## 会话连续性与模型工具链路

聊天上下文由 Java 按 `thread_id` 和本轮 `user_message_id` 从数据库读取：只包含本轮之前的用户消息及已完成的助手回答，最多 200 条。浏览器提供的历史不再作为上下文事实来源，失败的半截答案不会混入下一轮。Python 按顺序保留历史，在达到 token 预算后压缩；系统约束和用户明确给出的数值会单独保留。

HTTP 模型网关使用流式 function calling，为模型提供本轮实际允许的 `search_web`、`search_knowledge`、`search_graph` 和 `calculator` 定义。未开启联网或被工作区禁用的工具不会出现在定义中，也不能通过模型自行生成调用绕过限制。工具结果通过携带同一 `tool_call_id` 的 `tool` 消息回传。搜索服务失败与工具未开启分别记录。

可审计事件保存在运行记录中：

| 事件 | 内容 |
| --- | --- |
| `model.requested` | 可见工具定义、工具选择模式、消息数量、实际回传的工具结果 ID |
| `model.tool_call` | 模型选择的工具、调用 ID、参数 |
| `tool.started` / `tool.completed` | 工具执行状态和结果 |
| `model.tool_result` | 调用 ID、结果、回传角色 `tool` |

原生工具循环最多执行 8 次工具调用，同时服从更小的工作区调用预算；相同工具和参数复用结果。重复生成或超过输出长度时停止，一次自动恢复仍使用同一本轮上下文。连续流未收到完成标记时不能被保存为成功答案。

`thinking.started` / `thinking.completed` 只提供阶段和耗时。内部 reasoning 原文不再发送、保存或渲染；历史 `thinking.delta` 事件在前后端均忽略其文本。模型仍有流式活动时不使用整个阶段的固定秒数强行中断，连接和连续无数据仍由 HTTP 超时约束。

计算器仅支持有界的算术表达式，不执行任意 Python；整数和分数计算保持精确。联网结果仍需有可读取的相关来源，检索执行成功不等于事实列表必然完整。
