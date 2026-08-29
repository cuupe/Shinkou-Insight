<script setup lang="ts">
import { ArrowLeft, Copy, FileText, X } from "@lucide/vue";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useWorkspace } from "@/composables/useWorkspace";
import { runsApi } from "@/api/runs";
import PageHeader from "@/components/common/PageHeader.vue";
const router = useRouter();
const route = useRoute();
const {
  copied,
  copyEvidence,
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
});

type EvidenceItem = {
  code: string;
  title: string;
  source: string;
  assetId: string;
};
const evidence = ref<EvidenceItem[]>([]);
const evidenceExcerpt = ref("");
const evidenceLoading = ref(false);

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
  selectedEvidence.value = index;
  evidenceExcerpt.value = "当前运行没有后端返回的证据片段。";
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
      time: String(detail.updatedAt || detail.createdAt || ""),
      goal: String(detail.goal || ""),
      duration: String(detail.duration || "—"),
      tokens: String(detail.tokens || "—"),
      progress: Math.min(100, Math.max(0, Number(detail.progress || 0))),
      errorMessage: String(detail.errorMessage || ""),
    };
  } catch (error) {
    notify(error instanceof Error ? error.message : "运行详情加载失败");
  }
});

function generateReport() {
  const content = `# ${run.value.title}\n\n${summaryText.value}\n`;
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${run.value.title}.md`;
  link.click();
  URL.revokeObjectURL(url);
  notify("报告已生成并下载");
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
  <div v-if="false" class="run-detail-top">
    <div>
      <p class="eyebrow">AGENT / TASK DETAIL</p>
      <h1>{{ run.title }}</h1>
      <p class="page-subtitle">
        {{ run.id }} · {{ run.project }} · {{ run.time }}
      </p>
    </div>
    <span class="status-badge" :class="statusClass(run.status)"><i />{{ run.statusLabel }}</span>
  </div>
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
        @click="generateReport"
      >
        <FileText :size="14" />生成报告
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
            {{ evidenceLoading ? "正在加载引用片段…" : evidenceExcerpt }}
          </p>
        </div>
        <div>
          <button
            class="button button-secondary button-sm"
            type="button"
            @click="copyEvidence"
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
  font-size: 0.625rem;
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
  font-size: 0.5625rem;
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
.timeline-panel,
.event-panel,
.evidence-panel {
  min-height: 28.75rem;
}
.live-indicator {
  color: var(--teal-dark);
  font-size: 0.5rem;
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
  font-size: 0.625rem;
}
.timeline-item.active .timeline-copy strong {
  color: #b4771e;
}
.timeline-copy small {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
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
  font-size: 0.625rem;
}
.event-row p {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
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
  font-size: 0.625rem;
}
.evidence-card small,
.evidence-card p {
  display: block;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
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
