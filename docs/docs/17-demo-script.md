# 17. 项目演示与录屏脚本

## 1. 演示目标

在 5～8 分钟内证明：

```text
这是完整产品
RAG 检索真实可验证
Agent 流程不是黑盒
有安全和多租户设计
有评估而不只是“看起来不错”
```

## 2. 演示数据

项目：`消息队列技术选型`

准备三份原创或可公开使用的示例资料：

1. `订单系统架构说明.md`
2. `业务流量与可靠性要求.md`
3. `团队技术能力评估.md`

内容包含明确事实：

```text
峰值 TPS
消息可靠性要求
是否要求顺序 / 事务消息
团队当前运维经验
未来增长假设
```

## 3. 录屏流程

### 0:00–0:40 产品定位

展示 README 和架构图，说明不是编码助手，而是知识调研和证据报告平台。

### 0:40–1:30 知识资产

- 创建项目。
- 上传三份资料。
- 展示解析和索引状态。
- 打开 Chunk 和来源。

### 1:30–2:20 检索 Playground

查询：

```text
订单系统峰值 TPS 是多少？
```

展示：

- Top K。
- 目标文档和页码。
- Vector / Keyword / RRF / Rerank 分数。

### 2:20–3:00 普通 RAG

展示答案和引用，点击 `[E1]` 查看原文。

再问一个资料中没有的问题，展示资料不足而非编造。

### 3:00–5:30 Agent 调研

创建：

```text
结合内部资料比较 Kafka、RabbitMQ 和 RocketMQ，给出当前推荐、风险和待确认问题。
```

展示：

- Planner 子问题。
- 内部检索。
- 证据评估。
- 可选 Web Search。
- Report Reviewer。
- SSE 时间线和工具耗时。

### 5:30–6:30 报告

- 打开结论和引用。
- 查看冲突 / 信息缺口。
- 接受行动项。
- 展示模型、Prompt 和 Retriever 版本。

### 6:30–7:20 评估

展示固定数据集：

- Recall@K。
- 引用正确率。
- Prompt v1 / v2 对比。
- 一个失败 Case。

### 7:20–8:00 工程化

快速展示：

- Docker Compose。
- CI。
- 多工作区越权测试。
- 文档和 Roadmap。

## 4. 截图清单

```text
Workspace Dashboard
Asset List
Asset Chunk Detail
Retrieval Playground
Research Workspace 三栏
Report + Citation Drawer
Evaluation Dashboard
Architecture Diagram
```

## 5. 演示注意

- 不使用只含一两句话的假文档。
- 不预先把答案写进 Prompt。
- 展示一次资料不足或冲突场景。
- 不声称 LoRA 有提升，除非有对照评估。
- 演示数据和结果固定，避免现场模型波动导致失败。
