# 18. GitHub Backlog

可直接转为 Issues。估时仅用于个人排期。

## Milestone 0：Foundation

| Issue | 优先级 | 估时 | 验收 |
|---|---|---:|---|
| 修复登录 Set-Cookie | P0 | 0.5d | 浏览器有 HttpOnly Cookie |
| Filter 支持 Cookie JWT | P0 | 0.5d | `/auth/me` 刷新有效 |
| Logout 清 Redis 和 Cookie | P0 | 0.5d | 会话完全失效 |
| 引入 Flyway | P0 | 0.5d | 新库自动迁移 |
| 工作区 IDOR 测试 | P0 | 0.5d | 越权全部 403 |

## Milestone 1：Knowledge Assets

| Issue | 优先级 | 估时 |
|---|---|---:|
| knowledge_assets migration | P0 | 0.5d |
| 上传 API | P0 | 1d |
| PDF Parser | P0 | 1.5d |
| Markdown/TXT Parser | P0 | 1d |
| Chunking Service | P0 | 1d |
| Asset List UI | P0 | 1.5d |
| Asset Detail / Chunk UI | P1 | 1.5d |
| 重试和删除 | P1 | 1d |

## Milestone 2：Retrieval

| Issue | 优先级 | 估时 |
|---|---|---:|
| Milvus setup | P0 | 0.5d |
| Embedding Provider | P0 | 1d |
| Batch indexing | P0 | 1.5d |
| Vector search | P0 | 1d |
| Keyword search | P0 | 1d |
| RRF fusion | P0 | 1d |
| Playground API/UI | P0 | 2d |
| Retrieval evaluation | P0 | 1.5d |
| Reranker adapter | P2 | 1d |

## Milestone 3：RAG Answer

| Issue | 优先级 | 估时 |
|---|---|---:|
| Model Provider | P0 | 1d |
| Answer Prompt + Schema | P0 | 1d |
| Citation DTO | P0 | 1d |
| Quote validation | P0 | 1d |
| Insufficient evidence | P0 | 0.5d |
| Answer UI | P1 | 1d |

## Milestone 4：Agent Workflow

| Issue | 优先级 | 估时 |
|---|---|---:|
| research_runs / run_steps | P0 | 1d |
| LangGraph State | P0 | 1d |
| Planner Node | P0 | 1d |
| Retrieve Node | P0 | 1d |
| Evidence Evaluator | P0 | 1.5d |
| Query Rewrite | P1 | 1d |
| Report Writer | P0 | 1.5d |
| Report Reviewer | P0 | 1.5d |
| Max rounds / cancellation | P0 | 1.5d |
| SSE events | P0 | 2d |
| Research Workspace UI | P0 | 3d |

## Milestone 5：Report & Evaluation

| Issue | 优先级 | 估时 |
|---|---|---:|
| Report tables/API | P0 | 1.5d |
| Citation Drawer | P0 | 1d |
| Action Items | P1 | 1d |
| Prompt versioning | P0 | 1d |
| Metrics collection | P0 | 1.5d |
| Evaluation Runner | P0 | 2d |
| Dashboard | P1 | 2d |

## Milestone 6：Portfolio Release

| Issue | 优先级 | 估时 |
|---|---|---:|
| Testcontainers | P0 | 1.5d |
| Playwright E2E | P0 | 1.5d |
| GitHub Actions | P0 | 1d |
| Docker Compose full stack | P0 | 1d |
| Seed demo data | P0 | 1d |
| README screenshots | P0 | 1d |
| Demo video | P0 | 1d |
| Evaluation report | P0 | 1d |

## Optional：LoRA

| Issue | 优先级 | 估时 |
|---|---|---:|
| Evidence dataset pipeline | P2 | 2d |
| Baseline Prompt evaluation | P2 | 1d |
| QLoRA training | P2 | 2d+ |
| Adapter evaluation | P2 | 1.5d |
| Model Router | P2 | 1d |
