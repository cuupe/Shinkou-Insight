# 03. 领域模型与状态设计

## 1. 聚合边界

```text
Workspace Aggregate
├─ Workspace
├─ WorkspaceMember
└─ Invitation

Project Aggregate
├─ Project
├─ KnowledgeAsset
├─ DocumentChunk
└─ EmbeddingJob

Research Aggregate
├─ ResearchRun
├─ RunStep
├─ AgentToolCall
├─ EvidenceItem
├─ ResearchFinding
└─ ActionItem

Report Aggregate
├─ ResearchReport
├─ ReportSection
├─ ReportCitation
└─ ReportVersion

AI Configuration Aggregate
├─ ModelConfig
├─ ToolConfig
├─ PromptTemplate
└─ PromptVersion
```

## 2. 项目状态

```text
ACTIVE → ARCHIVED → ACTIVE
ACTIVE → DELETED
ARCHIVED → DELETED
```

删除为软删除。DELETED 项目不能创建新资产和运行，但历史审计可保留。

## 3. 知识资产状态

解析状态：

```text
PENDING → PARSING → PARSED
PARSING → PARSE_FAILED → PARSING
```

索引状态：

```text
PENDING → INDEXING → INDEXED
INDEXING → INDEX_FAILED → INDEXING
INDEXED → STALE → INDEXING
```

状态要求：

- 只有 `PARSED` 资产可以进入 Embedding。
- checksum 变化后标记 `STALE`。
- `DELETED` 资产不得被检索。

## 4. Research Run 状态

```text
PENDING → RUNNING → COMPLETED
PENDING → CANCELLED
RUNNING → CANCELLING → CANCELLED
RUNNING → FAILED
FAILED → RETRYING → RUNNING
```

字段：

```text
id / run_no
workspace_id / project_id / created_by
goal
run_type
allow_web_search
max_rounds / current_round
status / current_node / progress
model_snapshot / prompt_snapshot
input_tokens / output_tokens / estimated_cost
error_code / error_message
started_at / completed_at
```

## 5. Run Step 状态

```text
PENDING → RUNNING → COMPLETED
RUNNING → FAILED
RUNNING → SKIPPED
FAILED → RETRYING → RUNNING
```

常见节点：

```text
PLAN
RETRIEVE_INTERNAL
EVALUATE_EVIDENCE
REWRITE_QUERY
SEARCH_WEB
EXTRACT_EXTERNAL_EVIDENCE
SYNTHESIZE_FINDINGS
WRITE_REPORT
REVIEW_REPORT
PERSIST_RESULT
```

## 6. Tool Call 状态

```text
PENDING / RUNNING / SUCCESS / FAILED / TIMEOUT / REJECTED
```

`REJECTED` 用于人工确认未通过或工具策略拒绝。

## 7. 证据模型

Evidence Item：

```text
source_type: INTERNAL_CHUNK | WEB_PAGE
support_type: SUPPORT | PARTIAL | CONFLICT | CONTEXT
question_id
claim
quote
chunk_id 或 source_url_snapshot_id
asset_name / page_number / section_title
retrieval_score / rerank_score
confidence
created_by_step_id
```

关键原则：

- `quote` 必须来自原文，不允许模型凭空生成。
- 内部证据必须关联真实 `chunk_id`。
- 外部证据保存抓取快照摘要、时间和来源标识。

## 8. Finding 类型

```text
FACT
RECOMMENDATION
RISK
CONFLICT
INFORMATION_GAP
ASSUMPTION
```

Finding 与 Evidence 是多对多关系。一个结论可以由多个证据支持，一个证据也可用于多个结论。

## 9. 报告状态

```text
DRAFT → GENERATED → REVIEWED → PUBLISHED
DRAFT / GENERATED → ARCHIVED
```

个人项目 MVP 可以简化为：

```text
DRAFT → FINAL
```

但数据库预留 `version_no`、`review_status` 和 `published_at`。

## 10. 行动项状态

```text
DRAFT → ACCEPTED → TODO → IN_PROGRESS → DONE
DRAFT → REJECTED
TODO / IN_PROGRESS → CANCELLED
```

## 11. Prompt 状态

```text
DRAFT → ACTIVE → DEPRECATED
```

同一 `scene` 同一时刻只允许一个默认 ACTIVE 版本，历史运行保存 Prompt 快照或版本引用。

## 12. 评估实体

```text
EvaluationDataset
EvaluationCase
EvaluationRun
EvaluationCaseResult
HumanFeedback
```

评估用例必须包含：

```text
输入问题
限定项目或测试语料
期望命中文档 / Chunk
关键结论
禁止结论
评分规则
```

## 13. 权限矩阵

| 操作 | OWNER | ADMIN | MEMBER | VIEWER |
|---|:---:|:---:|:---:|:---:|
| 查看项目 | 是 | 是 | 是 | 是 |
| 上传资产 | 是 | 是 | 是 | 否 |
| 删除资产 | 是 | 是 | 自己上传可选 | 否 |
| 发起 Run | 是 | 是 | 是 | 否 |
| 查看全部 Run | 是 | 是 | 可查看项目内 | 可选 |
| 修改模型配置 | 是 | 可选 | 否 | 否 |
| 邀请成员 | 是 | 是 | 否 | 否 |
| 导出报告 | 是 | 是 | 是 | 是 |
