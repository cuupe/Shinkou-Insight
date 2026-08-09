# 11. 安全设计

## 1. 认证

目标：

```text
登录成功
→ JWT 包含 jti
→ Redis 保存有效会话
→ HttpOnly Cookie
→ 请求自动携带
→ 过滤器校验签名、过期和 Redis 会话
```

要求：

- `Secure=true` 用于 HTTPS。
- SameSite 默认 Lax 或 Strict。
- 前端不读取 Token。
- 退出同时删除 Redis 会话和 Cookie。
- 支持登录失败计数和临时锁定。

## 2. CSRF 与 CORS

- 写操作不使用 GET。
- CORS 使用明确 Origin，不使用 `*` 配合 credentials。
- 校验 Origin / Referer。
- 跨站部署使用 CSRF Token。
- SSE 路由同样校验会话和资源权限。

## 3. RBAC 与资源归属

每个请求：

```text
认证用户
→ ACTIVE Workspace Member
→ 角色权限
→ Project 属于 Workspace
→ Asset / Run / Report 属于 Project
```

不能只根据前端隐藏按钮实现权限。

## 4. 文件上传安全

- 白名单 MIME 和扩展名。
- 限制大小、页数、解压大小。
- 文件名随机化，原名只作为元数据。
- 存储路径使用 `workspaceId/projectId/assetId`。
- 规范化路径并阻止 `../`。
- 不执行上传文件中的脚本和宏。
- 解析服务使用低权限用户。
- 后续支持病毒扫描时放入异步流程。

## 5. RAG 数据隔离

- Chunk 查询强制租户过滤。
- Evidence 保存租户字段。
- 缓存 Key 包含 workspaceId/projectId。
- Embedding 任务无法指定其他工作区资产。
- 评估数据集不默认跨工作区混合。

## 6. Prompt Injection

威胁：文档或网页试图让模型忽略规则、调用工具或泄露数据。

措施：

```text
资料明确标记为 UNTRUSTED CONTENT
工具权限由代码校验
用户和文档不能修改租户上下文
模型上下文不包含秘钥
网页抓取结果不自动执行
写工具需要白名单或确认
```

## 7. 工具安全

### 7.1 Web Search / Fetch

- 限制协议为 HTTP/HTTPS。
- 阻止 localhost、内网 IP、云元数据地址，防止 SSRF。
- 限制响应大小和重定向次数。
- 设置超时。
- 不下载可执行文件。

### 7.2 Database Tool

MVP 不提供任意 SQL 工具。后续若增加：

- 只读账号。
- 查询模板或 AST 校验。
- 超时、行数和字段限制。
- 禁止系统表和跨租户查询。

### 7.3 Python Tool

MVP 不提供任意代码执行。若后续增加，必须使用隔离沙箱、资源限制和禁网策略。

## 8. 模型和秘钥

- API Key 只通过环境变量或 Secret Manager 注入。
- 数据库只保存 Key 引用或加密密文。
- 日志脱敏 Authorization、Cookie、Key、密码。
- Prompt 和 Trace 中不保存不必要的敏感全文。

## 9. 审计

记录：

```text
登录成功 / 失败
邀请和角色变化
项目和资产创建、删除
索引任务
Run 创建、取消、失败
外部搜索
报告导出
模型、工具、Prompt 配置变化
```

审计日志与 Agent Tool Call 分离：前者记录安全和业务操作，后者记录 AI 执行过程。

## 10. 速率与成本控制

- 用户和工作区级并发限制。
- Run 最大轮数。
- 工具最大调用次数。
- LLM Token 预算。
- Embedding 批次大小。
- Web 搜索配额。

## 11. 安全测试

必须覆盖：

```text
跨工作区 IDOR
Cookie 缺失 / 过期 / 伪造
CSRF
路径穿越
超大文件
恶意 URL 和 SSRF
Prompt Injection
伪造 Citation ID
Run 取消后的继续执行
日志敏感信息泄露
```
