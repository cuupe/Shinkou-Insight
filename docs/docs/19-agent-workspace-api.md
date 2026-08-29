# Agent 工作台接口约定

当前链路由 Java 后端统一承接鉴权、项目权限、运行持久化和 SSE；暂不调用模型，常规处理器会基于当前项目已建立索引的资料返回检索结果和真实引用。后续 Python Agent 通过 Java 内部处理器替换接入，浏览器不直接连接 Python。

页面会调用下面两个接口。接口统一沿用现有响应包装：

```json
{
  "code": "SUCCESS",
  "message": "",
  "data": {}
}
```

## 1. 发送消息

```http
POST /workspaces/{workspaceId}/projects/{projectId}/agent/messages
Content-Type: application/json
```

请求体：

```json
{
  "threadId": "thread-123",
  "messageId": "message-9001",
  "content": "结合当前项目资料，消息队列在峰值流量下如何保证可靠投递？",
  "context": {
    "assetIds": ["asset-01"],
    "runId": "run-2408",
    "mode": "research"
  }
}
```

返回：

```json
{
  "runId": "agent-run-2408",
  "messageId": "message-9001",
  "status": "RUNNING",
  "eventsUrl": "/api/workspaces/shinkou-labs/projects/queue-selection/agent/runs/agent-run-2408/events"
}
```

`eventsUrl` 可选。未返回时，前端会按照 `runId` 拼接默认 SSE 地址。

## 2. Agent 事件流

```http
GET /workspaces/{workspaceId}/projects/{projectId}/agent/runs/{runId}/events
Accept: text/event-stream
```

每条 SSE `data` 是一个 JSON 事件：

```text
data: {"type":"event.updated","runId":"agent-run-2408","event":{...}}
```

支持的事件：

| type | 用途 | 必要字段 |
| --- | --- | --- |
| `run.started` | 标记运行开始 | `runId` |
| `event.updated` | 更新线性执行节点 | `event.id/kind/title/detail/status` |
| `message.delta` | 流式追加回答文本 | `messageId/delta` |
| `citation.added` | 增加可追溯引用 | `citation.id/title/source/quote` |
| `media.added` | 增加 Agent 输出图片或视频 | `messageId/media.id/kind/name/url` |
| `message.completed` | 标记回答生成完成 | `messageId` |
| `run.completed` | 关闭运行 | `runId` |
| `run.failed` | 展示失败状态 | `runId/message` |

其中 `event.kind` 建议使用 `plan`、`search`、`tool`、`evidence`、`synthesis`，这样前端可以显示对应的执行节点图标。

## 3. 设计约束

- SSE 事件顺序应保持服务端实际执行顺序。
- `message.delta` 可以逐字或按段发送，前端会直接追加，不要求固定分片长度。
- 工具调用的参数、模型隐藏思维和敏感凭证不要通过事件流返回；仅返回可审计的动作摘要。
- 引用应包含原文片段和来源，前端会在右侧“证据引用”区域展示。
- 运行失败时发送 `run.failed` 并关闭连接，前端会保留已经产生的事件和部分回答。

## 4. 附件上传

```http
POST /workspaces/{workspaceId}/projects/{projectId}/agent/attachments
Content-Type: multipart/form-data
```

附件由 Java 接收并保存到对象存储，数据库只保存附件元数据和 `uploadId`；开发环境使用 MinIO，生产环境可切换到 S3/OSS。接口会返回受权限保护的内容地址。发送消息时必须携带当前项目生成的 `uploadId`，Java 会再次校验附件归属，不能直接相信浏览器传来的文件标识。

```http
GET /workspaces/{workspaceId}/projects/{projectId}/agent/attachments/{uploadId}/content
```

图片和视频的输出事件已经纳入前端协议和渲染层；当前不调用模型的常规处理器不会主动生成媒体，后续 Python Agent 只需通过同一事件协议返回已生成或已处理的媒体地址。
