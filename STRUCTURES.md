shinkou-insight/
├─ apps/
│  ├─ web/                         # Vue 3 前端
│  ├─ backend/                     # Spring Boot 业务后端
│  └─ ai-service/                  # FastAPI AI Runtime
│
├─ contracts/                      # 跨服务接口契约
│  ├─ openapi/
│  ├─ events/
│  └─ schemas/
│
├─ infra/                          # 基础设施和部署
│  ├─ docker/
│  ├─ compose/
│  ├─ nginx/
│  ├─ postgres/
│  ├─ observability/
│  └─ k8s/                         # 后期可选
│
├─ docs/                           # 产品与技术文档
│  ├─ architecture/
│  ├─ api/
│  ├─ database/
│  ├─ rag/
│  ├─ agent/
│  ├─ frontend/
│  ├─ security/
│  ├─ testing/
│  ├─ deployment/
│  └─ adr/
│
├─ scripts/                        # 开发、检查、初始化脚本
├─ .github/
│  ├─ workflows/
│  └─ ISSUE_TEMPLATE/
│
├─ .env.example
├─ .editorconfig
├─ .gitignore
├─ docker-compose.yml
├─ Makefile
├─ README.md
├─ CONTRIBUTING.md
├─ SECURITY.md
└─ LICENSE
