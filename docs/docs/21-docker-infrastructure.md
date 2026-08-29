# Docker 基础设施

前后端继续在宿主机运行，Docker 只管理基础设施：PostgreSQL、Redis、Neo4j 和 MinIO。

## 启动

```powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
```

宿主机端口：

- PostgreSQL：`localhost:15432`
- Redis：`localhost:16379`
- Neo4j Browser：`http://localhost:7474`
- Neo4j Bolt：`bolt://localhost:7687`
- MinIO API：`http://localhost:9000`
- MinIO Console：`http://localhost:9001`

PostgreSQL 和 Redis 使用高位宿主端口，是为了避开开发机上已有的本地服务；容器内部仍使用标准端口。

## 宿主机后端配置

后端默认已经指向上述端口。首次启动后，Flyway 会自动执行 `V1` 到最新版本的迁移，包括全文检索列、查询索引、约束和对象存储键字段。

```powershell
cd apps/backend
mvn spring-boot:run
```

知识库文件和 Agent 附件的二进制内容写入 MinIO 的 `shinkou-files` 桶，PostgreSQL 只保存元数据、文本内容和索引状态。桶由 `minio-init` 首次启动时自动创建，并保持私有访问。

## 停止与数据

```powershell
docker compose stop
docker compose start
```

数据保存在 Docker named volumes 中。不要使用 `docker compose down -v`，除非确认要删除 PostgreSQL、Neo4j、Redis 和 MinIO 的全部数据。
