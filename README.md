# Shinkou Insight

Shinkou Insight 是一个面向团队的证据驱动调研、项目规划与决策审查工作台。它把分散的内部资料、可选的外部来源和 Agent 执行过程组织成可追溯的研究结果，帮助团队从“提出问题”走到“形成计划、完成审查并落地行动”。

~~~text
工作区 / 项目
    → 资料上传与解析
    → 混合检索与证据收集
    → Agent 规划、研究、分析和写作
    → 引用校验与报告审查
    → 行动项、评估和持续改进
~~~

它不是一个开放式聊天机器人，也不替代项目负责人、法务、财务或管理层做最终决策。系统的重点是让每个重要结论都能回到来源，让证据不足、来源冲突和待确认事项显式呈现。

## 项目特点

### 1. 以工作区和项目为隔离边界

用户、成员、项目、资料、运行记录、报告、行动项和配置都围绕工作区与项目组织。后端在资源访问、检索、缓存和 Agent 运行过程中持续携带租户上下文，避免把前端隐藏按钮当成唯一权限控制。

### 2. 从资料到证据，而不是只生成答案

资料先经过解析、切片和索引，再进入检索与回答流程。证据记录包含来源名称、资产、页码或章节、URL、来源类型以及向量、关键词、融合和重排分数。报告中的事实性内容可以回到具体证据，而不是只保留一段无法解释的模型输出。

### 3. 可解释的混合 RAG

AI 服务同时支持向量检索、关键词检索和混合检索，并使用 RRF / 加权 RRF / 线性融合组织候选结果；需要时再进行确定性的轻量重排。知识库 Playground 可以查看 Top-K、来源位置和各类分数，适合验证“为什么召回了这段内容”。

### 4. 受约束的 Agent 工作流

运行时支持自动选择以下处理路径：

- 直接回答：适合范围明确、证据已足够的问题。
- ReAct：在有限工具调用次数内逐步检索并回答。
- Plan-and-Solve：先生成有限步骤，再按步骤执行。
- Reflection：生成后进行一次有边界的回答质量检查。

复杂研究可以使用协调器和多个专用 Agent，包括规划、研究、分析、写作、审查、网络研究等角色。默认使用进程内消息总线，也可以通过 HTTP Worker 拆分角色进程。

### 5. 研究过程可观察、可取消、可恢复

研究运行会记录计划、节点、工具调用、状态、耗时、Token 使用量和错误。前端通过 SSE 展示实时事件，支持重连、取消、重试和运行详情查看；Redis Stream 可用于异步任务队列，运行过程也可以通过回调与后端同步。

### 6. 资料来源与输出格式较完整

解析器覆盖文本、Markdown、PDF、Word、Excel、PowerPoint、HTML、CSV、JSON、图片、音频和视频等类型。OCR、PDF 渲染、Office 转换、FFmpeg 和 faster-whisper 按可用性启用，缺少可选工具时会返回可见警告。研究结果还可以通过文档生成工具导出为 Markdown、DOCX、PDF 或 PPTX。

### 7. 把结论放进审查和行动闭环

项目页面不止展示报告，还包括规划、报告审查、行动项和评估。审查模型会关注引用完整性、证据支持、事实一致性、数字一致性、冲突和风险等级；研究结果可以进一步转成负责人、优先级和截止时间明确的行动项。

### 8. 安全默认值优先

系统包含基于 Cookie 会话的认证、Redis 会话控制、验证码和登录限流、CSRF/CORS 配置、工作区成员权限、文件类型与大小限制、对象存储隔离、内部 API Key、审计记录以及安全 Harness。文档和网页内容按不可信数据处理，不会因为检索文本中的“指令”而改变工具权限或租户上下文。

## 功能地图

| 模块 | 能力 |
| --- | --- |
| 工作区 | 工作区概览、成员与邀请、通知、统计、存储配额 |
| 项目 | 项目目标、规划、知识资产、研究运行、报告、审查、行动项、评估 |
| 知识库 | 文件上传、解析状态、索引状态、重新索引、内容预览、Chunk 查看 |
| 检索 | 向量 / 关键词 / 混合检索、过滤、融合、重排、检索 Playground |
| Agent | 对话工作台、研究计划、工具调用、事件流、多 Agent 协作、任务队列 |
| 来源 | 内部资料、图谱结果、可选网页搜索、多源搜索、来源内容提取 |
| 报告 | 结构化报告、引用、限制项、生成信息、文档文件导出 |
| 审查 | 引用完整性、数字校验、冲突升级、风险等级、阻断项 |
| 配置 | 模型、Embedding、工具、联网搜索、项目切片配置、运行策略 |
| 质量 | Token 和耗时统计、运行事件、评估用例、反馈与安全检查 |

## 系统架构

~~~text
┌──────────────────────┐
│ Vue 3 + TypeScript    │  apps/web
│ Vite / Router / UI    │
└──────────┬───────────┘
           │ /api 代理 + Cookie 会话
┌──────────▼───────────┐
│ Spring Boot 4         │  apps/backend :8080
│ 认证 / 权限 / 业务 API │
│ Flyway / MyBatis       │
└──────┬───────┬────────┘
       │       │
       │       └──────────────┐
       │                      │
┌──────▼────────┐     ┌───────▼──────────┐
│ PostgreSQL     │     │ FastAPI AI 服务   │  apps/ai-service
│ 业务 / 运行数据 │     │ RAG / Agent / 文件 │
└───────────────┘     └──┬─────┬────┬────┘
                          │     │    │
                    ┌─────▼┐ ┌──▼──┐ ┌▼────────┐
                    │Milvus│ │Redis│ │MinIO    │
                    │向量  │ │队列 │ │文件对象 │
                    └──────┘ └─────┘ └─────────┘
                          │
                    ┌─────▼─────┐
                    │ Neo4j     │  可选图谱后端
                    └───────────┘
~~~

仓库中的 docker-compose.yml 主要负责 AI 服务和基础设施；Java 后端与 Vue 前端通常在本机启动。也可以单独通过 Compose 启动 ai-service，此时容器内部端口为 8000，宿主机端口由 AI_SERVICE_PORT 控制。Windows 快速启动脚本默认让本机 AI 服务监听 8003，这是为了匹配根目录 .env.example 中的后端配置。

## 代码结构

~~~text
.
├─ apps/
│  ├─ web/                  # Vue 3 + TypeScript 前端
│  ├─ backend/              # Spring Boot 业务后端
│  └─ ai-service/           # FastAPI AI Runtime、RAG、Agent、文件分析
├─ contracts/               # 跨服务契约目录
├─ docs/                    # 产品、架构、API、安全、部署和运行文档
├─ infra/                   # 基础设施资源目录
├─ scripts/                 # Windows 启动、检查和维护脚本
├─ tools/runtime/           # 可选的本地 OCR / PDF / Office 工具
├─ docker-compose.yml       # AI 服务与基础设施编排
├─ .env.example             # 环境变量模板
└─ STRUCTURES.md            # 项目结构参考
~~~

## 快速开始

### 环境要求

| 工具 | 要求 |
| --- | --- |
| Node.js | 22.18+ 或 24.12+ |
| Java | 21 |
| Maven | 3.9+ |
| Python | 3.11+ |
| Docker | Docker Desktop + Compose v2 |

### 1. 准备环境变量

在项目根目录执行：

~~~powershell
Copy-Item .env.example .env
~~~

本地开发可以使用模板中的默认数据库、Redis、MinIO 和内部 API Key。首次启用认证数据前，请为 SHINKOU_ENCRYPTION_KEY 设置一个稳定的 Base64 编码 32 字节密钥；密钥保存后不要随意更换，否则已加密凭据无法解密。

默认配置有意保持可启动：

~~~text
LLM_MODE=http
EMBEDDING_MODE=hash
GRAPH_MODE=memory
ENABLE_WEB_SEARCH=false
MCP_ENABLED=false
TASK_QUEUE_ENABLED=true
CACHE_ENABLED=true
~~~

真正使用模型、外部 Embedding 或网页搜索时，需要在 Web 界面配置对应的地址、模型和凭据；不要把真实密钥提交到仓库。

### 2. 启动基础设施

~~~powershell
docker compose --env-file .env up -d postgres redis milvus-etcd milvus-minio milvus minio minio-init
docker compose ps
~~~

如果要启用 Neo4j 图谱，将 GRAPH_MODE 改为对应模式后再启动：

~~~powershell
docker compose --env-file .env up -d neo4j
~~~

### 3. 安装 AI 服务依赖

~~~powershell
Set-Location apps/ai-service
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
Set-Location ../..
~~~

### 4. 一键启动本地开发栈（Windows）

~~~powershell
.\\scripts\\start-all.ps1 -NoBrowser
~~~

脚本会按顺序检查网络、启动基础设施、启动 AI 服务、启动 Spring Boot 后端和 Vite 前端，并等待健康检查通过。AI 服务需要访问外部模型或搜索服务时，脚本可能请求一次管理员权限；如果只想启动部分服务，可以使用：

~~~powershell
.\\scripts\\start-all.ps1 -SkipInfra
.\\scripts\\start-all.ps1 -SkipBackend
.\\scripts\\start-all.ps1 -SkipFrontend
.\\scripts\\start-all.ps1 -KeepExistingAi
~~~

### 5. 手动启动各服务

适合 Linux、macOS 或需要分别调试服务时使用。

~~~bash
# AI service，注意本地后端默认连接 8003
cd apps/ai-service
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python server.py --host 0.0.0.0 --port 8003

# 另开终端：Java backend
cd apps/backend
mvn spring-boot:run

# 另开终端：Vue frontend
cd apps/web
npm ci
npm run dev
~~~

如果 AI 服务改用 8000，同步修改根目录 .env 中的 SHINKOU_AI_SERVICE_URL，或在启动后端前通过环境变量覆盖它。

### 6. 访问地址

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| Web | http://localhost:5173 | Vite 开发服务器 |
| Backend | http://localhost:8080 | Spring Boot API |
| Backend health | http://localhost:8080/actuator/health | 后端健康检查 |
| AI service | http://localhost:8003/health | 本机 AI 服务健康检查 |
| MinIO API | http://localhost:9000 | 对象存储 API |
| MinIO Console | http://localhost:9001 | 对象存储控制台 |
| Neo4j Browser | http://localhost:7474 | 启用 Neo4j 时可用 |

前端的 /api 请求由 Vite 代理到 http://localhost:8080，并在代理层去掉 /api 前缀；浏览器直接访问后端接口时应以实际后端路由为准。

## 主要运行流程

### 知识资产流程

~~~text
上传文件
  → 校验扩展名、大小和归属
  → 对象存储保存原文件
  → 解析文本 / OCR / 转写
  → 分块并保存元数据
  → 生成 Embedding
  → 写入 PostgreSQL + Milvus
  → 资产状态变为可检索
~~~

资产页面可以查看解析与索引状态、失败原因、文件预览、Chunk、页码和章节，并支持重新索引。默认的 hash Embedding 适合验证流程是否连通；生产或真实检索质量评估应配置实际 Embedding 服务，并保证维度与 Milvus Collection 一致。

### 研究运行流程

~~~text
校验目标
  → 自动选择处理策略
  → 内部知识库检索
  → 证据评估
  → 查询改写 / 图谱检索 / 外部搜索（按策略启用）
  → 组织事实、风险、冲突和缺口
  → 生成带引用报告
  → 反思或审查
  → 保存报告与行动项
~~~

运行策略、最大研究轮数、最大工具调用数、是否允许联网、是否需要工具确认和审查规则均由运行配置控制。网页搜索默认关闭；打开后仍会经过来源验证与工具权限限制。

### 报告与证据规则

- 事实、推断、建议应当区分表达。
- 事实性断言应关联证据 ID。
- 引用需要属于当前工作区、项目和运行。
- 引用的内部 Quote 必须能在对应 Chunk 中找到。
- 证据不足时应展示限制，不用模型臆测补齐。
- 内外部来源冲突时保留冲突并交给审查流程处理。

## 服务与配置参考

### 关键端口

| 组件 | 默认宿主机端口 | 用途 |
| --- | ---: | --- |
| Spring Boot | 8080 | 业务 API |
| 本机 AI service | 8003 | FastAPI AI Runtime |
| Compose AI service | 8000 | 容器映射默认端口 |
| PostgreSQL | 15432 | 业务数据库 |
| Redis | 16379 | 会话、缓存和任务队列 |
| Milvus | 19530 | 向量检索 |
| MinIO | 9000 / 9001 | 文件 API / 控制台 |
| Neo4j | 7687 / 7474 | Bolt / Browser，按需启用 |
| MCP server | 8001 | mcp Compose profile，按需启用 |

### 重要环境变量

详细模板见 [.env.example](.env.example)。常用配置包括：

| 配置 | 作用 |
| --- | --- |
| SHINKOU_AI_SERVICE_URL | Java 后端访问 AI 服务的地址 |
| SHINKOU_AI_INTERNAL_API_KEY / INTERNAL_API_KEY | Java 与 AI 服务的内部认证 |
| SHINKOU_ENCRYPTION_KEY | 用户凭据等敏感配置的加密密钥 |
| DATABASE_URL | AI 服务访问 PostgreSQL 的连接串 |
| MILVUS_URI / AI_MILVUS_URI | AI 服务访问 Milvus 的地址 |
| STORAGE_MODE / MINIO_* | 文件和生成物的存储方式 |
| GRAPH_MODE / NEO4J_* | 图谱存储模式与连接信息 |
| ENABLE_WEB_SEARCH | 是否允许 AI 服务使用网络搜索 |
| MCP_ENABLED | 是否启用 MCP 扩展层 |
| AGENT_TRANSPORT / AGENT_WORKER_URLS | Agent 进程内或远程 Worker 配置 |
| TASK_QUEUE_* | Redis Stream 任务队列配置 |
| FILE_OCR_* / FILE_WHISPER_* | OCR、音视频分析参数 |

启用 MCP：

~~~powershell
docker compose --env-file .env --profile mcp up -d mcp-server
~~~

## 开发命令

### 前端

~~~powershell
Set-Location apps/web
npm ci
npm run dev
npm run type-check
npm run build
npm run preview
~~~

前端使用 Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios、Tailwind CSS、shadcn-vue、Markdown 渲染和 ECharts。

### Java 后端

~~~powershell
Set-Location apps/backend
mvn spring-boot:run
mvn test
mvn package
~~~

后端使用 Spring Boot、Spring Security、Redis、Flyway、MyBatis、PostgreSQL 和 MinIO SDK。数据库迁移位于 apps/backend/src/main/resources/db/migration/，应用启动时由 Flyway 执行。

### AI 服务

~~~powershell
Set-Location apps/ai-service
.\\.venv\\Scripts\\python.exe -m pytest
.\\.venv\\Scripts\\python.exe -m ruff check .
~~~

AI 服务的主要目录如下：

~~~text
api/          FastAPI 路由和内部接口
agents/       Agent 注册、协调、消息契约和运行时
core/         容器、缓存、事件、仓储和任务队列
documents/    文档、图片、音视频解析与文件分析
embeddings/   Embedding Provider 与缓存
models/       模型网关和 Pydantic Schema
rag/          分块索引、向量库、关键词检索和融合
tools/        Web、MCP、图谱、知识和文档生成工具
prompts/      Prompt 注册和搜索 Prompt
workflows/    研究工作流状态与图
test/         Python 测试
~~~

## API 入口

前端主要通过 Spring Boot 访问以下业务域：

~~~text
/auth                         登录、注册、验证码、会话
/workspaces                   工作区、成员、邀请、通知
/workspaces/{id}/projects     项目、规划、设置
/.../assets                   知识资产、内容、Chunk、重新索引
/.../knowledge                检索 Playground 和知识问答
/.../runs                     研究运行、取消、事件和运行详情
/.../agent                    对话 Agent、附件和运行轨迹
/.../reports                  报告与引用
/.../review                   项目审查与审查运行
/.../action-items             行动项
/.../evaluation               评估用例与结果
/.../settings                 模型、工具、联网搜索和安全设置
~~~

AI 服务公开健康检查 GET /health；其余运行时、知识、研究、工具和安全 Harness 接口位于 /internal/*，需要 X-Internal-Api-Key。可直接查看 FastAPI OpenAPI：

~~~text
http://localhost:8003/docs
http://localhost:8003/openapi.json
~~~

完整请求字段和响应示例见 [API 设计](docs/docs/05-api.md)。

## 测试与验证建议

开始调试前先确认三个健康接口：

~~~powershell
Invoke-RestMethod http://localhost:8003/health
Invoke-RestMethod http://localhost:8080/actuator/health
Invoke-WebRequest http://localhost:5173/
~~~

推荐按以下顺序验证：

1. 创建账号、登录并确认刷新后会话仍然有效。
2. 创建工作区和项目。
3. 上传一份 Markdown 或 PDF，等待解析和索引完成。
4. 在知识库 Playground 检查检索结果与来源位置。
5. 创建一次研究运行，观察事件、证据、报告和引用。
6. 在审查页检查引用、数字、冲突和阻断项。
7. 将结论转为行动项并查看评估记录。

测试设计、契约测试、E2E、安全测试和离线评估原则见 [测试设计](docs/docs/13-testing.md)。AI 服务的 Python 测试位于 apps/ai-service/test/，Java 当前包含 BackendApplicationTests。

## 故障排查

### 前端无法访问后端

确认后端监听 8080，并检查后端代理配置。前端代理目标在 apps/web/vite.config.ts 中定义；浏览器 Network 面板应看到 /api 请求而不是跨域直连 AI 服务。

### AI 服务健康但研究失败

先查看 http://localhost:8003/openapi.json 和 AI 服务日志，再确认模型地址、模型名、内部 API Key、Embedding 维度和 Redis / Milvus 状态。健康检查只代表进程可响应，不代表外部模型已经配置正确。

### 资料上传后无法检索

检查资产的解析状态、索引状态和失败原因；再确认 MILVUS_URI、Embedding 维度、项目过滤条件以及当前使用的工作区和项目。首次启动使用 hash Embedding 时，结果只能用于流程验证，不代表真实语义检索质量。

### SSE 没有实时事件

检查运行所属项目权限、后端到 AI 服务的回调地址、代理缓冲和 Redis 任务队列状态。刷新页面后，前端应先读取运行当前状态，再重新连接事件流。

### 文件预览或 OCR 不完整

查看 AI 服务的文件工具状态接口：

~~~powershell
Invoke-RestMethod -Headers @{ "X-Internal-Api-Key" = $env:INTERNAL_API_KEY } http://localhost:8003/internal/files/tools
~~~

Docker 镜像内会安装 Tesseract、Poppler、LibreOffice 和 FFmpeg；本地 Windows 运行优先使用 tools/runtime/ 中的工具。音频转写还需要 faster-whisper 模型可用。

## 文档导航

- [产品定位](docs/product-positioning.md)：目标用户、核心模块、反虚构制度和产品边界。
- [系统架构](docs/docs/02-architecture.md)：服务拆分、数据流和部署关系。
- [数据库设计](docs/docs/04-database.md)：业务表、运行数据、证据、报告和评估模型。
- [RAG 设计](docs/docs/06-rag-design.md)：解析、分块、检索、引用和评估。
- [Agent 工作流](docs/docs/07-agent-workflow.md)：研究图、节点、工具、安全和取消。
- [Reasoning Workflows](docs/docs/22-reasoning-workflows.md)：对话处理策略与运行方式。
- [Agent Workspace API](docs/docs/19-agent-workspace-api.md)：对话工作台接口和事件约定。
- [Agent Task Queue API](docs/docs/20-agent-task-queue-api.md)：异步任务队列和 Worker。
- [安全设计](docs/docs/11-security.md)：认证、租户隔离、文件、SSRF、Prompt Injection 和审计。
- [可观测性与评估](docs/docs/12-observability-evaluation.md)：Trace、指标、评估集和发布门槛。
- [开发与部署](docs/docs/14-development-deployment.md)：环境、迁移、发布和常见问题。
- [生产运维](docs/docs/23-production-operations.md)：运行检查、备份、升级和应急操作。
- [文档清单](docs/MANIFEST.md)：仓库内各专题文档索引。

## 项目边界

Shinkou Insight 的目标是提高调研、分析和审查效率，而不是让模型绕过责任链直接做决定。生产部署前应至少替换默认密码和内部 Key，设置稳定的加密密钥，限制 CORS 来源，启用 HTTPS Cookie，并为 LLM、Embedding、搜索服务和对象存储配置独立凭据。

