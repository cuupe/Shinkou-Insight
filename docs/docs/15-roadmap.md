# 15. 开发路线图

以下按个人项目 10～12 周设计，可根据时间压缩。每个阶段必须有可展示产物。

## Phase 0：重构基线

目标：旧系统冻结，新系统可启动。

任务：

- 打 Tag 和 V2 分支。
- 删除主导航中的代码审查入口。
- 补齐 Cookie 认证。
- 引入数据库迁移工具。
- 重组后端模块目录。

退出标准：

```text
登录、刷新、退出正常
工作区越权测试通过
项目 CRUD 正常
三服务可本地启动
```

## Phase 1：知识资产

- 新增表和 API。
- PDF / Markdown / TXT Parser。
- 上传、状态、重试和删除。
- Asset List / Detail 页面。

退出标准：真实文档可解析并展示 Chunk。

## Phase 2：RAG 检索

- Embedding Provider。
- pgvector。
- Keyword Search。
- Hybrid Fusion。
- Retrieval Playground。
- 检索评估集。

退出标准：目标 Chunk Recall@K 达到自己设定的基线，并可重复评估。

## Phase 3：普通 RAG

- Query Rewrite 可选。
- Answer Prompt。
- Citation DTO。
- Quote 和 Chunk 服务端校验。
- 资料不足拒答。

退出标准：带引用问答完整可演示。

## Phase 4：Agent 工作流

- LangGraph State 和节点。
- Plan / Retrieve / Evaluate / Write / Review。
- 受限循环和重试。
- Run / Step / Tool 持久化。
- SSE 工作台。

退出标准：完整调研 Run 可完成、取消、失败和重试。

## Phase 5：报告和行动项

- Report 结构和 Citation。
- Markdown 页面。
- 导出。
- Action Item 状态。

退出标准：从 Run 到报告和行动项闭环。

## Phase 6：可观测性和评估

- Token、成本和时延。
- Prompt 版本。
- Evaluation Dashboard。
- 20～30 个固定 Case。

退出标准：可以对比两个 Prompt 或模型配置。

## Phase 7：工程完善

- Testcontainers。
- Playwright E2E。
- CI。
- Docker 镜像。
- HTTPS 演示环境。
- README 截图和演示视频。

## Phase 8：LoRA 实验（可选）

- 筛选证据判定数据。
- Prompt 基线。
- QLoRA。
- 独立测试集。
- Model Router。

只有前七阶段完成后再进行。

## 风险控制

| 风险 | 控制 |
|---|---|
| 文档解析质量差 | MVP 先支持文本型 PDF，不做 OCR |
| Agent 无限循环 | max_rounds 和节点 attempt 硬限制 |
| 模型费用高 | 小模型用于改写/分类，评估时控制样本 |
| 前端工程量过大 | 先做五个核心页面，不做低代码编排器 |
| 技术栈堆叠 | 每个技术必须绑定一个业务需求和验收 |
| LoRA 无提升 | 与优化 Prompt 做对照实验，无增益则不接入 |
