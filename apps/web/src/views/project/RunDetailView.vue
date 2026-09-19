<script setup lang="ts">
import { ArrowLeft, Copy, FileText, Pause, Play, Plus, X } from "@lucide/vue";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useWorkspace } from "@/composables/useWorkspace";
import { runsApi } from "@/api/runs";
import type { ResearchPlanStep } from "@/api/types";
import PageHeader from "@/components/common/PageHeader.vue";
import { formatDateTime } from "@/lib/utils";
const router = useRouter();
const route = useRoute();
const {
  notify,
  statusClass,
  statusLabel,
  workspaceId,
  projectId,
} = useWorkspace();
const selectedEvidence = ref(-1);

type RunInfo = {
  id: string;
  title: string;
  project: string;
  status: string;
  statusLabel: string;
  time: string;
  goal: string;
  duration: string;
  tokens: string;
  progress: number;
  errorMessage: string;
  planVersion: number;
  paused: boolean;
};

const run = ref<RunInfo>({
  id: String(route.params.runId),
  title: "调研任务",
  project: "—",
  status: "pending",
  statusLabel: "等待执行",
  time: "",
  goal: "",
  duration: "—",
  tokens: "—",
  progress: 0,
  errorMessage: "",
  planVersion: 0,
  paused: false,
});

const plan = ref<ResearchPlanStep[]>([]);
const planSummary = ref("");
const planVersion = ref(0);
const planSaving = ref(false);
const newStep = ref({ objective: "", action: "SEARCH_INTERNAL" as ResearchPlanStep["action"], query: "" });

type EvidenceItem = {
  code: string;
  title: string;
  source: string;
  assetId: string;
  excerpt: string;
  pageNumber: number | string | null;
};
const evidence = ref<EvidenceItem[]>([]);
const evidenceExcerpt = ref("");
const copied = ref(false);

const metrics = computed(() => [
  { label: "当前状态", value: run.value.statusLabel },
  { label: "执行进度", value: `${run.value.progress}%` },
  { label: "运行时长", value: run.value.duration },
  { label: "消耗 Tokens", value: run.value.tokens },
]);

const summaryText = computed(() => {
  if (run.value.status === "failed")
    return run.value.errorMessage || "调研执行失败，可以在任务队列中重试。";
  if (run.value.goal) return `调研目标：${run.value.goal}`;
  return "调研完成后，这里会展示结论摘要。";
});

function selectEvidence(index: number) {
  const item = evidence.value[index];
  if (!item) return;
  selectedEvidence.value = index;
  evidenceExcerpt.value = item.excerpt || "当前证据没有可展示的摘录。";
}

async function copySelectedEvidence() {
  if (!evidenceExcerpt.value) return;
  try {
    await navigator.clipboard.writeText(evidenceExcerpt.value);
    copied.value = true;
    window.setTimeout(() => {
      copied.value = false;
    }, 1800);
  } catch {
    notify("复制失败，请手动选择引用内容");
  }
}

onMounted(async () => {
  const runId = String(route.params.runId);
  try {
    const [detail] = await Promise.all([
      runsApi.detail(workspaceId.value, projectId.value, runId),
    ]);
    const status = String(detail.status || "PENDING").toLowerCase();
    run.value = {
      id: String(detail.id ?? runId),
      title: String(detail.title || detail.goal || "未命名调研"),
      project: "—",
      status,
      statusLabel: statusLabel(status),
      time: formatDateTime(detail.updatedAt || detail.createdAt, ""),
      goal: String(detail.goal || ""),
      duration: String(detail.duration || "—"),
      tokens: String(detail.tokens || "—"),
      progress: Math.min(100, Math.max(0, Number(detail.progress || 0))),
      errorMessage: String(detail.errorMessage || ""),
      planVersion: Number(detail.planVersion || 0),
      paused: Boolean(detail.paused),
    };
    const rawPlan = (detail.plan || {}) as { summary?: string; steps?: ResearchPlanStep[] };
    plan.value = Array.isArray(rawPlan.steps) ? rawPlan.steps.map((step) => ({ ...step })) : [];
    planSummary.value = String(rawPlan.summary || "");
    planVersion.value = Number(detail.planVersion || 0);
    const detailRecord = detail as unknown as Record<string, unknown>;
    const rawEvidence = Array.isArray(detailRecord.evidence)
      ? detailRecord.evidence
      : [];
    evidence.value = rawEvidence.map((raw, index) => {
      const item = (raw || {}) as Record<string, unknown>;
      const sourceName = String(item.source_name ?? item.sourceName ?? item.asset_name ?? item.assetName ?? "项目资料");
      const pageNumber = (item.page_number ?? item.pageNumber ?? null) as number | string | null;
      const pageLabel = pageNumber != null && String(pageNumber) !== "" ? `第${pageNumber}页` : "";
      return {
        code: String(item.id ?? item.chunk_id ?? item.chunkId ?? `E${String(index + 1).padStart(2, "2")}`),
        title: String(item.section_title ?? item.sectionTitle ?? item.asset_name ?? item.assetName ?? sourceName),
        source: [sourceName, pageLabel].filter(Boolean).join(" · "),
        assetId: String(item.asset_id ?? item.assetId ?? ""),
        excerpt: String(item.content ?? item.excerpt ?? ""),
        pageNumber,
      };
    });
  } catch (error) {
    notify(error instanceof Error ? error.message : "运行详情加载失败");
  }
});

async function appendPlanStep() {
  const objective = newStep.value.objective.trim();
  if (!objective || planSaving.value) return;
  planSaving.value = true;
  try {
    const response = await runsApi.updatePlan(workspaceId.value, projectId.value, String(route.params.runId), {
      mode: "APPEND",
      expectedVersion: planVersion.value,
      steps: [{ id: `U${Date.now()}`, objective, action: newStep.value.action, query: newStep.value.query.trim() || objective }],
    });
    const updated = (response.plan || {}) as { summary?: string; steps?: ResearchPlanStep[] };
    plan.value = Array.isArray(updated.steps) ? updated.steps : plan.value;
    planSummary.value = String(updated.summary || planSummary.value);
    planVersion.value = Number(response.planVersion || planVersion.value + 1);
    newStep.value = { objective: "", action: "SEARCH_INTERNAL", query: "" };
    notify("计划步骤已加入，任务会在下一个安全检查点执行");
  } catch (error) {
    notify(error instanceof Error ? error.message : "计划更新失败，可能已被其他人修改");
  } finally {
    planSaving.value = false;
  }
}

async function togglePlanPause() {
  if (planSaving.value) return;
  planSaving.value = true;
  try {
    const response = await runsApi.updatePlan(workspaceId.value, projectId.value, String(route.params.runId), {
      mode: run.value.paused ? "RESUME" : "PAUSE",
      expectedVersion: planVersion.value,
    });
    run.value.paused = Boolean(response.paused);
    notify(run.value.paused ? "任务已请求暂停" : "任务已恢复执行");
  } catch (error) {
    notify(error instanceof Error ? error.message : "任务控制失败");
  } finally {
    planSaving.value = false;
  }
}

function exportSummary() {
  const content = `# ${run.value.title}\n\n${summaryText.value}\n`;
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${run.value.title}.md`;
  link.click();
  URL.revokeObjectURL(url);
  notify("摘要已导出");
}
</script>

<template>
  <button class="text-button back-button" type="button" @click="router.back()">
    <ArrowLeft :size="15" />返回 Agent 任务队列
  </button>
  <PageHeader
    eyebrow="AGENT / TASK DETAIL"
    :title="run.title"
    :subtitle="`${run.id} · ${run.project} · ${run.time}`"
  >
    <template #action>
      <span class="status-badge" :class="statusClass(run.status)"><i />{{ run.statusLabel }}</span>
    </template>
  </PageHeader>
  <div class="run-metrics">
    <div v-for="metric in metrics" :key="metric.label">
      <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong>
    </div>
  </div>
  <div class="research-workspace">
    <section class="panel markdown-body">
      <p class="eyebrow">FINAL SUMMARY</p>
      <h2>结论摘要</h2>
      <p>{{ summaryText }}</p>
      <button
        class="button button-secondary button-sm"
        type="button"
        @click="exportSummary"
      >
        <FileText :size="14" />导出摘要
      </button>
    </section>
    <aside class="panel evidence-panel">
      <div class="panel-heading">
        <div>
          <h2>证据与来源</h2>
          <p>点击证据查看引用片段</p>
        </div>
      </div>
      <button
        v-for="(item, index) in evidence"
        :key="item.code"
        class="evidence-card"
        :class="{ selected: selectedEvidence === index }"
        type="button"
        @click="selectEvidence(index)"
      >
        <div>
          <span class="evidence-code">{{ item.code }}</span
          ><strong>{{ item.title }}</strong>
        </div>
        <small>{{ item.source }}</small>
      </button>
      <p v-if="!evidence.length" class="empty-state">知识库暂无可引用资料。</p>
      <div v-if="selectedEvidence >= 0" class="evidence-drawer">
        <div>
          <span class="eyebrow">EVIDENCE</span>
          <h2>{{ evidence[selectedEvidence]?.title }}</h2>
          <p>
            {{ evidenceExcerpt }}
          </p>
        </div>
        <div>
          <button
            class="button button-secondary button-sm"
            type="button"
            @click="copySelectedEvidence"
          >
            <Copy :size="14" />{{ copied ? "已复制" : "复制引用" }}</button
          ><button
            class="icon-button small"
            type="button"
            @click="selectedEvidence = -1"
          >
            <X :size="17" />
          </button>
        </div>
      </div>
    </aside>
  </div>
  <section class="panel run-plan-panel">
    <div class="panel-heading">
      <div><span class="eyebrow">VERSIONED PLAN</span><h2>执行计划 <small>v{{ planVersion }}</small></h2><p>{{ planSummary || "计划由 Agent 根据目标自动生成，可在运行中追加。" }}</p></div>
      <button class="button button-secondary button-sm" type="button" :disabled="planSaving || !['running','pending','paused'].includes(run.status)" @click="togglePlanPause"><Play v-if="run.paused" :size="14" /><Pause v-else :size="14" />{{ run.paused ? "继续执行" : "暂停任务" }}</button>
    </div>
    <div class="run-plan-list">
      <div v-for="(step, index) in plan" :key="step.id" class="run-plan-step"><span>{{ index + 1 }}</span><div><strong>{{ step.objective }}</strong><small>{{ step.action }} · {{ step.query || "无需查询" }}</small></div></div>
      <p v-if="!plan.length" class="empty-state">计划将在任务开始后生成。</p>
    </div>
    <form class="run-plan-form" @submit.prevent="appendPlanStep">
      <input v-model="newStep.objective" type="text" maxlength="500" placeholder="追加一个研究步骤，例如：核对竞品定价" aria-label="追加计划步骤" />
      <select v-model="newStep.action" aria-label="计划动作"><option value="SEARCH_INTERNAL">项目资料</option><option value="SEARCH_GRAPH">知识图谱</option><option value="SEARCH_WEB">外部搜索</option><option value="SYNTHESIZE">整理结论</option></select>
      <input v-model="newStep.query" type="text" maxlength="2000" placeholder="查询语句（可选）" aria-label="计划查询语句" />
      <button class="button button-primary button-sm" type="submit" :disabled="planSaving || !newStep.objective.trim()"><Plus :size="14" />追加</button>
    </form>
  </section>
</template>

<style scoped>
.run-detail-top {
  align-items: center;
}
.run-detail-top h1 {
  font-size: 1.5rem;
}
.run-meta {
  gap: 0.875rem;
  margin-top: 0.6875rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.run-metrics {
  display: flex;
  gap: 0;
  background: var(--surface);
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  margin-bottom: 1.125rem;
}
.run-metrics div {
  padding: 0.9375rem 1.5rem;
  min-width: 8.75rem;
  border-right: 0.0625rem solid var(--workspace-divider);
}
.run-metrics div:last-child {
  border-right: 0;
}
.run-metrics span,
.run-metrics strong {
  display: block;
}
.run-metrics span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.run-metrics strong {
  color: var(--workspace-text);
  font-size: 1.0625rem;
  margin-top: 0.375rem;
}
.research-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(18rem, 0.85fr);
  gap: 0.9375rem;
  align-items: start;
}
.run-plan-panel { margin-top: 0.9375rem; }
.run-plan-panel h2 { display:flex; align-items:center; gap:.375rem; margin:0; color:var(--workspace-text); font-size:.875rem; }
.run-plan-panel h2 small { color:var(--teal-dark); font-size:.7rem; font-weight:500; }
.run-plan-panel p { margin:.3125rem 0 0; color:var(--workspace-muted); font-size:.75rem; }
.run-plan-list { display:grid; gap:.5rem; padding:0 1.25rem 1rem; }
.run-plan-step { display:flex; align-items:center; gap:.625rem; padding:.625rem .75rem; border:.0625rem solid var(--workspace-divider); border-radius:.5rem; background:var(--surface-soft); }
.run-plan-step > span { display:grid; place-items:center; width:1.5rem; height:1.5rem; flex:0 0 auto; border-radius:50%; color:var(--teal-dark); background:color-mix(in oklab,var(--teal) 14%,var(--surface)); font-size:.7rem; }
.run-plan-step div { display:grid; min-width:0; gap:.2rem; }.run-plan-step strong { color:var(--workspace-text); font-size:.75rem; }.run-plan-step small { overflow:hidden; color:var(--workspace-muted); font-size:.7rem; text-overflow:ellipsis; white-space:nowrap; }
.run-plan-form { display:grid; grid-template-columns:1.1fr 8rem 1.1fr auto; gap:.5rem; padding:1rem 1.25rem; border-top:.0625rem solid var(--workspace-divider); background:var(--surface-soft); }
.run-plan-form input,.run-plan-form select { min-width:0; padding:.5rem .625rem; border:.0625rem solid var(--workspace-border); border-radius:.4375rem; color:var(--workspace-text); background:var(--surface); font:inherit; font-size:.75rem; outline:0; }
@media (max-width:47.5rem) { .run-plan-form { grid-template-columns:1fr; } }
.timeline-panel,
.event-panel,
.evidence-panel {
  min-height: 28.75rem;
}
.live-indicator {
  color: var(--teal-dark);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
}
.live-indicator i {
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 0.25rem #e1f6f3;
}
.timeline {
  padding: 0.5625rem 1.375rem;
}
.timeline-item {
  position: relative;
  display: flex;
  gap: 0.625rem;
  min-height: 4.3125rem;
}
.timeline-item:not(:last-child)::before {
  content: "";
  position: absolute;
  left: 0.5rem;
  top: 1.25rem;
  height: calc(100% - 0.375rem);
  border-left: 0.0625rem solid var(--workspace-divider);
}
.timeline-marker {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 1.0625rem;
  height: 1.0625rem;
  border-radius: 50%;
  color: white;
  background: #e1e9e9;
  flex: 0 0 auto;
}
.timeline-item.done .timeline-marker {
  background: var(--teal);
}
.timeline-item.active .timeline-marker {
  background: #fff6e4;
  border: 0.0625rem solid #e8a93e;
}
.timeline-item.active .timeline-marker span {
  width: 0.3125rem;
  height: 0.3125rem;
  border-radius: 50%;
  background: #e8a93e;
}
.timeline-copy {
  padding-top: 0.0625rem;
}
.timeline-copy strong,
.timeline-copy small {
  display: block;
}
.timeline-copy strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.timeline-item.active .timeline-copy strong {
  color: #b4771e;
}
.timeline-copy small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.5;
  margin-top: 0.3125rem;
}
.step-spinner {
  margin-left: auto;
  color: #d79a2d;
  animation: spin 1.2s linear infinite;
}
.event-list {
  padding: 0.3125rem 1.375rem 1.25rem;
}
.event-row {
  display: grid;
  grid-template-columns: 2.875rem 1.6875rem 1fr;
  gap: 0.5rem;
  padding: 0.8125rem 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.event-row:last-child {
  border-bottom: 0;
}
.event-time {
  color: var(--workspace-muted);
  font:
    0.5625rem ui-monospace,
    monospace;
  padding-top: 0.3125rem;
}
.event-icon {
  width: 1.6875rem;
  height: 1.6875rem;
  border-radius: 0.4375rem;
  display: grid;
  place-items: center;
}
.gray-bg {
  background: #f0f3f3;
  color: #87979c;
}
.event-row strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.event-row p {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  margin: 0.3125rem 0 0;
  line-height: 1.5;
}
.evidence-list {
  padding: 0.25rem 0.875rem 1.125rem;
}
.evidence-card {
  width: 100%;
  display: block;
  border: 0.0625rem solid transparent;
  background: transparent;
  border-radius: 0.5rem;
  text-align: left;
  padding: 0.75rem 0.5625rem;
  cursor: pointer;
}
.evidence-card:hover,
.evidence-card.selected {
  background: color-mix(in oklab, var(--teal) 8%, var(--surface));
  border-color: color-mix(in oklab, var(--teal) 24%, var(--workspace-border));
}
.evidence-card > div {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
}
.evidence-code {
  display: inline-grid;
  place-items: center;
  width: 1.4375rem;
  height: 1.1875rem;
  color: var(--teal-dark);
  background: #ddf4ef;
  border-radius: 0.25rem;
  font:
    800 0.5625rem ui-monospace,
    monospace;
}
.evidence-code.conflict {
  color: #b06e17;
  background: #fff0d8;
}
.evidence-card strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.evidence-card small,
.evidence-card p {
  display: block;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  margin: 0.4375rem 0 0;
}
.evidence-card p {
  line-height: 1.55;
  color: var(--workspace-muted);
}
.evidence-drawer {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  z-index: 30;
  width: min(35rem, calc(100vw - 3rem));
  display: flex;
  justify-content: space-between;
  gap: 1.125rem;
  background: #173c3a;
  color: white;
  padding: 1.0625rem 1.125rem;
  border-radius: 0.625rem;
  box-shadow: 0 1rem 2.5rem rgba(17, 58, 56, 0.25);
}
.evidence-drawer .eyebrow {
  color: #81dbce;
  margin-bottom: 0.5rem;
}
.evidence-drawer h2 {
  font-size: 0.75rem;
  margin: 0;
}
.evidence-drawer p {
  color: #b8d9d5;
  font:
    0.625rem/1.6 Georgia,
    serif;
  margin: 0.5rem 0;
}
.evidence-drawer small {
  color: #8ab4af;
  font-size: 0.75rem;
}
.evidence-drawer > div:last-child {
  display: flex;
  align-items: flex-start;
  gap: 0.4375rem;
}
.evidence-drawer .button-secondary {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.13);
  color: white;
}

@media (max-width: 47.5rem) {
  .run-detail-top {
    align-items: flex-start;
    flex-direction: column;
  }

  .run-metrics {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .run-metrics div {
    min-width: 0;
    border-bottom: 0.0625rem solid #edf1f1;
  }

  .run-metrics div:nth-child(2) {
    border-right: 0;
  }

  .run-metrics div:nth-child(3),
  .run-metrics div:nth-child(4) {
    border-bottom: 0;
  }

  .research-workspace {
    grid-template-columns: 1fr;
  }

  .timeline-panel,
  .event-panel,
  .evidence-panel {
    min-height: auto;
  }

  .evidence-drawer {
    right: 0.75rem;
    bottom: 0.75rem;
    width: calc(100vw - 1.5rem);
  }
}
</style>
