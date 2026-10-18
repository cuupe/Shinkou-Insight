# 12. 可观测性与评估

## 1. 目标

Agent 项目不能只展示最终答案，必须能解释运行过程和质量变化。

## 2. Trace 维度

每个 Trace 关联：

```text
request_id
run_id
workspace_id
project_id
user_id
step_id
tool_call_id
model_name
prompt_version
retriever_version
```

## 3. 日志

结构化日志字段：

```text
timestamp
level
service
requestId
runId
workspaceId
projectId
node
toolName
latencyMs
errorCode
```

文档原文和 Prompt 全文默认不进入普通日志。

## 4. 指标

### 4.1 系统指标

```text
API 请求量和错误率
PostgreSQL 连接池
Redis 命中率
AI 服务并发
SSE 连接数
索引队列长度
```

### 4.2 Agent 指标

```text
Run 完成率
平均运行时长
平均 Research Round
节点失败率
工具成功率
取消率
输入 / 输出 Token
估算成本
```

### 4.3 RAG 指标

```text
检索延迟
Recall@K
目标 Chunk 平均排名
Rerank 延迟
引用正确率
引用覆盖率
无证据回答率
```

## 5. 离线评估数据集

目录：

```text
evaluation/
├─ datasets/
│  ├─ rag_facts_v1.jsonl
│  ├─ conflict_cases_v1.jsonl
│  └─ report_cases_v1.jsonl
├─ runners/
├─ scorers/
└─ reports/
```

用例：

```json
{
  "id": "rag-001",
  "question": "订单系统峰值 TPS 是多少？",
  "expectedAsset": "业务流量说明.pdf",
  "expectedChunkIds": [1001],
  "requiredFacts": ["3500"],
  "forbiddenFacts": ["10000"],
  "shouldRefuse": false
}
```

## 6. 评估层级

### 6.1 Retrieval Evaluation

不调用生成模型，只评估检索。

### 6.2 Answer Evaluation

评估答案事实、引用和拒答。

### 6.3 Workflow Evaluation

评估：

- 是否选择正确分支。
- 是否在最大轮数停止。
- 是否识别资料不足和冲突。
- 是否产生重复工具调用。

### 6.4 Human Evaluation

人工评分：

```text
正确性
引用质量
完整性
可读性
决策价值
```

## 7. 发布门槛

Prompt、模型或 Retriever 变更必须满足：

- JSON Valid Rate 不下降。
- 关键检索 Recall@K 不明显下降。
- 引用错误不得增加。
- 成本和延迟变化有记录。
- 失败 Case 可查看。

## 8. 线上反馈

报告页支持：

```text
有帮助 / 无帮助
接受结论
引用错误
信息遗漏
人工修改
```

反馈保存原版本和修改版本，用于后续 Prompt 改进和 LoRA 数据筛选。

## 9. Dashboard

推荐面板：

1. 系统健康。
2. Run 成功率和延迟。
3. Token 与成本。
4. 工具失败。
5. RAG 质量。
6. Prompt / 模型版本对比。

## 10. MVP 验收

- 每个 Run 可查看节点和工具耗时。
- 每次模型调用记录 Token 和版本。
- 至少 20 条固定评估用例。
- 一条命令生成评估报告。
- 能比较两个 Prompt 版本。
- 失败 Case 可定位到检索结果和引用。

## 11. 在线检索评估闭环

项目评估页的检索 Runner 使用固定的 Hybrid Recall@5，不调用回答生成模型。用例可标注目标资料、目标 Chunk ID、必需事实和禁止事实：

- 标注了目标 Chunk 时，Recall@5 = Top 5 命中目标 Chunk 数 / 目标 Chunk 总数。
- 只标注目标资料时，以 Top 5 是否命中该资料计为 100% 或 0%。
- 只标注必需事实时，以 Top 5 片段覆盖的必需事实比例作为召回分数。
- 必需事实缺失、禁止事实出现或目标资料未命中时，用例判为失败。
- 引用准确率与结构化输出分数不由检索 Runner 生成，继续由 Agent/人工核验流程负责。

每次运行保存匹配/缺失的目标 ID、资料名和事实摘要。失败用例可转为带问题、验收标准和失败原因的行动项草稿，供负责人确认和跟进。
