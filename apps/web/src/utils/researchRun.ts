import type { ResearchRun } from "../api/types.ts";

export type ResearchEvent = {
  id: string | number;
  type: string;
  timestamp: string;
  node?: string;
  title?: string;
  detail?: string;
  task?: {
    id: string;
    title: string;
    status: string;
    summary?: string;
    error?: string;
    startedAt?: string;
    durationMs?: number;
  };
};

export const researchStages = [
  {
    title: "理解目标",
    nodes: ["VALIDATE_INPUT", "PLAN"],
    description: "梳理目标、约束与成功指标，生成研究计划",
  },
  {
    title: "搜集证据",
    nodes: [
      "DECISION",
      "RETRIEVE_INTERNAL",
      "EVALUATE_EVIDENCE",
      "REWRITE_QUERY",
      "SEARCH_WEB",
    ],
    description: "检索项目资料，检查相关性与证据缺口",
  },
  {
    title: "形成方案",
    nodes: ["SYNTHESIS", "SYNTHESIZE_FINDINGS", "WRITE_REPORT"],
    description: "综合证据，整理方案、风险与建议",
  },
  {
    title: "核验结果",
    nodes: ["REFLECTION", "REVIEW_REPORT", "PERSIST_RESULT", "END"],
    description: "核对引用和结论，保存报告供人工审查",
  },
];

export function isResearchActive(run: ResearchRun | null) {
  return (
    !!run &&
    ["PENDING", "QUEUED", "RUNNING", "PAUSED", "CANCELLING"].includes(
      String(run.status).toUpperCase(),
    )
  );
}

export function researchEvents(run: ResearchRun | null): ResearchEvent[] {
  return Array.isArray(run?.events) ? (run.events as ResearchEvent[]) : [];
}

export function researchStageIndex(run: ResearchRun | null) {
  if (!run) return -1;
  const observed = researchEvents(run).filter((event) => event.node);
  const node = ["FAILED", "CANCELLED"].includes(String(run.currentNode))
    ? observed.at(-1)?.node
    : run.currentNode || observed.at(-1)?.node;
  if (String(run.status).toUpperCase() === "COMPLETED")
    return researchStages.length;
  return researchStages.findIndex((stage) =>
    stage.nodes.includes(String(node)),
  );
}

export function researchElapsed(run: ResearchRun | null, now: number) {
  if (!run) return "等待开始";
  const start =
    typeof run.startedAt === "string" ? Date.parse(run.startedAt) : NaN;
  const end =
    typeof run.finishedAt === "string" ? Date.parse(run.finishedAt) : NaN;
  const seconds = Number.isFinite(start)
    ? Math.max(
        0,
        Math.floor(
          ((Number.isFinite(end) ? end : isResearchActive(run) ? now : start) -
            start) /
            1000,
        ),
      )
    : null;
  const duration =
    !isResearchActive(run) && typeof run.durationSeconds === "number"
      ? run.durationSeconds
      : seconds;
  if (duration === null) return "等待开始";
  return duration < 60
    ? `${Math.floor(duration)} 秒`
    : `${Math.floor(duration / 60)} 分 ${Math.floor(duration % 60)} 秒`;
}

export function researchReport(run: ResearchRun | null) {
  const report = run?.report;
  return report && typeof report === "object" && !Array.isArray(report)
    ? (report as Record<string, unknown>)
    : null;
}

export function researchSummary(run: ResearchRun | null) {
  const report = researchReport(run);
  return String(
    report?.executive_summary ||
      report?.executiveSummary ||
      run?.finalSummary ||
      "",
  );
}

export function researchSections(run: ResearchRun | null) {
  const raw = researchReport(run)?.sections;
  return Array.isArray(raw)
    ? raw
        .filter((item) => item && typeof item === "object")
        .map((item) => ({
          title: String(item.title || item.heading || "分析结果"),
          content: String(item.content || item.body || ""),
        }))
    : [];
}

export function researchVisibleList(
  run: ResearchRun | null,
  field: "recommendations" | "limitations",
) {
  const report = researchReport(run);
  if (field === "limitations" && report?.limitations_in_body === true)
    return [];
  const raw = report?.[field];
  const body = researchSections(run)
    .map((section) => section.content)
    .join("\n");
  return Array.isArray(raw)
    ? [
        ...new Set(raw.map((item) => String(item).trim()).filter(Boolean)),
      ].filter((item) => !body.includes(item))
    : [];
}

export function researchOutcome(run: ResearchRun | null) {
  const explicit = researchReport(run)?.outcome;
  if (["COMPLETE", "PARTIAL", "NEEDS_INPUT"].includes(String(explicit)))
    return String(explicit);
  const review = run?.reviewResult as
    { approved?: boolean; issues?: unknown[] } | undefined;
  return review?.approved === false &&
    Array.isArray(review.issues) &&
    review.issues.length
    ? "PARTIAL"
    : "COMPLETE";
}

export function researchMarkdown(run: ResearchRun | null) {
  const parts = [
    `# ${researchReport(run)?.title || "分析报告"}`,
    researchSummary(run),
    ...researchSections(run).map(
      (section) => `## ${section.title}\n\n${section.content}`,
    ),
  ];
  for (const [field, title] of [
    ["recommendations", "建议"],
    ["limitations", "限制与待确认事项"],
  ] as const) {
    const items = researchVisibleList(run, field);
    if (items.length)
      parts.push(`## ${title}`, ...items.map((item) => `- ${item}`));
  }
  return parts.filter(Boolean).join("\n\n");
}

export function researchErrorHelp(message: string) {
  if (/timeout|timed out|超时/i.test(message))
    return "模型或执行服务未在时限内返回。可检查模型连接，或缩小研究范围后重新分析。";
  if (/network|connect|chunked|网络|连接/i.test(message))
    return "模型连接中断。请在模型设置中测试连接，通过后可重新分析。";
  return "本次分析已停止，规划输入和已有记录仍保留。检查失败原因后可重新分析。";
}
