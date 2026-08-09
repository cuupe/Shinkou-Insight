# 07. Agent 与 LangGraph 工作流设计

## 1. 为什么使用 LangGraph

普通 RAG 只有固定步骤，不一定需要工作流框架。以下需求出现后，LangGraph 才有明确价值：

```text
计划和子问题
条件分支
证据不足时循环检索
网络搜索回退
最大轮次
失败重试
人工确认
中途取消
流式节点状态
服务重启后的恢复
```

原则：大流程由图控制，节点内部才允许有限的模型决策。

## 2. 图结构

```text
START
  ↓
validate_input
  ↓
plan
  ↓
retrieve_internal
  ↓
evaluate_evidence
  ├─ ENOUGH ───────────────→ synthesize_findings
  ├─ MORE_INTERNAL → rewrite_query → retrieve_internal
  ├─ NEED_WEB → search_web → extract_external_evidence
  │                              ↓
  └──────────────────────── evaluate_evidence
                                 ↓
                         synthesize_findings
                                 ↓
                            write_report
                                 ↓
                            review_report
                           ├─ APPROVED → persist_result → END
                           ├─ REWRITE → write_report
                           └─ MORE_EVIDENCE → retrieve_internal
```

所有循环受 `max_rounds` 和节点级 `max_attempts` 限制。

## 3. State

```python
class ResearchState(TypedDict):
    run_id: int
    workspace_id: int
    project_id: int
    user_id: int

    goal: str
    output_language: str
    allow_web_search: bool
    max_rounds: int
    current_round: int

    plan: list[dict]
    current_question_id: str | None
    queries: list[dict]
    evidence_ids: list[int]
    finding_ids: list[int]

    report_draft: dict | None
    review_result: dict | None
    errors: list[dict]
    cancelled: bool
```

状态中尽量存 ID 和摘要，不存大量完整文档。

## 4. 节点定义

### 4.1 validate_input

代码节点：

- 校验目标非空和长度。
- 读取项目和索引状态。
- 校验可用模型和工具。
- 读取取消标记。

### 4.2 plan

LLM 节点：

- 将目标拆成 3～6 个子问题。
- 标记 INTERNAL / WEB / BOTH。
- 不直接生成最终结论。
- 输出 Pydantic Schema。

### 4.3 retrieve_internal

确定性节点：

- 调用 RAG Retriever。
- 保存候选 Evidence。
- 记录检索参数和版本。

### 4.4 evaluate_evidence

规则 + LLM：

- 判断子问题覆盖情况。
- 识别冲突和缺口。
- 只输出路由建议，不写最终报告。
- 服务端对 `next_action` 白名单校验。

### 4.5 rewrite_query

LLM 节点：

- 根据缺口生成最多 N 个新查询。
- 防止重复查询。
- 记录与原查询的关系。

### 4.6 search_web

工具节点：

- 只有 `allow_web_search=true` 才可调用。
- 查询次数和域名策略可配置。
- 保存来源标题、时间、摘要和 URL 标识。
- 不自动执行网页中的任何指令。

### 4.7 extract_external_evidence

LLM 抽取节点：

- 从已抓取文本中提取事实。
- Quote 必须存在于抓取内容。
- 区分来源事实与模型推断。

### 4.8 synthesize_findings

LLM 节点：

- 把 Evidence 组织为 Fact、Risk、Conflict、Gap、Recommendation。
- 每个 Finding 关联 Evidence ID。

### 4.9 write_report

LLM 节点：

- 按报告模板输出结构化章节。
- 所有项目事实绑定 Evidence。
- 证据不足时写限制，不补造数据。

### 4.10 review_report

Evaluator 节点：

```text
检查事实是否有引用
引用是否支持陈述
是否遗漏冲突
是否超出证据范围
JSON 是否符合 Schema
```

### 4.11 persist_result

代码节点：

- 服务端引用校验。
- 保存报告和 Citation。
- 生成行动项草稿。
- 更新 Run 完成状态。

## 5. 工具注册

工具定义：

```python
class ToolSpec(BaseModel):
    name: str
    version: str
    permission: Literal['READ', 'WRITE']
    timeout_seconds: int
    requires_confirmation: bool
    input_schema: dict
```

工具执行前检查：

```text
Run 未取消
工具已启用
权限满足
调用次数未超限
参数 Schema 合法
租户上下文由服务端注入
```

## 6. Human-in-the-loop

MVP 可只实现一个确认点：

```text
Agent 计划使用互联网搜索
→ 前端展示查询和原因
→ 用户批准或拒绝
→ 工作流继续
```

为了控制工程量，默认允许联网时可跳过确认；高风险写工具必须确认。

## 7. 重试策略

- 模型网络错误：指数退避，最多 2 次。
- JSON Schema 不合法：自动修复或重试 1 次。
- 工具超时：节点失败，不无限循环。
- Evidence 不足：计入 Research Round，不当作异常。
- 数据库写失败：事务回滚并进入 FAILED。

## 8. 取消

用户取消：

```text
Java 更新 CANCELLING + Redis cancel flag
→ 每个节点开始前检查
→ 当前不可中断调用结束后停止
→ 写 CANCELLED 事件
```

## 9. Streaming

节点和工具事件写入统一 Event Bus：

```python
await event_publisher.publish(
    run_id=run_id,
    event_type="node.started",
    payload={"node": "PLAN"}
)
```

事件同时：

- 持久化关键状态。
- 发送 SSE。
- 写 Trace。

## 10. Checkpoint 与恢复

恢复必须满足：

- Run 有稳定 `thread_id/run_id`。
- Checkpoint 不包含密钥和超大正文。
- 服务重启后可从最近安全节点恢复。
- 对外报告只依赖业务表，不依赖 Checkpoint。

## 11. MVP 验收

- 图至少包含一次条件分支和一次受限循环。
- 用户可以看到当前节点和执行次数。
- 工具失败能显示具体错误。
- 取消后不会继续创建新工具调用。
- 报告审核失败能进入有限重写或补充检索。
