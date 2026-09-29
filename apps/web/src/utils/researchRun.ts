import type { ResearchRun } from "../api/types.ts";

export type ResearchEvent = {
  id: string | number; type: string; timestamp: string;
  node?: string; title?: string; detail?: string;
  task?: { id: string; title: string; status: string; summary?: string; error?: string; startedAt?: string; durationMs?: number };
};

export const researchStages = [
  { title: "理解目标", nodes: ["VALIDATE_INPUT", "PLAN"], description: "梳理目标、约束与成功指标，生成研究计划" },
  { title: "搜集证据", nodes: ["RETRIEVE_INTERNAL", "EVALUATE_EVIDENCE", "REWRITE_QUERY", "SEARCH_WEB"], description: "检索项目资料，检查相关性与证据缺口" },
  { title: "形成方案", nodes: ["SYNTHESIZE_FINDINGS", "WRITE_REPORT"], description: "综合证据，整理方案、风险与建议" },
  { title: "核验结果", nodes: ["REVIEW_REPORT", "PERSIST_RESULT", "END"], description: "核对引用和结论，保存报告供人工审查" },
];

export function isResearchActive(run: ResearchRun | null) {
  return !!run && ["PENDING", "QUEUED", "RUNNING", "PAUSED", "CANCELLING"].includes(String(run.status).toUpperCase());
}

export function researchEvents(run: ResearchRun | null): ResearchEvent[] {
  return Array.isArray(run?.events) ? run.events as ResearchEvent[] : [];
}

export function researchStageIndex(run: ResearchRun | null) {
  if (!run) return -1;
  const observed = researchEvents(run).filter(event => event.node);
  const node = ["FAILED", "CANCELLED"].includes(String(run.currentNode))
    ? observed.at(-1)?.node : run.currentNode || observed.at(-1)?.node;
  if (String(run.status).toUpperCase() === "COMPLETED") return researchStages.length;
  return researchStages.findIndex(stage => stage.nodes.includes(String(node)));
}

export function researchElapsed(run: ResearchRun | null, now: number) {
  if (!run) return "等待开始";
  const start = typeof run.startedAt === "string" ? Date.parse(run.startedAt) : NaN;
  const end = typeof run.finishedAt === "string" ? Date.parse(run.finishedAt) : NaN;
  const seconds = Number.isFinite(start)
    ? Math.max(0, Math.floor(((Number.isFinite(end) ? end : isResearchActive(run) ? now : start) - start) / 1000))
    : null;
  const duration = !isResearchActive(run) && typeof run.durationSeconds === "number" ? run.durationSeconds : seconds;
  if (duration === null) return "等待开始";
  return duration < 60 ? `${Math.floor(duration)} 秒` : `${Math.floor(duration / 60)} 分 ${Math.floor(duration % 60)} 秒`;
}

export function researchReport(run: ResearchRun | null) {
  const report = run?.report;
  return report && typeof report === "object" && !Array.isArray(report) ? report as Record<string, unknown> : null;
}

export function researchSummary(run: ResearchRun | null) {
  const report = researchReport(run);
  return String(report?.executive_summary || report?.executiveSummary || run?.finalSummary || "");
}

export function researchErrorHelp(message: string) {
  if (/timeout|timed out|超时/i.test(message)) return "模型或执行服务未在时限内返回。可检查模型连接，或缩小研究范围后重新分析。";
  if (/network|connect|chunked|网络|连接/i.test(message)) return "模型连接中断。请在模型设置中测试连接，通过后可重新分析。";
  return "本次分析已停止，规划输入和已有记录仍保留。检查失败原因后可重新分析。";
}
