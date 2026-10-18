# 功能与源码覆盖矩阵

静态范围核对基于 26 个页面、108 个业务接口、34 个 AI 接口与 5 个框架入口。每个接口有独立 API 编号；每页有 PAGE 编号和具体业务模块；测试样例不代表已通过。

## 页面与操作覆盖

路径中的 {w}/{p} 替换为你的 QA workspaceId/projectId，{assetId}/{runId} 用本轮对象 ID。所有页面均按对应 PAGE 编号验收。

| 页面和路径 | 页面源码 | PAGE 编号 | 专项模块 | 源码中识别的动作（需核对每个可见操作） |
|---|---|---|---|---|
| 登录 `/login` | `apps/web/src/views/auth/LoginView.vue` | PAGE-001 | AUTH | LoginForm：密码/短信登录、验证码、恢复密码、记住手机号、模式切换 |
| 注册 `/register` | `apps/web/src/views/auth/RegisterView.vue` | PAGE-002 | AUTH | RegisterForm：注册、短信、图形码、协议弹窗、密码显示、登录跳转 |
| 帮助中心 `/workspaces/{w}/help` | `apps/web/src/views/help/HelpCenterView.vue` | PAGE-003 | STAT | focusSearch, categoryCount, openArticle, toggleFaq, submitFeedback |
| 行动项 `/workspaces/{w}/projects/{p}/action-items` | `apps/web/src/views/project/ActionItemsView.vue` | PAGE-004 | REPORT | mapActionItem, loadActionItems, itemsForStatus, resetForm, openCreateDialog, openEditDialog, saveActionItem, advanceItem, advanceLabel, priorityClass |
| 项目对话 `/workspaces/{w}/projects/{p}/agent` | `apps/web/src/views/project/AgentWorkspaceView.vue` | PAGE-005 | AGENT | handleWebSearchToggle, formatElapsed, activityDetail, nextActivityLabel, formatProcessingTime, formatRealToken, formatTokenCount, loadContextSources, modelConfig, applyModelGenerationDefaults, loadModelOptions, loadWebSearchConfig, initializeAgentWorkspace, returnToEvaluation, eventIcon, citationForUrl, citationTooltip, citationBadge, escapeRegExp, citationMarkerExpression, normalizeCitationLinks, citationForMarker, citationSourceKey, uniqueCitations, messageCitations, messageParagraphs, citationNumber, inspectorCitationNumber, citationTitle, renderMessageMarkdown, writeTextToClipboard, textContentForCopy, copyMessage, copyCodeBlock, openMessageCitation, eventStatusLabel, eventTimeLabel, attachmentIcon, attachmentLabel, detectAttachmentKind, formatFileSize, openAttachmentPicker, normalizeFileLibraryAttachment, isPendingFileLibraryAttachment, openFileLibrary, toggleFileLibrarySelection, confirmFileLibrarySelection, closeFileLibrary, visibleMessageAttachments, toggleAttachmentGroup, attachmentImageUrl, isImageAttachmentPreviewable, openMessageImagePreview, closeMessageImagePreview, handleAttachmentClick, attachmentId, normalizePastedFile, appendAttachmentFiles, handleFilesSelected, handleComposerPaste, removePendingAttachment, openCitation, isWebCitation, canSaveCitation, citationKnowledgeKey, savedCitationAsset, isSavingCitation, saveCitationToKnowledge, handleSubmit, handleCreateThread, requestDeleteThread, confirmDeleteThread, openSettings, exportConversation, scrollConversationToBottom |
| 知识资产详情 `/workspaces/{w}/projects/{p}/knowledge/assets/{assetId}` | `apps/web/src/views/project/AssetDetailView.vue` | PAGE-006 | ASSET | mapRemoteAsset, loadChunkPage, setActiveSection, setPreviewExpanded, applyCitationTarget, goBack, reindex, downloadOriginal, copyChunkId |
| 知识库 `/workspaces/{w}/projects/{p}/knowledge/assets` | `apps/web/src/views/project/AssetsView.vue` | PAGE-007 | ASSET | syncChunkingConfig, saveChunkingConfig, mapAsset, stopIndexPolling, startIndexPolling, loadAssets, onFilesSelected, updatedRank, openAsset, toggleSelected, toggleAllVisible, clearSelection, retrySelected, requestDelete, confirmDelete |
| 评估 `/workspaces/{w}/projects/{p}/evaluation` | `apps/web/src/views/project/EvaluationView.vue` | PAGE-008 | EVAL | averageMetric, formatMetric, displayQuery, evaluationStatusLabel, createEvaluation, splitAnnotationList, parseJsonStringList, parseJsonRecord, mapEvaluationCase, saveEvaluationCase, editSelectedCase, canRunEvaluation, runSelectedEvaluation, createActionFromFailedEvaluation, syncEvaluationData, openSelectedCaseInPlayground, openSelectedCaseInAgent, updateSelectedCaseStatus |
| 文件库 `/workspaces/{w}/projects/{p}/files` | `apps/web/src/views/project/FileLibraryView.vue` | PAGE-009 | LIB | normalizeFile, formatBytes, fileIcon, fileKindLabel, canPreview, isExternalMedia, loadFiles, openPreview, closePreview |
| 项目概览 `/workspaces/{w}/projects/{p}/overview` | `apps/web/src/views/project/OverviewView.vue` | PAGE-010 | PRJ | statisticStatusLabel, overviewIcon, formatTokens, heatLevel, downloadText, exportTokenCsv, exportProjectSnapshot |
| 项目流程/规划输入 `/workspaces/{w}/projects/{p}/planning` | `apps/web/src/views/project/PlanningView.vue` | PAGE-011 | PLAN | loadDraft, saveDraft, analysisGoal, startAnalysis, openResearch, openReview |
| 检索 Playground `/workspaces/{w}/projects/{p}/knowledge/playground` | `apps/web/src/views/project/PlaygroundView.vue` | PAGE-012 | RAG | formatScore, modeLabel, mapResult, runSearch, saveAsEvaluationCase, returnToEvaluation, openParameters, applyParameters, openEvidence |
| 报告 `/workspaces/{w}/projects/{p}/reports` | `apps/web/src/views/project/ReportsView.vue` | PAGE-013 | REPORT | mapProjectReport, loadReports, citationLabel, citationFooter, openEditor, saveReport, toggleReportStatus, exportReport, copySummary, createActionFromRecommendation |
| 审查 `/workspaces/{w}/projects/{p}/review` | `apps/web/src/views/project/ReviewView.vue` | PAGE-014 | REPORT | loadGovernance, saveRules, runReview, openPlanning |
| 分析详情 `/workspaces/{w}/projects/{p}/research/runs/{runId}` | `apps/web/src/views/project/RunDetailView.vue` | PAGE-015 | RUN | time, go, control, copyEvidence, exportReport |
| 智能分析记录 `/workspaces/{w}/projects/{p}/research/runs` | `apps/web/src/views/project/RunsView.vue` | PAGE-016 | RUN | queueStatusLabel, mapRun, loadRuns, priorityLabel, statusClass, openTask, retryTask, cancelQueuedTask |
| 工作区设置 `/workspaces/{w}/settings` | `apps/web/src/views/settings/GeneralView.vue` | PAGE-017 | WS | applyPreferences, loadSettings, saveSettings, copySlug, confirmDelete, openDeleteDialog, savePreferences |
| 模型配置 `/workspaces/{w}/settings/models` | `apps/web/src/views/settings/ModelsView.vue` | PAGE-018 | MODEL | connectionKey, parseConfig, isEmbeddingConfig, loadEmbeddingForm, fromApiModel, embeddingPayload, useLocalEmbedding, saveEmbedding, testEmbedding, toggleModel, testConnection, fetchContextWindow, fetchContextWindowForModel, removeModel, saveDefaultModel, resetNewModel, openAddModel, openAddModelForConnection, openEditModel, applyConnectionSelection, updateProviderDefaults, saveModel |
| 安全审计 `/workspaces/{w}/settings/security` | `apps/web/src/views/settings/SecurityView.vue` | PAGE-019 | SEC | resultIcon, resultClass, formatTime, refresh, waitForRun, runHarness |
| 工具与连接器 `/workspaces/{w}/settings/tools` | `apps/web/src/views/settings/ToolsView.vue` | PAGE-020 | TOOL | applyAgentPolicy, applyLocalToolPreferences, applyLocalTools, loadLocalTools, reloadLocalTools, toggleLocalTool, saveLocalTools, localToolSourceLabel, readyLabel, resetConnectorForm, openConnector, openNewConnector, savePolicy, saveConnector, disconnectTool, removeTool |
| 个人设置 `/workspaces/{w}/account/settings` | `apps/web/src/views/settings/UserSettingsView.vue` | PAGE-021 | STAT | applyUser, saveProfile, savePreferences, changePassword, sendPasswordCode, sendPhoneCode, changePhone, handleLogout |
| 联网搜索 `/workspaces/{w}/settings/web-search` | `apps/web/src/views/settings/WebSearchView.vue` | PAGE-022 | WEB | loadForm, changeProvider, load, save, testConnection |
| 工作区概览 `/workspaces/{w}/dashboard` | `apps/web/src/views/workspace/DashboardView.vue` | PAGE-023 | STAT | openReport, formatTokens, focusIcon |
| 成员与权限 `/workspaces/{w}/members` | `apps/web/src/views/workspace/MembersView.vue` | PAGE-024 | WS | memberDisplayFields, memberActivityFields, loadMembers, isCurrentUser, openInviteDialog, inviteMember, updateMemberRole, canEditRole, memberRoleOptions |
| 通知 `/workspaces/{w}/notifications` | `apps/web/src/views/workspace/NotificationsView.vue` | PAGE-025 | STAT | notificationIcon, openNotification |
| 项目列表 `/workspaces/{w}/projects` | `apps/web/src/views/workspace/ProjectsView.vue` | PAGE-026 | PRJ | loadProjects, goToPage, previousPage, nextPage, openCreateProject, resetProjectForm, createProject, openProjectMenu, openEditProject, saveProjectEdit, toggleProjectArchive, requestDeleteProject, confirmDeleteProject |

附加组件：Sidebar/Topbar 工作区和项目切换、菜单、搜索、通知与账户入口；ThemeToggle；ImageCaptcha/RecoveryDialog/AgreementDialog；引用、附件预览与文件库弹窗；ProjectWorkflow。归入 WS/PRJ/AUTH/STAT/AGENT/PAGE 用例。

## 模块用例索引

| 模块 | 编号范围 | 用例数 | 批次 |
|---|---|---:|---|
| 环境与基线 | ENV-001 ～ ENV-012 | 12 | 01 准备 |
| 注册、登录与会话 | AUTH-001 ～ AUTH-024 | 24 | 02 账号 |
| 工作区与成员 | WS-001 ～ WS-014 | 14 | 02 账号 |
| 项目管理 | PRJ-001 ～ PRJ-012 | 12 | 03 配置与项目 |
| 模型与 Embedding | MODEL-001 ～ MODEL-016 | 16 | 03 配置与项目 |
| 工具、连接器与权限策略 | TOOL-001 ～ TOOL-016 | 16 | 03 配置与项目 |
| 联网搜索与来源验证 | WEB-001 ～ WEB-012 | 12 | 03 配置与项目 |
| 知识资料上传、索引与切分 | ASSET-001 ～ ASSET-020 | 20 | 04 文件与索引 |
| 文件库与预览 | LIB-001 ～ LIB-008 | 8 | 04 文件与索引 |
| 检索与知识问答 | RAG-001 ～ RAG-019 | 19 | 05 检索 |
| Agent 对话工作台 | AGENT-001 ～ AGENT-031 | 31 | 06 核心运行 |
| 项目规划与发起研究 | PLAN-001 ～ PLAN-008 | 8 | 06 核心运行 |
| 研究运行、计划与恢复 | RUN-001 ～ RUN-021 | 21 | 06 核心运行 |
| 报告、审查与行动闭环 | REPORT-001 ～ REPORT-020 | 20 | 07 结果闭环 |
| 评估与质量验证 | EVAL-001 ～ EVAL-014 | 14 | 07 结果闭环 |
| 工作区统计、通知与账户设置 | STAT-001 ～ STAT-016 | 16 | 08 全站功能 |
| 鉴权、数据隔离与输入安全 | SEC-001 ～ SEC-017 | 17 | 09 权限与异常 |
| 队列、缓存、持久化与上线运行 | OPS-001 ～ OPS-022 | 22 | 10 上线准备 |
| 性能、稳定性与兼容性 | LOAD-001 ～ LOAD-008 | 8 | 10 上线准备 |
| 核心流程端到端验收 | CORE-001 ～ CORE-010 | 10 | 11 最终核心回归 |
| 核心主流程逐步记录 | E2EA-001 ～ E2EA-022 | 22 | 06 核心运行 |
| 所有支持文件格式 | FMT-001 ～ FMT-040 | 40 | 04 文件与索引 |
| 复杂文件与原生文档生成 | FILEX-001 ～ FILEX-011 | 11 | 04 文件与索引 |
| 全部页面通用验收 | PAGE-001 ～ PAGE-026 | 26 | 08 全站功能 |

## 全接口覆盖

完整独立编号和源码位置见 03-api-acceptance.md；Excel 的接口用例包含身份、输入、四个子结果和证据记录栏。

## 全格式覆盖

.aac, .avi, .bmp, .csv, .doc, .docx, .flac, .gif, .htm, .html, .jpeg, .jpg, .json, .m4a, .m4v, .markdown, .md, .mkv, .mov, .mp3, .mp4, .odp, .ods, .odt, .ogg, .opus, .pdf, .png, .ppt, .pptx, .rtf, .svg, .tif, .tiff, .txt, .wav, .webm, .webp, .xls, .xlsx

逐后缀 FMT-001～FMT-040；复杂解析与四种原生文档生成见 FILEX；上传/附件/预览链路分别在 ASSET/AGENT/LIB 验证。

## 当前自动测试文件（尚未在本轮全量执行）

### frontend：4 个文件

- `apps/web/test/agentMarkdown.test.mjs`
- `apps/web/test/agentProgress.test.mjs`
- `apps/web/test/agentStream.test.mjs`
- `apps/web/test/researchRun.test.mjs`

### backend：5 个文件

- `apps/backend/src/test/java/com/cuupe/backend/BackendApplicationTests.java`
- `apps/backend/src/test/java/com/cuupe/backend/modules/ai/AiIndexingClientTest.java`
- `apps/backend/src/test/java/com/cuupe/backend/modules/research/service/ResearchRunProgressServiceTest.java`
- `apps/backend/src/test/java/com/cuupe/backend/modules/asset/service/AssetIndexingServiceTest.java`
- `apps/backend/src/test/java/com/cuupe/backend/modules/agent/service/AgentServiceProgressTest.java`

### ai：27 个文件

- `apps/ai-service/test/test_agent_bus.py`
- `apps/ai-service/test/test_agent_evaluation.py`
- `apps/ai-service/test/test_agent_runtime.py`
- `apps/ai-service/test/test_api_structure.py`
- `apps/ai-service/test/test_config.py`
- `apps/ai-service/test/test_conversation_regressions.py`
- `apps/ai-service/test/test_document_generation.py`
- `apps/ai-service/test/test_event_bus.py`
- `apps/ai-service/test/test_hybrid_search.py`
- `apps/ai-service/test/test_knowledge_api.py`
- `apps/ai-service/test/test_knowledge_pipeline.py`
- `apps/ai-service/test/test_knowledge_recall_regressions.py`
- `apps/ai-service/test/test_llm_gateway.py`
- `apps/ai-service/test/test_mcp_system.py`
- `apps/ai-service/test/test_milvus_store.py`
- `apps/ai-service/test/test_postgres_keyword.py`
- `apps/ai-service/test/test_prompt_engineering.py`
- `apps/ai-service/test/test_research_progress.py`
- `apps/ai-service/test/test_retriever.py`
- `apps/ai-service/test/test_runtime_infrastructure.py`
- `apps/ai-service/test/test_search_quality.py`
- `apps/ai-service/test/test_security_harness.py`
- `apps/ai-service/test/test_semantic_agent.py`
- `apps/ai-service/test/test_source_content.py`
- `apps/ai-service/test/test_temporal_context.py`
- `apps/ai-service/test/test_tools.py`
- `apps/ai-service/test/test_web_search.py`

现有单元测试不自动等于所有文件格式、UI、真实供应商、部署拓扑或安全边界已覆盖。最终阶段按功能风险补实际集成与端到端证据。

## 范围完整性复核

- 每个 PAGE 编号对应一个真实页面，专项功能用例进一步覆盖按钮和状态。
- 每个静态路由与框架入口对应一个 API 编号，不把没有 UI 的接口排除。
- 内部工具、MCP/图谱/HTTP Worker 的启用和禁用分支均有用例，拟交付分支必须实际测试。
- 当前业务角色为 OWNER/ADMIN/MEMBER；没有实际 VIEWER 角色入口，不凭空增加通过项。
- 若对外功能清单比代码更多，差异登记为未交付；若测试期间增加功能或路径，更新此矩阵。
- 覆盖矩阵是静态清单，不是安全漏洞审计结论或生产可用性证明。
