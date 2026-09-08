<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { AlertCircle, ArrowRight, CheckCircle2, Clock3, Pause, Play, RotateCcw, Search, Square } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { runsApi } from "@/api/runs";
import type { ResearchRun } from "@/api/types";

type QueueStatus = "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";
type QueueTask = {
  id: string;
  runId: string;
  title: string;
  status: QueueStatus;
  progress: number;
  currentStep: string;
  priority: "high" | "normal" | "low";
  source: string;
  projectName: string;
  time: string;
  duration: string;
  tokens: string;
};

const { router, routeTo, selectedProject, notify, workspaceId, projectId } = useWorkspace();
const tasks = ref<QueueTask[]>([]);
const searchQuery = ref("");
const statusFilter = ref<"all" | QueueStatus>("all");
const priorityFilter = ref("all");

const queueStatusLabelMap: Record<QueueStatus, string> = {
  queued: "等待中",
  running: "运行中",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};
function queueStatusLabel(status: QueueStatus) {
  return queueStatusLabelMap[status] || status;
}

function mapRun(run: ResearchRun): QueueTask {
  const rawStatus = String(run.status || "PENDING").toLowerCase();
  const status: QueueStatus =
    rawStatus === "running" ? "running"
    : rawStatus === "completed" ? "completed"
    : rawStatus === "failed" ? "failed"
    : rawStatus === "cancelled" ? "cancelled"
    : "queued";
  const rawPriority = String(run.priority || "NORMAL").toUpperCase();
  return {
    id: String(run.id),
    runId: String(run.id),
    title: String(run.title || run.goal || "未命名调研"),
    status,
    progress: Math.min(100, Math.max(0, Number(run.progress || 0))),
    currentStep: String(run.currentStep || ""),
    priority: rawPriority === "HIGH" ? "high" : rawPriority === "LOW" ? "low" : "normal",
    source: "research",
    projectName: selectedProject.value?.name || "—",
    time: String(run.updatedAt || run.createdAt || "—"),
    duration: String(run.duration || "—"),
    tokens: String(run.tokens || "—"),
  };
}

onMounted(async () => {
  try {
    tasks.value = (await runsApi.list(workspaceId.value, projectId.value)).map(mapRun);
  } catch (error) {
    notify(error instanceof Error ? error.message : "任务队列加载失败");
  }
});

const filteredTasks = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return tasks.value.filter((task) => {
    const matchesStatus = statusFilter.value === "all" || task.status === statusFilter.value;
    const matchesPriority = priorityFilter.value === "all" || task.priority === priorityFilter.value;
    const matchesQuery = !query || `${task.title} ${task.currentStep}`.toLowerCase().includes(query);
    return matchesStatus && matchesPriority && matchesQuery;
  });
});

const counts = computed(() => ({
  queued: tasks.value.filter((task) => task.status === "queued").length,
  running: tasks.value.filter((task) => task.status === "running").length,
  paused: tasks.value.filter((task) => task.status === "paused").length,
  completed: tasks.value.filter((task) => task.status === "completed").length,
  failed: tasks.value.filter((task) => ["failed", "cancelled"].includes(task.status)).length,
}));

function priorityLabel(priority: QueueTask["priority"]) {
  return priority === "high" ? "高" : priority === "low" ? "低" : "普通";
}

function statusClass(status: QueueStatus) {
  return `queue-status-${status}`;
}

function openTask(task: QueueTask) {
  router.push({ name: "project-run-detail", params: { ...routeTo("project-run-detail").params, runId: task.runId || task.id } });
}

async function retryTask(task: QueueTask) {
  try {
    const remote = await runsApi.retry(workspaceId.value, projectId.value, task.runId);
    Object.assign(task, mapRun(remote));
    notify("任务已重新排队");
  } catch (error) {
    notify(error instanceof Error ? error.message : "任务重试失败");
  }
}

async function cancelQueuedTask(task: QueueTask) {
  try {
    const remote = await runsApi.cancel(workspaceId.value, projectId.value, task.runId);
    Object.assign(task, mapRun(remote));
    notify("任务已取消");
  } catch (error) {
    notify(error instanceof Error ? error.message : "任务取消失败");
  }
}
</script>

<template>
  <PageHeader eyebrow="PROJECT / AGENT QUEUE" title="Agent 任务队列" :subtitle="`${selectedProject?.name || '暂无项目'} · 统一查看 Agent 的等待、执行和结果状态`">
  </PageHeader>

  <div class="queue-summary">
    <div class="queue-summary-card queue-summary-running"><span><Play :size="15" /></span><strong>{{ counts.running }}</strong><small>运行中</small></div>
    <div class="queue-summary-card queue-summary-queued"><span><Clock3 :size="15" /></span><strong>{{ counts.queued }}</strong><small>等待中</small></div>
    <div class="queue-summary-card queue-summary-paused"><span><Pause :size="15" /></span><strong>{{ counts.paused }}</strong><small>已暂停</small></div>
    <div class="queue-summary-card queue-summary-completed"><span><CheckCircle2 :size="15" /></span><strong>{{ counts.completed }}</strong><small>已完成</small></div>
    <div class="queue-summary-card queue-summary-failed"><span><AlertCircle :size="15" /></span><strong>{{ counts.failed }}</strong><small>失败/取消</small></div>
  </div>

  <section class="panel queue-panel">
    <div class="queue-panel-heading"><div><span class="eyebrow">TASK LIFECYCLE</span><h2>执行任务</h2><p>每个任务都会沿着规划、检索、核对和回答阶段推进。</p></div><span class="queue-live-note"><i />状态自动更新</span></div>
    <div class="queue-toolbar"><label class="queue-search"><Search :size="14" /><input v-model="searchQuery" type="search" aria-label="搜索任务" placeholder="搜索任务或当前步骤" /></label><select v-model="statusFilter" aria-label="筛选任务状态"><option value="all">全部状态</option><option value="queued">等待中</option><option value="running">运行中</option><option value="completed">已完成</option><option value="failed">失败</option><option value="cancelled">已取消</option></select><select v-model="priorityFilter" aria-label="筛选任务优先级"><option value="all">全部优先级</option><option value="high">高优先级</option><option value="normal">普通优先级</option><option value="low">低优先级</option></select></div>
    <div class="queue-table-wrap">
      <div class="queue-table queue-table-header"><span>任务</span><span>状态</span><span>进度</span><span>优先级</span><span>更新时间</span><span>操作</span></div>
      <div v-for="task in filteredTasks" :key="task.id" class="queue-table queue-table-row">
        <button class="queue-task-cell" type="button" @click="openTask(task)"><span class="queue-task-icon" :class="statusClass(task.status)"><Play v-if="task.status === 'running'" :size="13" /><Pause v-else-if="task.status === 'paused'" :size="13" /><CheckCircle2 v-else-if="task.status === 'completed'" :size="13" /><AlertCircle v-else :size="13" /></span><span><strong>{{ task.title }}</strong><small>调研任务 · {{ task.projectName }} · #{{ task.id }}</small></span></button>
        <span class="queue-status" :class="statusClass(task.status)"><i />{{ queueStatusLabel(task.status) }}</span>
        <div class="queue-progress-cell"><div class="queue-progress-top"><strong>{{ task.progress }}%</strong><small>{{ task.currentStep }}</small></div><div class="queue-progress-track"><i :style="{ width: `${task.progress}%` }" /></div></div>
        <span class="queue-priority" :class="`priority-${task.priority}`">{{ priorityLabel(task.priority) }}</span>
        <span class="queue-time">{{ task.time }}<small>{{ task.duration }} · {{ task.tokens }} tokens</small></span>
        <div class="queue-actions"><button v-if="['failed','cancelled'].includes(task.status)" class="icon-button small" type="button" aria-label="重试任务" @click.stop="retryTask(task)"><RotateCcw :size="14" /></button><button v-if="['queued','running'].includes(task.status)" class="icon-button small queue-cancel-button" type="button" aria-label="取消任务" @click.stop="cancelQueuedTask(task)"><Square :size="13" /></button><button class="icon-button small" type="button" aria-label="查看任务详情" @click.stop="openTask(task)"><ArrowRight :size="14" /></button></div>
      </div>
      <div v-if="!filteredTasks.length" class="queue-empty"><Clock3 :size="18" /><strong>没有匹配的任务</strong><span>请更换搜索或筛选条件。</span></div>
    </div>
  </section>

  <section class="queue-flow-card"><div><span class="queue-flow-icon"><Clock3 :size="16" /></span><div><strong>Agent 任务如何推进</strong><p>队列负责调度任务，右侧执行进度负责展示单个任务的实时事件；行动项则负责记录任务完成后的人工跟进。</p></div></div><div class="queue-flow-steps"><span>等待</span><b>→</b><span>规划</span><b>→</b><span>检索</span><b>→</b><span>核对证据</span><b>→</b><span>生成回答</span><b>→</b><span>完成</span></div></section>
</template>

<style scoped>
.queue-summary { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.75rem; margin-bottom:1rem; }.queue-summary-card { display:grid; grid-template-columns:1.75rem 1fr; grid-template-rows:1.125rem 1rem; column-gap:.5625rem; padding:.75rem .8125rem; border:.0625rem solid var(--workspace-border); border-radius:.625rem; background:var(--surface); }.queue-summary-card > span { grid-row:1 / -1; display:grid; place-items:center; width:1.75rem; height:1.75rem; border-radius:.5rem; }.queue-summary-card strong { color:var(--workspace-text); font-size:1rem; line-height:1.1; }.queue-summary-card small { color:var(--workspace-muted); font-size:.5625rem; }.queue-summary-running > span { color:#0c887a; background:#e1f7f3; }.queue-summary-queued > span { color:#6d7b85; background:#eef2f3; }.queue-summary-paused > span { color:#b7771d; background:#fff2dc; }.queue-summary-completed > span { color:#2f8b5e; background:#e7f7ee; }.queue-summary-failed > span { color:#b65b5b; background:#fff0f0; }
.queue-panel { overflow:hidden; }.queue-panel-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; padding:1.125rem 1.25rem .875rem; border-bottom:.0625rem solid var(--workspace-divider); }.queue-panel-heading h2 { margin:0; color:var(--workspace-text); font-size:.875rem; }.queue-panel-heading p { margin:.3125rem 0 0; color:var(--workspace-muted); font-size:.5625rem; }.queue-live-note { display:inline-flex; align-items:center; gap:.3125rem; color:var(--teal-dark); font-size:.5625rem; white-space:nowrap; }.queue-live-note i { width:.375rem; height:.375rem; border-radius:50%; background:var(--teal); box-shadow:0 0 0 .1875rem #dcf6f1; }.queue-toolbar { display:flex; align-items:center; gap:.625rem; padding:.75rem 1.25rem; border-bottom:.0625rem solid var(--workspace-divider); background:var(--surface-soft); }.queue-search { display:flex; align-items:center; gap:.375rem; min-width:16rem; flex:1; padding:.4375rem .5625rem; border:.0625rem solid var(--workspace-border); border-radius:.4375rem; background:var(--surface); color:var(--workspace-subtle); }.queue-search input { width:100%; border:0; outline:0; color:var(--workspace-text); background:transparent; font:inherit; font-size:.5625rem; }.queue-toolbar select { min-width:7.5rem; padding:.5rem .5625rem; border:.0625rem solid var(--workspace-border); border-radius:.4375rem; color:var(--workspace-muted); background:var(--surface); font:inherit; font-size:.5625rem; }.queue-table-wrap { overflow-x:auto; }.queue-table { display:grid; grid-template-columns:minmax(17rem,1.75fr) 5.5rem minmax(12rem,1.35fr) 4.5rem 7.5rem 7.25rem; gap:.75rem; align-items:center; min-width:54rem; padding:0 1.25rem; }.queue-table-header { min-height:2.5rem; color:var(--workspace-subtle); border-bottom:.0625rem solid var(--workspace-divider); font-size:.5rem; }.queue-table-row { min-height:4.75rem; border-bottom:.0625rem solid var(--workspace-divider); }.queue-table-row:last-child { border-bottom:0; }.queue-task-cell { display:flex; align-items:center; min-width:0; gap:.5625rem; padding:0; border:0; background:transparent; text-align:left; cursor:pointer; }.queue-task-icon { display:grid; place-items:center; width:1.875rem; height:1.875rem; flex:0 0 auto; border-radius:.5625rem; }.queue-task-cell > span:last-child { display:grid; min-width:0; gap:.25rem; }.queue-task-cell strong,.queue-task-cell small { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.queue-task-cell strong { color:var(--workspace-text); font-size:.625rem; }.queue-task-cell small { color:var(--workspace-muted); font-size:.5rem; }.queue-status,.queue-priority { display:inline-flex; align-items:center; gap:.3125rem; font-size:.5625rem; white-space:nowrap; }.queue-status i { width:.375rem; height:.375rem; border-radius:50%; background:currentColor; }.queue-status-running,.queue-status-completed { color:var(--teal-dark); }.queue-status-queued { color:#78868c; }.queue-status-paused { color:#b4771e; }.queue-status-failed,.queue-status-cancelled { color:#b65b5b; }.queue-progress-cell { min-width:0; }.queue-progress-top { display:flex; align-items:center; justify-content:space-between; gap:.375rem; margin-bottom:.3125rem; }.queue-progress-top strong { color:var(--teal-dark); font-size:.5625rem; }.queue-progress-top small { overflow:hidden; color:var(--workspace-muted); font-size:.5rem; text-overflow:ellipsis; white-space:nowrap; }.queue-progress-track { height:.25rem; overflow:hidden; border-radius:999px; background:var(--workspace-divider); }.queue-progress-track i { display:block; height:100%; border-radius:inherit; background:var(--teal); transition:width .3s ease; }.queue-priority { justify-content:center; width:max-content; padding:.25rem .375rem; border-radius:.3125rem; }.priority-high { color:#b65b5b; background:#fff0f0; }.priority-normal { color:#75828a; background:#eef2f3; }.priority-low { color:#56836d; background:#eaf7ef; }.queue-time { display:grid; gap:.25rem; color:var(--workspace-muted); font-size:.5625rem; }.queue-time small { color:var(--workspace-subtle); font-size:.5rem; }.queue-actions { display:flex; align-items:center; justify-content:flex-end; gap:.3125rem; }.queue-cancel-button:hover { color:#b65b5b; border-color:#e2b7b7; }.queue-status-running { background:#e1f7f3; color:#0c887a; }.queue-status-completed { background:#e7f7ee; color:#2f8b5e; }.queue-status-failed,.queue-status-cancelled { background:#fff0f0; color:#b65b5b; }.queue-status-queued { background:#eef2f3; color:#78868c; }.queue-status-paused { background:#fff2dc; color:#b7771e; }.queue-task-icon.queue-status-running,.queue-task-icon.queue-status-completed,.queue-task-icon.queue-status-failed,.queue-task-icon.queue-status-cancelled,.queue-task-icon.queue-status-queued,.queue-task-icon.queue-status-paused { background:color-mix(in oklab,currentColor 12%,var(--surface)); }.queue-empty { display:grid; justify-items:center; gap:.375rem; padding:3rem 1rem; color:var(--workspace-subtle); }.queue-empty strong { color:var(--workspace-muted); font-size:.6875rem; }.queue-empty span { font-size:.5625rem; }.queue-flow-card { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-top:1rem; padding:.875rem 1rem; border:.0625rem solid var(--workspace-border); border-radius:.625rem; background:linear-gradient(110deg,color-mix(in oklab,var(--teal) 6%,var(--surface)),var(--surface)); }.queue-flow-card > div:first-child { display:flex; align-items:flex-start; gap:.5625rem; }.queue-flow-icon { display:grid; place-items:center; width:1.875rem; height:1.875rem; flex:0 0 auto; border-radius:.5rem; color:var(--teal-dark); background:#e2f7f3; }.queue-flow-card strong,.queue-flow-card p { display:block; }.queue-flow-card strong { color:var(--workspace-text); font-size:.625rem; }.queue-flow-card p { max-width:34rem; margin:.25rem 0 0; color:var(--workspace-muted); font-size:.5625rem; line-height:1.45; }.queue-flow-steps { display:flex; align-items:center; gap:.375rem; color:var(--teal-dark); font-size:.5rem; white-space:nowrap; }.queue-flow-steps b { color:var(--workspace-subtle); font-weight:400; }
@media (max-width:68.75rem) { .queue-summary { grid-template-columns:repeat(3,minmax(0,1fr)); }.queue-flow-card { align-items:flex-start; flex-direction:column; }.queue-flow-steps { flex-wrap:wrap; white-space:normal; } }
@media (max-width:47.5rem) { .queue-summary { grid-template-columns:repeat(2,minmax(0,1fr)); }.queue-panel-heading { align-items:flex-start; flex-direction:column; }.queue-toolbar { align-items:stretch; flex-direction:column; }.queue-search { min-width:0; }.queue-toolbar select { width:100%; }.queue-flow-steps { line-height:1.8; } }
.queue-summary-running > span,.queue-flow-icon{color:var(--teal-dark);background:color-mix(in oklab,var(--teal) 13%,var(--surface))}.queue-summary-queued > span,.priority-normal,.queue-status-queued{color:var(--workspace-muted);background:var(--surface-soft)}.queue-summary-paused > span,.priority-high,.queue-status-paused{color:#c58a32;background:color-mix(in oklab,#d7962a 14%,var(--surface))}.queue-summary-completed > span,.priority-low,.queue-status-completed{color:var(--teal-dark);background:color-mix(in oklab,var(--teal) 13%,var(--surface))}.queue-summary-failed > span,.queue-status-failed,.queue-status-cancelled{color:#d27878;background:color-mix(in oklab,#dc7171 14%,var(--surface))}.queue-live-note i{box-shadow:0 0 0 .1875rem color-mix(in oklab,var(--teal) 14%,transparent)}
</style>
