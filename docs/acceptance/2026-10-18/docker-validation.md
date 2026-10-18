# Docker 全栈打包验证

日期：2026-10-18（Asia/Shanghai）。

## 构建产物

三个镜像均已在本机实际构建成功：

| 镜像 | 镜像标识（SHA-256 前缀） |
| --- | --- |
| `shinkou-insight/web:local` | `7b983dc3cc2b` |
| `shinkou-insight/backend:local` | `909dd25031e2` |
| `shinkou-insight/ai-service:local` | `d13eeef02f3a` |

本机原有 Docker 镜像站不可用，验证时通过官方仓库预拉取基础镜像；Maven 使用 Aliyun 镜像，Python 系统包使用 Huawei Debian 镜像。为绕过本机构建网络的 DNS 故障，本次命令临时使用地址映射；源文件中没有固定 IP。可选镜像源参数及标准构建命令见 [部署说明](../../docs/21-docker-infrastructure.md)。

## 自动测试

| 检查 | 结果 |
| --- | --- |
| Vue `npm test` | 49 项通过 |
| Vue `npm run build` | 类型检查及正式构建通过；存在大于 500 kB 的分块提示 |
| Python `pytest -q` | 339 项通过；7 项因未设置 `TEST_POSTGRES_URL` 跳过 |
| Java `mvn clean test` | 61 项通过；2 项需显式启用的数据库集成测试跳过 |
| Compose 默认及 MCP profile 配置校验 | 通过 |
| 镜像内 `nginx -t` | 通过 |
| Git whitespace 检查 | 通过 |

## 隔离运行验证

使用独立的 `shinkou-insight-docker-qa` 项目、`shinkou-docker-qa` 网络、全新测试数据卷及 18080 / 18081 / 18000 端口。未使用现有开发数据库。`minio-init` 正常完成，Vue、Java、Python、PostgreSQL、Redis、Milvus、etcd 及两个 MinIO 共 9 个运行容器全部健康。

- 首页、`/healthz` 及 Vue 深层路由返回 200。
- `/api/actuator/health` 正确去除 API 前缀，返回 `UP`。
- `/api/auth/csrf` 返回 200 并透传 Cookie。
- 未登录的 `/api/auth/me`、`/api/actuator/env` 返回 401。
- Java 通过容器服务名及内部 API Key 成功访问 AI；AI 可访问 Java 回调主机的健康接口。
- AI 使用 Redis 缓存、Redis Streams 队列（8 个工作协程）及 Redis 持久化运行记录。
- 文件工具状态接口确认 Tesseract、Poppler、LibreOffice、FFmpeg、FFprobe 和 Whisper 依赖可用。
- AI 普通用户可写数据卷和模型缓存卷；MinIO 文件写入、读取与删除通过。

测试使用 `LLM_MODE=mock`，未调用真实外部模型或下载语音模型执行转写。SSE 的无缓冲代理配置已通过 Nginx 配置检查，本次未执行真实模型驱动的完整研究任务。

验证结束后移除该临时项目的容器、网络和测试卷，保留三个应用镜像及构建缓存。
