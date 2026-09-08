# Shinkou Insight

> 面向企业知识的智能调研与决策 Agent 平台

Shinkou Insight 是由原 Shinkou“需求变更影响分析平台”重构而来的个人全栈项目。新项目不再与 Codex、Claude Code、Cursor 等编码智能体竞争，而是聚焦一个更清晰、可完成、可评估的业务闭环：

```text
上传企业文档 / 添加网页资料
→ 文档解析、切片与向量化
→ 用户提出调研目标
→ RAG 检索内部证据
→ Agent 制订计划并补充外部资料
→ 审核引用与冲突
→ 生成可追溯的决策报告和行动项
```

## 1. 项目价值

该项目用于展示完整的 Agent 工程技术栈，而不是只展示一次模型调用：

- Spring Boot 企业业务控制面：认证、权限、工作区、项目、报告、审计。
- Python Agent Runtime：RAG、模型适配、工具调用、LangGraph 工作流。
- PostgreSQL + Milvus：PostgreSQL 保存业务数据、文档切片和运行记录，Milvus 保存向量索引。
- Vue 3 工作台：知识库、检索测试、Agent 实时轨迹、证据和报告。
- Prompt 工程：结构化输出、版本管理、离线评估、回归测试。
- 可观测性：节点耗时、工具成功率、Token、成本、引用正确率。
- 可选 LoRA：针对“证据支持性判断”这一窄任务进行 QLoRA 实验。

## 2. 核心演示场景

```text
项目：消息队列技术选型
内部资料：
- 订单系统架构说明.pdf
- 峰值流量与可靠性要求.md
- 团队技术能力评估.txt

调研目标：
“结合内部业务约束，比较 Kafka、RabbitMQ 和 RocketMQ，给出当前阶段的推荐方案、风险和待确认问题。”
```

系统应输出：

1. 调研计划和子问题。
2. 内部知识库检索结果。
3. 可选互联网来源。
4. 证据卡片和冲突标记。
5. 带引用的技术选型报告。
6. 后续行动项。
7. 完整节点、工具、Prompt 和模型运行轨迹。

## 3. 技术架构

```text
Vue 3 / TypeScript / Vite / Pinia / TanStack Query
                    │ REST + SSE + HttpOnly Cookie
                    ▼
Spring Boot / Spring Security / MyBatis-Plus
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
PostgreSQL + Milvus            Redis
        │
        ▼
FastAPI / Pydantic / LangGraph / LangChain Core
RAG / Prompt / Tool Registry / Evaluation / Optional LoRA
```

## 4. 文档目录

| 文档 | 内容 |
|---|---|
| `docs/00-refactor-plan.md` | 从旧项目迁移到新项目的具体方案 |
| `docs/01-product-requirements.md` | 产品定位、用户、功能与验收 |
| `docs/02-architecture.md` | 系统架构、边界和关键流程 |
| `docs/03-domain-model.md` | 领域对象、状态机和权限 |
| `docs/04-database.md` | 数据库表、索引和隔离策略 |
| `docs/05-api.md` | 对外 API、内部 API、SSE 事件 |
| `docs/06-rag-design.md` | RAG 入库、检索、引用与评估 |
| `docs/07-agent-workflow.md` | LangGraph 状态、节点、路由和恢复 |
| `docs/08-prompt-engineering.md` | Prompt 模板、版本、Schema 和回归 |
| `docs/09-lora-finetuning.md` | LoRA/QLoRA 可选实验设计 |
| `docs/10-frontend-design.md` | 页面、交互、组件和实时工作台 |
| `docs/11-security.md` | 认证、权限、文件与 Agent 安全 |
| `docs/12-observability-evaluation.md` | Trace、指标、数据集和评估体系 |
| `docs/13-testing.md` | 前后端、AI、RAG、安全和 E2E 测试 |
| `docs/14-development-deployment.md` | 本地开发、部署、环境变量和规范 |
| `docs/15-roadmap.md` | 分阶段开发计划与退出标准 |
| `docs/16-resume-interview.md` | 简历描述、面试讲法和技术亮点 |
| `docs/17-demo-script.md` | 演示数据、录屏流程和展示要求 |
| `docs/18-backlog.md` | 可直接转成 GitHub Issues 的任务清单 |

## 5. MVP 范围

MVP 必须完成：

```text
Cookie 认证与多工作区权限
调研项目管理
PDF / Markdown / TXT 上传与解析
文档切片和 Embedding
Milvus 向量检索 + PostgreSQL 关键词检索
普通 RAG 带引用回答
LangGraph 多阶段调研工作流
SSE 实时运行轨迹
证据、报告和行动项
Prompt 版本和基础评估数据集
Token、耗时、错误和引用指标
```

MVP 明确不做：

```text
十几个独立 Agent
任意浏览器自动操作
任意 Python 代码执行
知识图谱
模型全量微调
复杂审批流
通用低代码 Agent 编排平台
Elasticsearch、Milvus 同时部署
```

## 6. 开发原则

1. 先证明检索正确，再接 LLM。
2. 先完成普通 RAG，再接 LangGraph。
3. 确定性规则放代码，语义判断放模型。
4. 所有内部事实必须可回到真实文档 Chunk。
5. 所有工作区级数据必须在代码和 SQL 两层隔离。
6. LoRA 只有在基线、数据集和评估稳定后才进入实验。
7. 每个阶段必须有明确验收结果和可演示界面。
