# 14. 开发与部署说明

## 1. 推荐环境

```text
Node.js 20+
Java 21
Maven 3.9+
Python 3.11+
PostgreSQL 16
Milvus 2.4.x（Standalone）
Redis 7
Docker / Docker Compose
```

实际项目应锁定版本并维护升级记录。

## 2. 仓库结构

```text
Shinkou/
├─ Shinkou-web/
├─ Shinkou-backend/
├─ Shinkou-ai/
├─ docs/
├─ migrations/
├─ evaluation/
├─ training/
├─ docker-compose.yml
├─ .env.example
└─ README.md
```

## 3. Java 模块结构

```text
com.cuupe.shinkou
├─ common
├─ config
├─ security
├─ auth
├─ workspace
├─ project
├─ knowledge
├─ research
├─ report
├─ actionitem
├─ audit
└─ aiconfig
```

按领域组织，不再把所有 Controller、DTO、Service 放在全局大目录。

## 4. Python 结构

```text
app/
├─ api
├─ core
├─ models
├─ prompts
├─ rag
├─ tools
├─ workflows
├─ nodes
├─ schemas
├─ repositories
├─ observability
└─ main.py
```

## 5. 环境变量

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
REDIS_HOST
REDIS_PORT
APP_JWT_SECRET
COOKIE_SECURE
COOKIE_SAME_SITE
AI_SERVICE_BASE_URL
INTERNAL_SERVICE_TOKEN
FILE_STORAGE_ROOT
MAX_UPLOAD_SIZE_MB
# LLM provider endpoint, model id and API keys are configured in the web UI.
LLM_MODE
EMBEDDING_MODEL
EMBEDDING_DIMENSION
RERANKER_MODEL
# Web search API keys are configured in project settings.
OTEL_EXPORTER_ENDPOINT
MILVUS_URI
MILVUS_TOKEN
MILVUS_DB_NAME
MILVUS_COLLECTION_NAME
```

`.env.example` 不包含真实密钥。

## 6. 本地启动

```bash
docker compose up postgres milvus-etcd milvus-minio milvus redis -d

cd Shinkou-backend
mvn spring-boot:run

cd Shinkou-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd Shinkou-web
npm install
npm run dev
```

Windows 使用对应 PowerShell 虚拟环境命令。

## 7. 数据库迁移

- 启动前自动校验 migration。
- 生产禁止修改已发布 migration。
- 向量维度变化使用新 migration 和重建任务。
- 初始化演示数据单独放 `seed/`，不混入 Schema migration。

## 8. 代码规范

### Java

- Controller 只做协议转换和权限入口。
- Service 处理业务事务。
- DTO 与 Entity 分离。
- 所有外部错误映射为业务错误码。

### Python

- Pydantic 定义外部边界。
- Node 不直接拼 SQL。
- Prompt 与代码分离。
- Provider 接口隔离模型厂商。
- 类型检查和 lint。

### Frontend

- API 按业务模块封装。
- 服务器状态使用 Query。
- 组件不直接访问 Cookie/Token。
- 页面必须包含 loading、empty、error。

## 9. Docker Compose

服务：

```text
frontend
backend
ai-service
postgres
milvus-etcd
milvus-minio
milvus
redis
```

挂载卷：

```text
postgres-data
redis-data（可选）
asset-storage
model-adapters（可选）
```

## 10. 生产演示部署

个人项目建议：

- 单机 Docker Compose 或轻量容器平台。
- Nginx / Caddy 统一 HTTPS 和域名。
- 前端 `/api` 代理 Spring Boot。
- Python 只在内部网络暴露。
- 免费或低成本模型配置需要有降级提示。

## 11. 发布流程

```text
feature branch
→ PR tests
→ merge main
→ build images
→ migration check
→ deploy staging/demo
→ smoke test
→ tag release
```

## 12. 故障排查

### Cookie 认证失败

检查：Set-Cookie、SameSite、Secure、Origin、credentials、Redis 会话。

### 索引失败

检查：文件类型、Parser 日志、Embedding Key、维度、数据库扩展。

### 检索为空

检查：asset 状态、workspace/project filter、向量维度、查询语种。

### SSE 无事件

检查：会话权限、代理缓冲、连接超时、事件发布和心跳。

### Run 卡住

检查：当前节点、工具超时、取消标记、Checkpoint 和数据库 Step 状态。
