# Java 后端认证安全加固

本次加固覆盖注册、登录、短信验证码、密码找回、会话和生产配置边界。

## 已启用的控制

- 新注册、找回密码和修改密码要求 12 至 72 位密码，并要求四类字符中的至少三类；BCrypt 工作因子提升到 12，旧的低成本 BCrypt 哈希会在成功登录后自动升级。
- 登录失败采用 IP + 账号维度的 Redis 原子计数；同时限制单 IP 登录请求，避免单个攻击者直接锁死整个账号。
- 短信申请现在是 POST，匿名注册/登录/找回必须先通过图片验证码；按 IP、手机号和发送冷却时间限流。
- 短信验证码使用 Redis Lua 脚本校验并删除，成功后只能消费一次；图片验证码同样是原子一次性消费。
- 登录成功前轮换 Session ID，限制每个账号的活动会话数量；修改/找回密码后使其他会话失效。
- CSRF 仍然对所有状态变更请求生效；会话 Cookie 使用 HttpOnly、SameSite=Lax，生产环境强制 Secure。
- 添加 frame-deny、MIME sniffing 防护和严格 Referrer-Policy；认证响应不应被缓存。
- 认证失败只返回统一错误，审计日志只保存脱敏手机号、请求来源、方式和失败原因，不保存密码、验证码或 Token。
- 生产配置文件不再允许使用默认数据库、Redis、内部 API、对象存储、图数据库和加密密钥；`SPRING_PROFILES_ACTIVE=prod` 时必须显式提供环境变量。

## 生产部署要求

至少设置：`SHINKOU_ENVIRONMENT=production`（或启用 `prod` profile）、`SHINKOU_COOKIE_SECURE=true`、`SHINKOU_ENCRYPTION_KEY`（32 字节 Base64）、`SHINKOU_AI_INTERNAL_API_KEY`（随机高熵值）、数据库/Redis/MinIO/Neo4j 凭据以及精确的 `SHINKOU_ALLOWED_ORIGINS`。

反向代理必须把真实客户端地址传给应用服务器；应用不会信任来自浏览器的 `X-Forwarded-For`，避免攻击者伪造来源绕过限流。

## 后续运营项

生产环境应接入真实短信供应商、集中式告警和凭据轮换；Redis、数据库和日志平台需要使用 TLS/访问控制，并定期执行认证接口的黑盒安全测试。
