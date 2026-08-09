# 00. 项目重构计划

## 1. 重构目标

将旧版 Shinkou 从“多智能体代码审查 / 需求影响分析”重构为“企业知识调研与决策 Agent 平台”。

重构不是重写全部系统，而是保留通用控制面，替换代码审查领域模型和前端交互。

## 2. 为什么重构

旧方向的问题：

- 与 Codex、Claude Code、Cursor 等主流编码 Agent 的能力边界重叠。
- 代码语义理解、仓库索引、跨语言解析、Diff、IDE 交互工程量过大。
- “多人智能体协作”很容易成为技术演示，难形成稳定业务闭环。
- 个人项目需要在有限时间内形成完整、可部署、可演示、可评估的结果。

新方向的优势：

- 业务目标清楚：从企业资料中得到可引用的调研结论。
- RAG、工具调用、工作流、Prompt、评估均有真实使用位置。
- 可以复用旧版账号、工作区、项目、运行轨迹、报告和审计设计。
- 前端不再需要 Monaco、代码树和复杂 IDE 布局。

## 3. 保留、改造和删除

### 3.1 直接保留

```text
users
workspaces
workspace_members
invitations
认证与账号激活
Redis 登录会话
工作区角色和权限校验
projects 基础 CRUD
audit_logs
model_configs
tool_configs
统一 Result 和错误码
Docker Compose 基础设施
```

### 3.2 保留表结构思想，修改业务语义

| 旧概念 | 新概念 | 处理方式 |
|---|---|---|
| 代码项目 | 调研项目 / 知识空间 | `projects` 表保留 |
| project_files | knowledge_assets | 新建表，迁移通用文件字段 |
| requirement | research goal | `agent_sessions.input_text` 迁移为 `research_runs.goal` |
| agent_sessions | research_runs | 可先兼容旧表，稳定后改名 |
| agent_tool_calls | agent_tool_calls | 直接保留并扩展节点信息 |
| affected_files | evidence_items | 删除旧语义，新建证据表 |
| analysis_risks | research_findings | 改为发现、风险和冲突 |
| task_drafts | action_items | 改为后续行动项 |
| reports | research_reports | 完善引用、版本和结构化内容 |

### 3.3 删除或停止开发

```text
Monaco Editor
代码树和多标签代码预览
代码 Diff
代码行号影响分析
PR 审查
代码语言识别 UI
多语言 AST 分析
多人代码审查 Agent
受影响文件专属页面
```

## 4. Git 重构策略

```bash
git checkout main
git tag v0.1-code-analysis
git checkout -b refactor/shinkou-insight-v2
```

推荐目录演进：

```text
Shinkou/
├─ Shinkou-web/       # 保留认证和基础设施，重写业务页面
├─ Shinkou-backend/   # 保留控制面，新增 knowledge/research 模块
├─ Shinkou-ai/        # 从预留目录发展为真实 AI Runtime
├─ docs/              # 替换为 V2 文档
├─ migrations/        # Flyway/Liquibase 数据库迁移
├─ evaluation/        # RAG 与 Prompt 评估数据集
└─ training/          # 可选 LoRA 训练脚本
```

## 5. 数据迁移策略

个人项目不需要保留旧代码分析业务数据，建议：

1. 保留账号、工作区、成员和项目示例数据。
2. 删除旧 `analysis_affected_files`、`analysis_risks` 测试数据。
3. `agent_sessions` 在过渡期增加 `run_type` 字段。
4. 新增 V2 表，不直接复用旧表中的代码专属字段。
5. 使用 Flyway 或 Liquibase，禁止只维护一份手工 SQL。

建议迁移顺序：

```text
V001 旧基础表基线
V002 修复 Cookie 会话相关字段和索引
V003 新增 knowledge_assets / document_chunks / embedding_jobs
V004 新增 research_runs / run_steps / evidence_items
V005 新增 reports / action_items / prompt_versions
V006 新增 evaluation / feedback 表
V007 可选训练和模型版本表
```

## 6. 开发顺序

```text
0. 修复认证和工作区隔离
1. 重写项目与知识库页面
2. 完成文档入库和检索测试
3. 完成普通 RAG
4. 完成 LangGraph 调研工作流
5. 完成报告、证据和行动项
6. 完成评估和可观测性
7. 可选 LoRA 实验
```

## 7. 重构完成标准

旧版代码审查功能不再出现在主导航和核心 API 中；新系统可以完成：

```text
上传真实资料
→ 建立索引
→ 检索正确片段
→ 生成带引用回答
→ 执行多步骤调研
→ 实时展示执行轨迹
→ 生成报告和行动项
→ 回溯模型、Prompt、工具与证据
```
