# Docker 全栈部署

Compose 统一构建 Vue 前端、Java 21 / Spring Boot 后端和 Python 3.11 / FastAPI AI 服务，并编排 PostgreSQL、Redis、Milvus、Neo4j 和 MinIO。

## 构建和启动

宿主机只需 Docker（Linux 容器模式）和 Compose。首次创建配置，已有 `.env` 时保留原文件：

```powershell
Copy-Item .env.example .env
```

在 `.env` 中设置稳定的 `SHINKOU_ENCRYPTION_KEY`，可以用 PowerShell 生成 Base64 编码的 32 字节随机值：

```powershell
$keyBytes = New-Object byte[] 32
$keyGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$keyGenerator.GetBytes($keyBytes)
$keyGenerator.Dispose()
[Convert]::ToBase64String($keyBytes)
```

将输出写入 `.env` 的 `SHINKOU_ENCRYPTION_KEY=`，保存后保持不变，否则已加密的模型凭据无法解密。

```powershell
docker compose --env-file .env up -d --build
docker compose ps
```

单独构建三个应用镜像，不启动容器：

```powershell
docker compose build web backend ai-service
```

镜像名称为 `shinkou-insight/web:local`、`shinkou-insight/backend:local` 和 `shinkou-insight/ai-service:local`；通过 `IMAGE_TAG` 指定版本。Java 使用 Maven 构建后复制可执行 JAR 至 JRE 镜像，Vue 使用 `npm ci` 和包含类型检查的 `npm run build` 构建后复制静态产物至 Nginx，Python 镜像包含 OCR、PDF、LibreOffice、FFmpeg 和语音转写依赖。三个构建上下文均排除本机环境、密钥和构建缓存。

首次构建需要下载基础镜像、语言依赖和系统工具。Python 镜像较大，语音模型在实际使用时下载，并保存在独立缓存卷。

如果 Docker 已配置的镜像站不可用，可在 `.env` 中设置 `BASE_IMAGE_REGISTRY=registry-1.docker.io`，让应用构建直接访问 Docker 官方仓库，再重新构建。此选项只影响三个应用的基础镜像。

Java 构建默认访问 Maven Central。网络受限时可通过 `MAVEN_MIRROR_URL` 指定可达的 Maven 镜像，例如 `https://maven.aliyun.com/repository/public`；此选项只影响构建阶段，Maven 依赖通过 BuildKit 缓存复用。

Python 系统工具默认从 Debian 官方源安装。如果该源连接不稳定，可设置 `DEBIAN_MIRROR_URL=https://repo.huaweicloud.com` 等同时提供 `/debian` 和 `/debian-security` 的镜像。APT 下载与 Python 包下载均通过 BuildKit 缓存复用，APT 自动重试临时网络失败。

## 服务与地址

| 服务 | 默认宿主机地址 | 容器内地址 / 用途 |
| --- | --- | --- |
| Vue / Nginx | `http://localhost` | `web:80` |
| Java backend | `http://localhost:8080` | `backend:8080` |
| Backend health | `http://localhost:8080/actuator/health` | 无需登录的最小健康状态 |
| Python AI | `http://localhost:8000/health` | `ai-service:8000` |
| PostgreSQL | `localhost:15432` | `postgres:5432` |
| Redis | `localhost:16379` | `redis:6379` |
| Milvus | `localhost:19530` | `milvus:19530` |
| Milvus Web UI | `http://localhost:19091/webui/` | `milvus:9091` |
| Neo4j Browser | `http://localhost:7474` | `neo4j:7474` |
| Neo4j Bolt | `bolt://localhost:7687` | `neo4j:7687` |
| MinIO API | `http://localhost:9000` | `minio:9000` |
| MinIO Console | `http://localhost:9001` | `minio:9001` |

`WEB_PORT`、`BACKEND_PORT`、`AI_SERVICE_PORT` 控制应用发布到宿主机的端口。容器间连接始终使用服务名及内部端口；根目录 `.env` 中供本机开发使用的 `SHINKOU_AI_SERVICE_URL`、`DATABASE_URL`、`REDIS_URL` 等本机地址不会覆盖 Compose 显式配置的容器地址。

Nginx 将 `/api/` 去除前缀后转发到 Java，与 Vite 开发代理保持一致，保留会话 Cookie 和 CSRF 请求头。它提供 Vue Router 的页面回退、允许文件上传，并关闭 API 响应缓冲以支持 Agent / Research SSE。后端重新创建后，Nginx 通过 Docker DNS 重新解析服务地址。

Java 的 AI 地址固定为 `http://ai-service:8000`，AI 回调地址为 `http://backend:8080`。两端使用同一个 `INTERNAL_API_KEY`。MinIO 初始化完成、数据库、Redis 和 AI 服务健康后才启动 Java，Java 健康后才启动前端。Flyway 随 Java 启动自动执行数据库迁移。

模型地址、模型名称、凭据及网页搜索配置在 Web 界面按用户设置。容器中的 `localhost` 指向当前容器；访问宿主机模型服务时，Docker Desktop 可使用 `http://host.docker.internal:<端口>`。模型服务需要监听可由 Docker 访问的地址；Linux Docker Engine 可按环境配置 host-gateway 或使用可达的主机地址。

## 本机调试与可选 MCP

本机调试时仅启动依赖，避免启动容器应用占用本机开发端口：

```powershell
docker compose up -d postgres redis milvus minio minio-init
# 如需 Neo4j
docker compose up -d neo4j
```

已有容器应用运行时，先执行 `docker compose stop web backend ai-service`，再运行 `scripts/start-all.ps1`。本机 AI 默认端口仍为 8003。

可选 MCP 服务复用 AI 镜像，以独立进程启动：

```powershell
# 先在 .env 设置 MCP_ENABLED=true
docker compose --profile mcp up -d --build
```

## 日志、更新与数据

```powershell
docker compose logs --tail 100 -f web backend ai-service
docker compose up -d --build web backend ai-service
docker compose stop
docker compose start
```

数据保存在命名卷中。`shinkou-ai-data` 保存 Python 本地文件模式的数据，`shinkou-ai-model-cache` 保存语音模型缓存；数据库、索引及对象存储沿用原有卷。自定义工具目录以只读方式挂载，修改工具文件后重启 AI 服务加载。

MinIO 的 `shinkou-files` 桶由 `minio-init` 创建且保持私有。Python 和 Java 均使用 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 连接同一个 MinIO 服务。不要使用 `docker compose down -v`，除非确认要删除数据库、索引、文件及模型缓存。

## HTTPS 部署配置

默认配置用于本机 HTTP。部署到域名时，在外层 HTTPS 反向代理后配置 `SHINKOU_ALLOWED_ORIGINS=https://你的域名`、`SHINKOU_COOKIE_SECURE=true`、`SHINKOU_ENVIRONMENT=production` 和 `APP_ENV=production`，并设置非默认的基础设施密码、`INTERNAL_API_KEY` 和稳定的加密密钥。生产模式保留应用现有的启动配置校验。

外层代理同样需要允许上传并关闭 SSE 缓冲。对外发布 Web 入口即可；按部署网络限制数据库、Redis、对象存储和应用调试端口的访问。

参考：[Compose 启动顺序与健康检查](https://docs.docker.com/compose/how-tos/startup-order/)、[Docker 多阶段构建](https://docs.docker.com/build/building/multi-stage/)、[Nginx 代理与缓冲](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)。
