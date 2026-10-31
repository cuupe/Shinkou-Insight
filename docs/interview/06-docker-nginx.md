# 06. Docker、Compose、镜像、网络与 Nginx

基准：根目录 docker-compose.yml，apps/web、apps/backend、apps/ai-service 下的 Dockerfile 与 .dockerignore，以及 apps/web/nginx.conf。本章逐个对应仓库服务，不把不存在的 Kubernetes、Service Mesh 或集群部署写成已完成。

## 1. 先说清 Docker 解决什么

把应用和依赖封装到可复用镜像，减少 Node/Java/Python/系统工具版本差异，利用 Compose 把多服务、网络、卷和启动条件描述为配置。它不会自动修复错误配置、建立高可用、备份数据或保证模型服务可用。

### 1.1 镜像、容器、仓库

- 镜像是分层只读文件系统及运行元数据；tag 是可移动名称，digest 标识具体内容。
- 容器是从镜像启动的进程及隔离环境，并有可写层。
- Registry 保存和分发镜像，构建缓存与运行数据不属于同一概念。
- Dockerfile 描述如何生成镜像；Compose 描述如何组合运行服务。

### 1.2 与虚拟机的区别

Linux 容器通常共享宿主机 Linux 内核，用 namespaces 隔离进程/网络等视图，用 cgroups 管资源，使用分层文件系统共享镜像层。Windows Docker Desktop 的 Linux 容器还依赖其 Linux 运行环境，不能说 Linux 容器直接共享 Windows 内核。

隔离不等于绝对安全。root、挂载宿主目录、额外 capability、宽松 seccomp 和容器逃逸风险都影响边界。当前 Milvus 配置 seccomp:unconfined，需要按所用版本和部署要求评估，不应顺便把所有服务改成 privileged。

## 2. Compose 的 12 个服务逐项清单

| Service | 镜像/构建来源 | 容器端口 → 默认宿主机端口 | 数据/职责 |
| --- | --- | --- | --- |
| web | Node 24 构建，Nginx stable-alpine 运行 | 80 → 80 | Vue 静态资源、/api 代理 |
| backend | Maven 3.9 + JDK 21 构建，JRE 21 运行 | 8080 → 8080 | Java 业务 API |
| ai-service | Python 3.11-slim + 系统解析工具 | 8000 → 8000 | FastAPI、RAG、Agent、文件 |
| mcp-server | 复用 AI 镜像，执行 mcp_server.py | 8001 → 8001 | 可选 MCP 工具接口；mcp profile |
| postgres | postgres:16-alpine | 5432 → 15432 | 业务库与 Chunk |
| redis | redis:7.4-alpine | 6379 → 16379 | 验证码/限流、AI 缓存/队列/快照 |
| milvus | milvusdb/milvus:v2.4.23 | 19530 → 19530；9091 → 19091 | standalone 向量引擎 |
| milvus-etcd | quay.io/coreos/etcd:v3.5.5 | 内部 2379，未发布 | Milvus 元数据依赖 |
| milvus-minio | MinIO RELEASE.2025-04-22T22-12-26Z | 内部 9000/9001，未发布 | Milvus 专用对象数据 |
| minio | 同上 MinIO 版本 | 9000 → 9000；9001 → 9001 | 业务原文件与生成物 |
| minio-init | minio/mc:RELEASE.2025-03-12T17-29-24Z | 无服务端口 | 创建私有 bucket 的一次性任务 |
| neo4j | neo4j:5.26-community | 7687 → 7687；7474 → 7474 | 可选图数据库后端 |

版本是仓库声明，不是「当前所有技术的最新版本」。stable、alpine、主版本 tag 仍可能变化，严格复现需保存应用和基础镜像 digest。

### 默认启动的细节

MCP 通过 profile 选择；Neo4j 没有 profile，因此不指定服务的完整 compose up 可以启动 Neo4j，虽然 GRAPH_MODE 默认 memory。minio-init 成功退出是正常状态。默认服务清单和历史 QA 的「9 个长期运行容器」不同，后者未包含可选 Neo4j。

## 3. 启动依赖图

~~~mermaid
flowchart TD
    E[etcd 健康] --> M[Milvus 健康]
    O[Milvus MinIO 健康] --> M
    P[PostgreSQL 健康] --> A[AI service 健康]
    R[Redis 健康] --> A
    B[业务 MinIO 健康] --> I[minio-init 成功退出]
    M --> A
    B --> A
    I --> A
    A --> J[Backend 健康]
    P --> J
    R --> J
    I --> J
    J --> W[Web]
~~~

当前依赖能避免大部分「进程刚启动但服务未准备好」的问题。service_healthy 等待健康探针，service_completed_successfully 适合初始化任务。普通依赖启动顺序本身不等于可用性，见 [Compose 启动顺序说明](https://docs.docker.com/compose/how-tos/startup-order/)。

依赖在运行一小时后故障，Compose 不会因此自动把整个应用链路恢复到一致状态；业务客户端需要超时、重连和降级。unhealthy 也不等于进程退出，restart:unless-stopped 不是完整的依赖故障编排器。

## 4. 前端镜像的两阶段构建

### 4.1 构建阶段

以 node:24-alpine 为基础，复制 package.json 与 package-lock.json，npm ci 安装，再复制源码并 npm run build。先复制依赖清单，让只改源码时可以复用依赖层。

npm ci 按 lockfile 安装，适合 CI；npm install 可能更新依赖解析结果。构建命令同时类型检查与生成 dist，Vite 本身转换 TypeScript 不等于做完整类型检查。

### 4.2 运行阶段

仅把 dist 和 nginx.conf 放入 nginx 镜像，不需要把 Node 和源码放到运行环境。好处是减小攻击面和体积；最终页面中的变量已在构建期固化，不能假设运行容器时任意环境变量会自动修改前端脚本。

当前前端固定请求相对 /api，减少不同部署域名的构建配置差异。

## 5. Java 镜像构建

第一阶段使用 Maven/JDK 21，先 dependency:go-offline，再复制 src 并 package。BuildKit 的 cache mount 复用 /root/.m2，减少重复下载；docker-settings.xml 与 MAVEN_MIRROR_URL 控制镜像源。

第二阶段仅包含 JRE、curl 和应用 jar，以 UID 10001 的 shinkou 用户运行。ENTRYPOINT 的 exec 数组形式使 Java 成为主进程，有利于接收停止信号。

关键边界：Dockerfile 的 package 带 -DskipTests，因此镜像构建成功不能替代 mvn test。数据库迁移在应用启动时执行，不是在镜像构建期对生产库执行。

当前没有固定 JVM 堆大小、容器 CPU/内存限制或完整优雅下线编排；要根据真实负载设预算，不能直接把容器内存全部分给堆。

## 6. Python 镜像和系统依赖

保持 /app/apps/ai-service 的目录结构，因为配置代码会向上解析项目根。设置 PYTHONUNBUFFERED 让日志及时输出，PYTHONDONTWRITEBYTECODE 减少 pyc 写入，PYTHONPATH 提供模块路径，HF_HOME 指向持久化模型缓存。

安装 LibreOffice、Poppler、Tesseract 中英语言包、FFmpeg。它们体积较大，但服务需要实际进行 OCR、Office 和音视频处理。requirements 含范围约束，当前没有完全固定每个 Python 包版本，因此不能声称构建在任意时间完全逐字节可复现。

pip 与 apt 使用 BuildKit 缓存挂载；设置普通用户，并创建可写的 /app/data 与 /app/model-cache。最后用 uvicorn main:app 单进程启动，未设置多个 Uvicorn worker。

增加 worker 会让 EventBus、热快照、进程内去重、工具 semaphore 和角色队列各自复制，必须先解决共享状态与认领，不宜只为提高 CPU 使用率直接增加 worker 数。

## 7. .dockerignore、构建上下文和秘密

三个上下文都是各自 app 目录，.dockerignore 排除 .env、node_modules、target、.venv、日志、测试等。目的是减少构建传输和意外复制本地文件。

构建参数适合镜像站和非秘密配置，不适合长期凭据；凭据可能进入镜像层、构建日志或元数据。运行 environment 也不是秘密保险箱，能 inspect 容器的用户可能读取它。生产可评估秘密管理和只读文件注入。

AI 的 custom_tools 以宿主目录只读挂载。只读意味着容器不能修改该目录，不意味着工具代码无害；Python 插件执行依然具有 AI 服务进程的权限。

## 8. 容器网络与地址

### 8.1 三个网络视角

| 调用方 | 目标 PostgreSQL | 目标 AI | 解释 |
| --- | --- | --- | --- |
| 本机开发进程 | localhost:15432 | localhost:8003，按本地脚本默认 | 走宿主机映射或本地监听 |
| backend 容器 | postgres:5432 | ai-service:8000 | 走 Compose 服务名与容器端口 |
| 浏览器 | 不应直连数据库 | 经 /api 访问 Java | 浏览器不认识内部服务名 |

容器内 localhost 指该容器自身。把本机开发 DATABASE_URL 原封不动用于容器，往往会连到不存在的本容器数据库。

### 8.2 服务发现与端口映射

用户定义网络中，服务名可通过 Docker DNS 解析。ports 将容器端口发布到宿主机；同网络容器通信不需要都发布端口。EXPOSE 是镜像说明，不等于实际发布。

当前 shinkou-infra 网络未设 internal:true，服务可能仍具出站能力；网络名有 infra 不代表网络被严格隔离。上线可仅发布边缘入口和必要管理端口，并区分前端、业务、数据库网络。

### 8.3 Nginx 动态 DNS

upstream 配置 Docker DNS 127.0.0.11、valid=10s 以及 server backend:8080 resolve，目的是 Backend 重建 IP 改变时重新解析。容器服务名通常稳定，IP 不应写死。

要验证所用 Nginx 版本是否支持这些配置，nginx -t 是配置有效性的证据；DNS 解析正确还需实际请求验证。

## 9. 存储：可写层、volume 与 bind mount

| 类型 | 特点 | 本项目例子 |
| --- | --- | --- |
| 容器可写层 | 与容器生命周期关联，不宜当数据库持久化 | 临时运行文件 |
| named volume | Docker 管理，容器重建仍可挂载 | postgres-data、redis-data、minio-data |
| bind mount | 直接映射宿主路径，受宿主权限/路径影响 | custom_tools:ro |
| 镜像只读层 | 发布内容，适合应用与静态资源 | jar、dist、Python 源码 |

卷清单：AI data/model-cache、PostgreSQL data、Redis data、Milvus data/etcd data/专用 MinIO data、业务 MinIO data，以及 Neo4j data/logs/import/plugins。

### 显式 name 的隔离陷阱

Compose 为多个卷和网络指定固定 name。更换 -p 项目名不会自动把这些显式名称加前缀。要启动独立测试环境，应覆盖卷/网络名及宿主端口，并确认最终解析配置，避免 QA 操作现有开发数据。

### 停止、重建与删除

stop 只停止容器；up 可按镜像/配置重建；down 移除本项目容器和默认网络处理，但通常保留命名卷；带 -v 的删除会涉及数据卷，不能把它作为常规排障第一步。重建应用镜像不应要求清空数据库。

volume 是持久化位置，不是备份。备份需要跨主机/独立介质和可验证恢复过程。

## 10. 健康检查逐个解释

| 服务 | 当前探针 | 能证明什么 / 不能证明什么 |
| --- | --- | --- |
| web | GET /healthz | Nginx 可响应；不证明 Java/模型业务成功 |
| backend | /actuator/health | Actuator 当前健康定义；不等于所有外部能力都已测试 |
| ai-service | /health | AI 进程能处理健康请求；不证明模型 Key 和语料质量 |
| postgres | pg_isready | 可接受连接状态；不验证所有迁移/权限/业务查询 |
| redis | 带认证 ping | Redis 能应答；不证明 AOF 恢复和队列不丢 |
| etcd | etcdctl endpoint health | 端点健康；不构成多节点容错证明 |
| Milvus MinIO | /minio/health/live | 对象服务存活；不验证所有历史索引对象 |
| Milvus | :9091/healthz | Milvus 健康；检索质量另测 |
| 业务 MinIO | mc ready local | 当前就绪状态；对象读写需另测 |
| Neo4j | cypher-shell RETURN 1 | 能认证并执行简单查询；不证明图谱完整 |
| MCP | 禁用继承探针 | 复用镜像的 8000 探针对 MCP 8001 不适用；应补专属验证 |
| minio-init | 退出码为 0 | 初始化命令成功完成，无需长期运行 |

start_period 给初始慢启动留时间；interval/timeout/retries 决定失败判定节奏。增加重试次数不能修复错误密码或端口。

## 11. Nginx 配置逐项拆解

### 11.1 静态站点与 SPA 回退

root 指向 dist，index index.html；try_files 先找真实文件，找不到时返回 index.html。API location 要更明确匹配，避免业务 API 404 被错误变成 HTML 200。

### 11.2 /api 改写

location /api/ 配合 proxy_pass 到 upstream 的根路径，会去掉匹配的 /api/ 部分。精确 /api 返回 308 到 /api/；308 保留请求方法。尾斜杠语义可查 [Nginx proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass)。

### 11.3 Header

Host、X-Real-IP、X-Forwarded-For、X-Forwarded-Proto 传递原请求信息。后端必须只信任来自受控代理的转发信息，不能直接信任客户端自填的 Header。

当前限流器使用 request.getRemoteAddr()，若没有正确配置可信代理地址还原，可能把所有请求识别成 Nginx 的 IP；反之无条件信任 X-Forwarded-For 又可被伪造。应通过实际部署请求验证。

### 11.4 SSE 与超时

HTTP/1.1、清理 Connection 头、关闭 response buffering 与 cache、较长 read timeout 支持持续读取上游事件；send timeout 针对向上游发送请求。proxy_read_timeout 约束读取间隔，不是业务任务总预算。SSE 应避免缓存，必要心跳也需应用层配合。

### 11.5 上传上限

Nginx client_max_body_size=257m；Spring multipart max-file-size/max-request-size=256MB；应用拒绝 >=256 MiB。多层上限需要协调：额外 1 MiB 只在代理层留头部空间，Spring 总请求上限仍可能使接近单文件上限的 multipart 提前失败。

大文件上传还涉及代理请求缓冲、临时磁盘、Java 内存和对象存储流式写入，不能只调大大小限制。

## 12. 环境变量与配置优先级

根 .env/--env-file 用于 Compose 插值；service.environment 决定实际传入容器的变量。文件里写了一项不意味着每个容器都自动收到它。backend 又有 Spring 的配置导入，AI 有自己的 Settings，这些属于不同读取机制。

容器配置强制服务名地址，例如 backend→ai-service:8000；本地 .env 的 localhost:8003 不应覆盖进容器内部连接。特殊字符的数据库密码还涉及 URL 编码，不能仅靠字符串拼接认为任何密码都能工作。

SHINKOU_ENCRYPTION_KEY 是持久密文的解密条件，重新部署必须保留；IMAGE_TAG 是版本标签，仍需要避免覆盖已发布 tag 导致无法回滚。

## 13. 常用验证命令与含义

以下以仓库根目录执行为例，不包含清空数据命令。

~~~powershell
docker compose config --quiet
docker compose --profile mcp config --quiet
docker compose ps
docker compose logs --tail 100 backend
docker compose logs --tail 100 ai-service
docker compose logs --tail 100 milvus
docker compose exec web nginx -t
docker stats --no-stream
docker compose images
Invoke-RestMethod http://localhost:8080/actuator/health
Invoke-RestMethod http://localhost:8000/health
~~~

不要无筛选地把 docker compose config 或 docker inspect 全量输出贴到公开问题中，它们可能包含运行凭据。排障需要目标字段、时间和服务，避免日志中泄露个人文档。

## 14. 构建失败与运行失败怎么分

| 现象 | 第一检查点 | 常见原因 |
| --- | --- | --- |
| 拉不到基础镜像 | Registry DNS/TLS/代理 | 镜像站失效、网络策略 |
| Maven 下载失败 | 镜像源、缓存、依赖坐标 | 远端仓库或代理 |
| apt/pip 超时 | 系统包源、DNS、架构 | 构建网络与依赖未固定 |
| Backend 不健康 | 应用日志、Flyway、DB、加密 Key | 默认生产密码校验、迁移失败 |
| AI 不健康 | Milvus/PG/Redis 初始化 | 模型配置、权限、依赖连接 |
| 502 | Nginx 上游 DNS/端口/健康 | 服务重建、连接拒绝、路径错误 |
| 数据消失 | 实际挂载卷、项目配置 | 启动到新卷、误删卷、错误路径 |
| 无法下载 Whisper | HF_HOME、网络、磁盘 | 模型缓存无权写、下载源不可达 |

## 15. 面试时讲部署完成的证据

按配置校验 → 镜像构建 → 单元/集成测试 → 服务健康 → 服务间认证 → 文件读写 → 登录/权限 → 索引/检索 → SSE/取消 → 真实模型报告 → 备份恢复逐级说明。

现有验收记录证明镜像和基础连通，未证明真实模型端到端。当前 Compose 没有主从数据库、Redis Sentinel、Milvus 分布式、集中日志、TLS、完善资源限额和自动发布流水线；这些应作为上线演进方案讲。

## 16. 官方补充：配置插值与容器变量是两次决策

Compose 首先解析 YAML 中的变量，再根据 environment/env_file/镜像 ENV 等决定容器内值。宿主环境和 .env 不是自动注入渠道；CLI compose run -e 是另一个明确覆盖入口，不能把该参数套到所有 up 命令。见 [Compose 环境变量优先级](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/)。

~~~yaml
services:
  demo:
    environment:
      APP_ENV: ${APP_ENV:-local}
      INTERNAL_HOST: backend
~~~

APP_ENV 会取插值来源或默认值；INTERNAL_HOST 在这里是明确常量，不因 .env 有同名项就自动改写。项目中的 postgres:5432、ai-service:8000 因此能与本机开发地址分开。排查步骤应是：确认输入来源 → 看脱敏后的解析值 → 看目标服务实际收到的值。

构建私有依赖时，可用 BuildKit secret mount 暂时提供凭据；ARG/ENV 可能进入镜像或构建元数据，不能当秘密通道。secret mount 也不能阻止构建脚本主动把值复制/打印出去。见 [Docker Build secrets](https://docs.docker.com/build/building/secrets/)。当前镜像源参数不是凭据，本项目也不能据此声称已接入完整秘密管理。

## 17. 三种「自动恢复」和两种超时

| 机制 | 什么时候生效 | 不提供什么 |
| --- | --- | --- |
| depends_on condition | Compose 启动依赖的时机 | 运行期全链路自动协调 |
| Docker restart policy | 按策略处理容器进程退出等事件 | 单凭 unhealthy 就重建健康业务 |
| 应用客户端重试/重连 | 具体调用或连接失败 | 跨存储事务和业务幂等 |

启动条件依据 [Compose 启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)，运行策略依据 [Docker 容器运行说明](https://docs.docker.com/engine/containers/run/)。当前应用仍要自行处理缓存/数据库连接恢复，restart:unless-stopped 不会检查报告是否正确生成。

proxy_read_timeout 限制相邻两次读取上游响应之间的等待，不限制整条响应的总时长；proxy_send_timeout 针对向上游发送请求的写入间隔，不是「向浏览器发 SSE 的总时长」。项目业务预算由 Runtime 另管。参见 [Nginx proxy 模块](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)。

由此可设计两个测试：长时间持续发心跳的流可能活过 read_timeout 的数值；进程活着但迟迟没有任何响应则会超时。心跳只证明连接有活动，不证明研究有有效进展。

## 18. Nginx 动态解析存在版本条件

upstream 中 resolver、server 的 resolve 等配置在开源版本的可用性有历史差异，相关能力在 1.27.3 附近发生变化。当前使用浮动 stable-alpine，搬到旧镜像时应先核对 nginx -v 和 nginx -t。依据 [Nginx upstream 模块](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)。

配置测试成功还要验证 backend 容器重建后地址变化，现有连接如何结束、新请求何时能重新解析。单次首页返回 200 不能覆盖该过程。
