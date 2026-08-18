export type AssetStatus = "indexed" | "indexing" | "failed";

export const workspace = {
  name: "Shinkou Labs",
  slug: "shinkou-labs",
  description: "面向企业知识的智能调研与决策工作区。",
  plan: "Enterprise workspace",
  initials: "SL",
  usagePercent: "68%",
};

export const projects = [
  {
    id: "queue-selection",
    name: "消息队列技术选型",
    description: "比较 Kafka、RabbitMQ 与 RocketMQ，形成当前阶段的技术建议。",
    assets: 18,
    runs: 12,
    reports: 4,
    color: "#15b8a6",
  },
  {
    id: "observability",
    name: "可观测性平台评估",
    description: "梳理内部监控能力与开源方案的落差。",
    assets: 9,
    runs: 6,
    reports: 2,
    color: "#8b7cf6",
  },
  {
    id: "retrieval-quality",
    name: "知识检索质量提升",
    description: "围绕 Chunk、Rerank 与引用准确率建立评估基线。",
    assets: 26,
    runs: 9,
    reports: 3,
    color: "#f59e0b",
  },
];

export const stats = [
  {
    label: "活跃项目",
    value: "12",
    trend: "+2 本月",
    icon: "folder",
    tone: "teal",
  },
  {
    label: "知识资产",
    value: "186",
    trend: "+24 本周",
    icon: "layers",
    tone: "violet",
  },
  {
    label: "调研运行",
    value: "48",
    trend: "+8 本周",
    icon: "activity",
    tone: "amber",
  },
  {
    label: "完成率",
    value: "91.4%",
    trend: "+4.8%",
    icon: "check",
    tone: "blue",
  },
];

export const recentRuns = [
  {
    id: "run-2408",
    project: "消息队列技术选型",
    title: "评估高峰流量下的可靠性与成本",
    status: "completed",
    statusLabel: "已完成",
    time: "今天 09:42",
    duration: "6m 18s",
    tokens: "42.8k",
  },
  {
    id: "run-2407",
    project: "可观测性平台评估",
    title: "补充内部告警与审计要求",
    status: "running",
    statusLabel: "运行中",
    time: "今天 09:18",
    duration: "3m 04s",
    tokens: "18.2k",
  },
  {
    id: "run-2406",
    project: "知识检索质量提升",
    title: "对比 Hybrid 与 Vector 检索表现",
    status: "failed",
    statusLabel: "失败",
    time: "昨天 18:27",
    duration: "1m 12s",
    tokens: "8.9k",
  },
  {
    id: "run-2405",
    project: "消息队列技术选型",
    title: "整理团队现有约束与迁移成本",
    status: "completed",
    statusLabel: "已完成",
    time: "昨天 15:06",
    duration: "4m 52s",
    tokens: "31.4k",
  },
];

export const assets = [
  {
    id: "asset-01",
    name: "订单系统架构说明.pdf",
    type: "PDF",
    size: "4.8 MB",
    uploader: "林默",
    updated: "今天 09:16",
    chunks: 42,
    progress: 100,
    status: "indexed" as AssetStatus,
    reason: "",
  },
  {
    id: "asset-02",
    name: "峰值流量与可靠性要求.md",
    type: "Markdown",
    size: "86 KB",
    uploader: "周然",
    updated: "今天 08:52",
    chunks: 18,
    progress: 100,
    status: "indexed" as AssetStatus,
    reason: "",
  },
  {
    id: "asset-03",
    name: "团队技术能力评估.txt",
    type: "Text",
    size: "32 KB",
    uploader: "陈雪",
    updated: "昨天 17:40",
    chunks: 12,
    progress: 74,
    status: "indexing" as AssetStatus,
    reason: "",
  },
  {
    id: "asset-04",
    name: "Kafka 生产实践复盘.pdf",
    type: "PDF",
    size: "2.1 MB",
    uploader: "林默",
    updated: "昨天 16:24",
    chunks: 0,
    progress: 0,
    status: "failed" as AssetStatus,
    reason: "解析器无法识别第 7 页的嵌入字体",
  },
  {
    id: "asset-05",
    name: "RocketMQ 设计白皮书.pdf",
    type: "PDF",
    size: "7.2 MB",
    uploader: "周然",
    updated: "8 月 06 日",
    chunks: 64,
    progress: 100,
    status: "indexed" as AssetStatus,
    reason: "",
  },
];

export const retrievalResults = [
  {
    rank: 1,
    source: "订单系统架构说明.pdf · p.12",
    title: "消息投递与消费确认",
    score: "0.94",
    vector: "0.96",
    keyword: "0.82",
    fusion: "0.94",
    reranked: true,
    text: "订单事件进入消息总线后，生产端必须等待 Broker 返回持久化确认。消费端采用手动 ack，并在业务事务提交后确认消息，避免重复消费与消息丢失。",
  },
  {
    rank: 2,
    source: "峰值流量与可靠性要求.md · 峰值流量",
    title: "流量峰值与降级策略",
    score: "0.89",
    vector: "0.87",
    keyword: "0.91",
    fusion: "0.89",
    reranked: true,
    text: "大促期间预计峰值为平时流量的 8-12 倍。系统需要支持生产端限流、消费端水平扩展，并允许非核心事件进入延迟队列。",
  },
  {
    rank: 3,
    source: "团队技术能力评估.txt · 现状",
    title: "团队运维与排障能力",
    score: "0.81",
    vector: "0.76",
    keyword: "0.88",
    fusion: "0.81",
    reranked: false,
    text: "团队目前具备 Kafka 的基础运维经验，但对跨地域复制、积压治理和 Broker 调优尚缺少稳定的操作手册。",
  },
];

export const reports = [
  {
    id: "report-01",
    title: "消息队列技术选型建议",
    project: "消息队列技术选型",
    version: "v1.4",
    updated: "今天 10:06",
    status: "已发布",
    citations: 24,
    lead: "结合内部业务约束与现有团队能力，建议当前阶段采用 Kafka 作为核心消息总线，并以明确的可靠性边界控制迁移风险。",
    summary: "Kafka 在吞吐能力、生态成熟度和团队已有经验之间取得了更好的平衡。RabbitMQ 在低延迟与简单路由场景中仍有优势。",
    recommendation: "推荐方案：Kafka",
    recommendationDetail: "优先验证跨地域复制与积压治理，完成后进入灰度迁移。",
  },
  {
    id: "report-02",
    title: "可观测性平台调研摘要",
    project: "可观测性平台评估",
    version: "v0.8",
    updated: "昨天 17:24",
    status: "草稿",
    citations: 14,
    lead: "围绕内部告警、审计和可观测性要求整理现有方案，形成待验证的建设方向。",
    summary: "当前平台已覆盖基础指标和日志采集，但在统一告警治理与审计追踪方面仍有明显缺口。",
    recommendation: "推荐方案：补齐统一告警治理",
    recommendationDetail: "优先完成告警分级、责任归属和审计留痕设计。",
  },
  {
    id: "report-03",
    title: "Hybrid 检索优化实验报告",
    project: "知识检索质量提升",
    version: "v2.1",
    updated: "8 月 05 日",
    status: "已发布",
    citations: 31,
    lead: "通过 Hybrid、Vector 和 Keyword 多组检索实验，评估不同召回策略对引用准确率的影响。",
    summary: "Hybrid 检索在召回覆盖和关键词精确匹配之间取得了更稳定的平衡。",
    recommendation: "推荐方案：Hybrid 检索",
    recommendationDetail: "继续优化 Chunk 边界和 Rerank 阈值，建立稳定评估基线。",
  },
];

export const actionItems = [
  {
    id: "action-1",
    title: "确认跨地域复制的 RPO 目标",
    owner: "林默",
    due: "今天",
    priority: "高",
    status: "in-progress",
  },
  {
    id: "action-2",
    title: "补充 RabbitMQ 运维成本数据",
    owner: "周然",
    due: "明天",
    priority: "中",
    status: "todo",
  },
  {
    id: "action-3",
    title: "安排架构委员会评审",
    owner: "陈雪",
    due: "8 月 13 日",
    priority: "高",
    status: "todo",
  },
  {
    id: "action-4",
    title: "归档已确认的检索基线",
    owner: "林默",
    due: "8 月 09 日",
    priority: "低",
    status: "done",
  },
];

export const evaluationCases = [
  {
    id: "E-1024",
    query: "Kafka 是否满足订单事件的可靠投递要求？",
    recall: "100%",
    citation: "100%",
    json: "100%",
    status: "passed",
  },
  {
    id: "E-1023",
    query: "当前团队是否具备 RocketMQ 运维能力？",
    recall: "100%",
    citation: "92%",
    json: "100%",
    status: "passed",
  },
  {
    id: "E-1022",
    query: "峰值流量下推荐的扩容策略是什么？",
    recall: "83%",
    citation: "76%",
    json: "100%",
    status: "review",
  },
  {
    id: "E-1021",
    query: "列出所有未解决的迁移风险。",
    recall: "67%",
    citation: "58%",
    json: "75%",
    status: "failed",
  },
];

export const userProfile = {
  name: "林默",
  initials: "LM",
  email: "lin.mo@shinkou.ai",
  phone: "138****8024",
  timezone: "Asia/Shanghai",
  roleLabel: "工作区成员",
};

export const dashboardData = {
  greeting: "早上好",
  titleSuffix: "✦",
  subtitle: "这是 Shinkou Labs 的最新工作状态。",
  trend: {
    title: "运行与洞察趋势",
    description: "过去 30 天的运行量和完成情况",
    ranges: ["过去 7 天", "过去 30 天", "过去 90 天"],
    yAxis: ["60", "40", "20", "0"],
    xAxis: ["7/11", "7/18", "7/25", "8/01", "8/08"],
    legend: ["完成运行", "总运行"],
    series: [
      { name: "完成运行", data: [18, 24, 22, 35, 31], color: "#16b8a6" },
      { name: "总运行", data: [26, 32, 30, 43, 40], color: "#8175e8" },
    ],
    summary: [
      { value: "48", label: "总运行" },
      { value: "91.4%", label: "完成率", tone: "teal" },
      { value: "2.4m", label: "平均耗时" },
    ],
  },
  focusItems: [
    {
      number: "01",
      title: "1 个运行需要重试",
      detail: "Hybrid 检索基线 · 昨天 18:27",
      route: "project-runs",
      icon: "activity",
      ariaLabel: "查看运行列表",
    },
    {
      number: "02",
      title: "3 个证据冲突待审核",
      detail: "消息队列技术选型 · 运行 #2408",
      route: "project-runs",
      icon: "arrow",
      ariaLabel: "查看运行详情",
    },
    {
      number: "03",
      title: "2 个行动项即将到期",
      detail: "最近截止日期为今天",
      route: "project-action-items",
      icon: "arrow",
      ariaLabel: "查看行动项",
    },
  ],
};

export const projectOverviewData = {
  memberCountLabel: "4 位成员",
  updatedLabel: "最近更新 今天 10:06",
  visibilityLabel: "内部项目",
  quickActions: [
    {
      label: "上传资料",
      description: "PDF、Markdown、TXT",
      route: "project-assets",
      tone: "teal",
    },
    {
      label: "检索测试",
      description: "验证知识库召回",
      route: "project-playground",
      tone: "violet",
    },
    {
      label: "创建调研",
      description: "让 Agent 开始工作",
      route: "project-new-run",
      tone: "amber",
    },
  ],
  assetSummary: {
    title: "知识资产状态",
    description: "当前项目的资料索引进度",
    totalLabel: "全部资料",
    indexedLabel: "已索引",
    completion: "86%",
    completionLabel: "索引完成率",
  },
  capabilities: [
    { title: "知识库已就绪", description: "支持混合检索与证据引用", icon: "database" },
    { title: "Agent 可运行", description: "可直接创建调研任务", icon: "zap" },
  ],
};

export const assetTabs = ["全部", "已索引", "处理中", "失败"];
export const assetFilterOptions = [
  { label: "全部", value: "全部" },
  { label: "已索引", value: "indexed" },
  { label: "处理中", value: "indexing" },
  { label: "失败", value: "failed" },
];
export const assetDetailCopy = {
  subtitle: "查看索引详情、切片信息和引用状态。",
  summaryTitle: "索引摘要",
  summaryDescription: "当前资产可被 Agent 检索和引用。",
  chunksLabel: "切片数量",
  progressLabel: "索引进度",
  updatedLabel: "最后更新",
  securityNote: "项目内资料，仅对工作区成员可见。",
};
export const timezoneOptions = [
  { value: "Asia/Shanghai", label: "中国标准时间（UTC+8）" },
  { value: "Asia/Tokyo", label: "日本标准时间（UTC+9）" },
  { value: "UTC", label: "协调世界时（UTC）" },
];
export const reportReaderCopy = {
  eyebrow: "TECHNICAL DECISION REPORT",
  summaryHeading: "01 / 执行摘要",
};
export const reportFilters = ["全部", "已发布", "草稿"];
export const runStatusFilters = ["全部状态", "已完成", "运行中", "失败"];
export const actionItemStatusFilters = ["全部", "todo", "in-progress", "done"];
export const memberRoleFilters = ["全部", "OWNER", "ADMIN", "MEMBER"];
export const memberRoleCycle = ["MEMBER", "ADMIN"];

export const retrievalModes = ["Hybrid", "Vector", "Keyword"];
export const playgroundDefaults = {
  query: "消息队列在峰值流量下如何保证可靠投递？",
  mode: "Hybrid",
  topK: 5,
  rerank: true,
};
export const runSummary = [
  { value: "48", label: "总运行" },
  { value: "91.4%", label: "完成率" },
  { value: "2.4m", label: "平均耗时" },
];

export const researchPreviewSteps = [
  "拆解调研问题并生成检索计划",
  "优先引用项目知识库中的可验证资料",
  "整理结论、风险和待确认问题",
];
export const researchDefaults = {
  goal: "结合内部业务约束，比较 Kafka、RabbitMQ 和 RocketMQ，给出当前阶段的推荐方案、风险和待确认问题。",
  allowWeb: true,
  maxRounds: 5,
};
export const projectDefaults = {
  description: "新建项目，等待补充调研目标。",
  color: "#15b8a6",
};
export const actionItemDefaults = {
  owner: "林默",
  due: "待安排",
  priority: "中",
  status: "todo",
};
export const memberInviteDefaults = {
  role: "MEMBER",
  date: "今天",
  active: "待接受邀请",
};

export const runDetailData = {
  metrics: [
    { label: "运行耗时", value: "6m 18s" },
    { label: "消耗 Tokens", value: "42.8k" },
    { label: "引用证据", value: "24" },
    { label: "可信度", value: "91%" },
  ],
  summary:
    "结合内部业务约束与已检索证据，当前阶段建议采用 Kafka 作为核心消息总线，并优先验证跨地域复制与积压治理能力。",
  keyPoints: [
    "吞吐能力和团队已有经验使 Kafka 更适合当前阶段。",
    "生产端应等待持久化确认，消费端在事务提交后手动 ack。",
    "跨地域复制与长期运维成本仍需补充验证。",
  ],
  evidence: [
    {
      code: "E1",
      title: "生产端等待持久化确认",
      source: "订单系统架构说明.pdf · p.12",
    },
    {
      code: "E2",
      title: "团队具备 Kafka 基础运维经验",
      source: "团队技术能力评估.txt · 现状",
    },
    {
      code: "C1",
      title: "重试策略存在冲突",
      source: "峰值流量与可靠性要求.md · 峰值流量",
    },
  ],
  evidenceDetail:
    "生产端必须等待 Broker 返回持久化确认，消费端在业务事务提交后确认消息。",
};

export const evaluationSummary = {
  metrics: [
    { label: "平均召回率", value: "87.5%", change: "+4.2% 较上次" },
    { label: "引用准确率", value: "81.5%", change: "+6.8% 较上次" },
    { label: "结构化输出", value: "93.8%", change: "稳定" },
  ],
  lastRun: "最近一次运行：今天 09:30",
};
export const evaluationStatusLabels = {
  passed: "通过",
  review: "待复核",
  failed: "失败",
};

export const workspaceMembers = [
  { name: "林默", email: "lin.mo@shinkou.ai", role: "OWNER", date: "2026/06/12", active: "刚刚" },
  { name: "周然", email: "ran.zhou@shinkou.ai", role: "ADMIN", date: "2026/06/14", active: "12 分钟前" },
  { name: "陈雪", email: "xue.chen@shinkou.ai", role: "MEMBER", date: "2026/07/03", active: "今天 09:32" },
  { name: "顾言", email: "yan.gu@shinkou.ai", role: "MEMBER", date: "2026/07/18", active: "昨天" },
];

export const modelConfigs = [
  { name: "GPT-4.1", provider: "OpenAI", use: "调研规划与报告生成", enabled: true },
  { name: "Qwen 2.5 72B", provider: "DashScope", use: "内部知识检索改写", enabled: true },
  { name: "Claude Sonnet 4", provider: "Anthropic", use: "备用模型", enabled: false },
];

export const toolConfigs = [
  { name: "内部知识库", description: "检索当前工作区已索引资产", icon: "database", enabled: true },
  { name: "Web Search", description: "补充外部公开资料与最新信息", icon: "globe", enabled: true },
  { name: "Jira", description: "读取项目缺陷与行动项状态", icon: "list", enabled: false },
];

export const promptConfigs = [
  { name: "research-planner", version: "v3.2", updated: "今天 09:12", status: "生产中" },
  { name: "evidence-reviewer", version: "v2.8", updated: "昨天 18:03", status: "生产中" },
  { name: "report-writer", version: "v1.6", updated: "8 月 05 日", status: "草稿" },
];
