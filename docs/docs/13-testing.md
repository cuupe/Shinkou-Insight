# 13. 测试设计

## 1. 测试分层

```text
单元测试
→ 组件 / Service 测试
→ 集成测试
→ 契约测试
→ E2E
→ RAG / Prompt 离线评估
→ 安全测试
```

## 2. 前端测试

建议：Vitest + Vue Test Utils + Playwright。

覆盖：

- Auth Store 恢复登录态。
- 路由守卫。
- 工作区切换缓存清理。
- 上传表单。
- SSE 事件去重、重连和完成。
- Citation Drawer。
- Run 错误和取消交互。

## 3. Java 后端测试

建议：JUnit、Spring Boot Test、Testcontainers。

### 3.1 认证

```text
登录成功 / 失败
未激活账号
失败锁定
Cookie 签发
Cookie 认证
退出清 Cookie 和 Redis
```

### 3.2 权限

```text
非成员访问工作区
跨工作区项目 ID
MEMBER 调用管理员接口
已归档项目写操作
```

### 3.3 文件

```text
非法扩展名
超大文件
路径穿越文件名
重复 checksum
删除资产级联清理
```

### 3.4 Research

```text
创建 Run 幂等
取消
状态流转
重复完成回调
非法 Citation
```

## 4. Python AI 测试

建议：pytest。

覆盖：

- Parser 输出。
- Chunk 边界。
- Embedding Provider mock。
- Hybrid Fusion。
- Prompt 渲染。
- Pydantic Schema。
- LangGraph Router。
- 最大轮数。
- Cancel Flag。
- Tool timeout。

LLM 单元测试使用 Fake Model，不在普通 CI 中调用付费模型。

## 5. 契约测试

Java 和 Python 对以下 DTO 建立契约：

```text
IndexAssetRequest
KnowledgeSearchRequest / Response
ExecuteRunRequest
RunEvent
FinalReportPayload
```

可以通过共享 OpenAPI Schema 或 JSON Schema 测试。

## 6. PostgreSQL + Milvus 集成测试

使用 PostgreSQL 和 Milvus Testcontainer/Compose 依赖，验证：

- Milvus 向量写入和相似度召回。
- 租户过滤。
- 全文检索。
- Hybrid 候选合并。
- 删除资产后 Chunk 不可检索。

## 7. E2E 场景

### 场景 A：普通 RAG

```text
激活账号
→ 创建项目
→ 上传资料
→ 等待索引
→ 检索问题
→ 查看引用
```

### 场景 B：Agent 调研

```text
创建 Run
→ 观察 SSE
→ 证据加入
→ 报告完成
→ 打开 Citation
→ 接受行动项
```

### 场景 C：失败恢复

```text
模拟模型失败
→ Run FAILED
→ 查看错误
→ 重试
→ 完成
```

### 场景 D：权限

两个工作区使用相同项目 ID 测试越权。

## 8. AI 质量测试

普通测试断言结构和边界，不断言模型全文完全一致。

可断言：

```text
JSON 合法
Evidence ID 真实
禁止事实未出现
资料不足时 shouldRefuse
目标 Chunk 位于 Top K
```

## 9. 安全测试

参见安全文档，必须自动化至少：

- IDOR。
- 路径穿越。
- SSRF URL 过滤。
- Prompt Injection 工具越权。
- Citation 伪造。

## 10. CI

Pull Request：

```text
frontend lint + unit + build
backend unit + integration
ai-service unit
schema / contract validation
migration validation
```

夜间或手动：

```text
付费模型评估
完整 RAG 数据集
E2E
安全扫描
```
