# 10. 前端产品与交互设计

## 1. 技术栈

```text
Vue 3
TypeScript
Vite
Vue Router
Pinia
TanStack Query
Axios
Markdown Renderer
ECharts（指标页）
```

移除 Monaco 和代码 IDE 相关依赖。

## 2. 信息架构

```text
/login
/activate
/workspace-select
/workspaces/:workspaceId
├─ dashboard
├─ projects
├─ members
└─ settings
   ├─ models
   ├─ tools
   └─ prompts

/workspaces/:workspaceId/projects/:projectId
├─ overview
├─ knowledge
│  ├─ assets
│  ├─ assets/:assetId
│  └─ playground
├─ research
│  ├─ new
│  ├─ runs
│  └─ runs/:runId
├─ reports
├─ action-items
└─ evaluation
```

## 3. 页面要求

### 3.1 Workspace Dashboard

展示：

- 项目数、资产数、运行数、完成率。
- 最近运行和失败运行。
- 最近报告。
- Token 和成本趋势（有数据后）。

### 3.2 Project Overview

展示：

- 项目描述。
- 知识资产状态。
- 最近调研。
- 报告数量。
- 快速入口：上传资料、检索测试、创建调研。

### 3.3 Knowledge Asset List

功能：

- 拖拽上传。
- 类型、状态、上传者筛选。
- 索引进度。
- 重试、重新索引、删除。
- 失败原因提示。

### 3.4 Asset Detail

展示：

- 元数据、checksum、解析器版本。
- 文本预览。
- Chunk 列表。
- 页码和标题。
- 单 Chunk 复制和检索测试。

### 3.5 Retrieval Playground

左侧参数：

```text
查询
Top K
Vector / Keyword / Hybrid
是否 Rerank
资产过滤
```

右侧结果：

- 排名和来源。
- 四类分数。
- 原始文本。
- 打开文档位置。

这是证明 RAG 不是黑盒的关键页面。

### 3.6 Create Research Run

表单：

```text
调研目标
是否联网
最大轮数
报告模板
输出语言
```

创建前显示预计使用的知识资产数量和联网策略。

### 3.7 Research Workspace

三栏：

```text
左：计划、节点和进度
中：实时事件、工具轨迹和错误
右：证据、来源和冲突
```

顶部：

- Run 状态。
- 取消、重试。
- Token、耗时、轮次。

### 3.8 Report Detail

- Markdown 主体。
- 结构化目录。
- 点击 `[E1]` 打开证据抽屉。
- 显示内部 / 外部来源。
- 编辑、导出、查看生成信息。
- 显示“模型 / Prompt / Retriever 版本”。

### 3.9 Evaluation Dashboard

- 数据集和配置选择。
- 检索 Recall@K。
- 引用正确率。
- JSON 成功率。
- Prompt / 模型对比。
- 失败 Case 查看。

## 4. 状态管理

Pinia：

```text
auth.store
workspace.store
project.store
ui.store
```

服务器状态尽量交给 TanStack Query：

```text
assets
runs
reports
evaluation results
```

SSE 事件可以写入独立 `runEventStore`，Run 完成后刷新服务端数据。

## 5. SSE 客户端

要求：

- 自动重连。
- 事件 ID 去重。
- 页面刷新后先读取 Run 当前状态，再连接 SSE。
- 运行结束关闭连接。
- 组件卸载清理连接。
- 心跳超时显示连接异常，不误判 Run 失败。

## 6. 组件清单

```text
AssetUploader
AssetStatusBadge
ChunkCard
RetrievalScorePanel
RunTimeline
RunStepCard
ToolCallCard
EvidenceCard
CitationDrawer
ConflictBadge
ReportMarkdown
ModelUsageCard
EvaluationCaseTable
```

## 7. 响应式与可访问性

- 三栏工作台在窄屏切换为 Tabs。
- 长文档名和 URL 可换行或截断。
- 状态不能只依赖颜色。
- 所有按钮有明确 loading / disabled 状态。
- 错误信息可复制。
- 键盘可以打开和关闭证据抽屉。

## 8. 空状态

每个页面提供下一步动作：

```text
没有项目 → 创建项目
没有资产 → 上传资料
没有索引 → 查看失败或开始索引
没有 Run → 创建首次调研
没有报告 → 从已完成 Run 生成
```

## 9. 前端验收

- 登录刷新不丢失。
- 工作区切换后不显示旧工作区缓存。
- 上传和索引状态可见。
- 检索结果可以定位来源。
- SSE 能正确处理重连和完成。
- 报告引用抽屉展示真实 Quote。
- 常见 1366px 屏幕可正常使用。
