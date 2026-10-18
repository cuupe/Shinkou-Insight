# 代码规模分析

统计日期：2026-10-18。统计当前工作区准备提交的版本。

## 统计口径

使用 `git ls-files -co --exclude-standard` 去重获取已跟踪文件和未忽略的新文件，只统计 `apps/`、`scripts/` 下的 Python、Java、Vue、TypeScript、JavaScript、CSS、HTML、SQL、PowerShell 和 CMD 源文件。排除第三方依赖、虚拟环境、构建产物、日志、文档、配置及锁文件。Vue 单文件组件整体归入 Vue，包含其中的模板、脚本和样式。测试按路径中的 `test`、`tests`、`__tests__` 目录识别。

“物理行数”包含空行和注释；“非空行数”仅排除空白行，仍含注释，不能等同于剔除注释后的有效代码行数。

## 按模块

| 模块 | 源文件 | 物理行数 | 非空行数 | 其中测试行数 | 测试文件 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vue 前端 `apps/web` | 171 | 50,120 | 47,278 | 628 | 6 |
| Python AI 后端 `apps/ai-service` | 126 | 28,238 | 25,335 | 9,348 | 33 |
| Java 后端及 SQL `apps/backend` | 188 | 11,152 | 10,083 | 988 | 9 |
| 开发脚本 `scripts` | 15 | 739 | 669 | 0 | 0 |
| **合计** | **500** | **90,249** | **83,365** | **10,964** | **48** |

按物理行数，前端占 55.5%，Python AI 后端占 31.3%，Java 后端及 SQL 占 12.4%，脚本占 0.8%。排除测试后约 79,285 行；测试代码占总物理行数的 12.1%。此比例反映测试代码体积，不代表测试覆盖率。

## 按语言

| 语言 | 文件数 | 物理行数 |
| --- | ---: | ---: |
| Vue | 103 | 41,445 |
| Python | 126 | 28,238 |
| Java | 153 | 10,360 |
| TypeScript | 60 | 7,267 |
| SQL | 35 | 792 |
| CSS | 1 | 765 |
| PowerShell | 14 | 730 |
| JavaScript（测试） | 6 | 628 |
| HTML | 1 | 15 |
| CMD | 1 | 9 |

## 维护重点

该项目已具有中等规模的多服务业务系统体量，代码主要集中在 Vue 页面和 Python AI 运行时。非测试文件中有 19 个超过 1,000 行，较大的文件如下：

| 文件 | 物理行数 |
| --- | ---: |
| `apps/web/src/views/project/AgentWorkspaceView.vue` | 5,624 |
| `apps/web/src/views/settings/ModelsView.vue` | 2,123 |
| `apps/ai-service/models/llm.py` | 1,891 |
| `apps/web/src/views/settings/ToolsView.vue` | 1,645 |
| `apps/web/src/views/project/AssetsView.vue` | 1,469 |
| `apps/backend/src/main/java/com/cuupe/backend/modules/agent/service/AgentService.java` | 1,378 |

建议优先拆分 Agent 工作区页面及模型设置页面中的独立面板、状态和交互逻辑；Python 模型网关及 Java Agent 服务也可按职责逐步拆分。现有测试体积主要集中在 Python，前端测试以工具和状态逻辑为主，可以补充关键页面、认证代理和流式交互的集成验证。单看行数不能判断代码质量或圈复杂度，这些是后续审查的优先顺序。

前端正式构建已提示部分压缩后的 JavaScript 分块超过 500 kB，可在后续性能工作中检查路由、图表和 Markdown 渲染依赖的加载边界。
