<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ArrowLeft, ArrowRight, Check, CircleAlert, Clock3, Copy, Database, FileText, LoaderCircle, Pause, Play, Plus, RefreshCw, Square } from "@lucide/vue";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "@/components/common/PageHeader.vue";
import ProjectWorkflow from "@/components/project/ProjectWorkflow.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { useResearchRun } from "@/composables/useResearchRun";
import { runsApi } from "@/api/runs";
import type { ResearchPlanStep } from "@/api/types";
import { researchElapsed, researchErrorHelp, researchEvents, researchReport, researchStageIndex, researchStages, researchSummary } from "@/utils/researchRun";

const router = useRouter();
const route = useRoute();
const { notify, routeTo, selectedProject, workspaceId, projectId } = useWorkspace();
const { run, active, loading, error, lastSynced, now, refresh } = useResearchRun();
const busy = ref(false);
const selectedEvidence = ref("");
const newStep = ref({ objective: "", action: "SEARCH_INTERNAL" as ResearchPlanStep["action"], query: "" });
const status = computed(() => String(run.value?.status || "PENDING").toUpperCase());
const labels: Record<string, string> = { PENDING: "等待执行", QUEUED: "排队中", RUNNING: "分析中", PAUSED: "已请求暂停", CANCELLING: "正在取消", COMPLETED: "分析完成", FAILED: "分析失败", CANCELLED: "已取消" };
const statusText = computed(() => labels[status.value] || status.value);
const progress = computed(() => Math.min(100, Math.max(0, Number(run.value?.progress) || 0)));
const events = computed(() => researchEvents(run.value));
const latestWait = computed(() => [...events.value].reverse().find(event => event.type === "node.waiting" && (!event.node || event.node === run.value?.currentNode))?.detail || "");
const stageIndex = computed(() => researchStageIndex(run.value));
const elapsed = computed(() => researchElapsed(run.value, now.value));
const planData = computed(() => run.value?.plan as { summary?: string; steps?: ResearchPlanStep[] } | undefined);
const plan = computed(() => Array.isArray(planData.value?.steps) ? planData.value.steps : []);
const report = computed(() => researchReport(run.value));
const summary = computed(() => researchSummary(run.value));
const reportSections = computed(() => Array.isArray(report.value?.sections) ? report.value.sections as { title?: string; content?: string }[] : []);
const recommendations = computed(() => Array.isArray(report.value?.recommendations) ? report.value.recommendations : []);
const limitations = computed(() => Array.isArray(report.value?.limitations) ? report.value.limitations : []);
const editable = computed(() => active.value && status.value !== "CANCELLING");
const disconnected = computed(() => Boolean(error.value) || run.value?.runtimeAvailable === false);
const sinceActivity = computed(() => {
  const timestamp = run.value?.lastActivityAt || events.value.at(-1)?.timestamp || run.value?.startedAt;
  return typeof timestamp === "string" ? Math.max(0, Math.floor((now.value - Date.parse(timestamp)) / 1000)) : 0;
});
const waiting = computed(() => active.value && status.value !== "PAUSED" && sinceActivity.value >= 30);
const tasks = computed(() => {
  const result = new Map<string, NonNullable<(typeof events.value)[number]["task"]>>();
  for (const event of events.value) if (event.task) result.set(event.task.id, event.task);
  return [...result.values()].map(task => ({ ...task,
    status: !active.value && ["pending", "running"].includes(task.status) ? "interrupted" : task.status,
  }));
});
const activityTitle = computed(() => {
  if (disconnected.value) return "暂时无法同步分析状态";
  if (status.value === "FAILED") return "本次分析未完成";
  if (status.value === "COMPLETED") return "分析已完成，可以检查结论与证据";
  if (status.value === "CANCELLED") return "本次分析已取消";
  if (status.value === "PAUSED") return "已请求暂停，将在当前步骤结束后等待";
  return String(run.value?.currentStep || "等待分析服务接收任务");
});
const evidence = computed(() => {
  const raw = Array.isArray(run.value?.evidence) ? run.value.evidence as Record<string, unknown>[] : [];
  return raw.map((item, index) => ({
    id: String(item.id || item.chunk_id || index),
    title: String(item.source_name || item.sourceName || item.asset_name || "项目资料"),
    section: String(item.section_title || item.sectionTitle || ""),
    excerpt: String(item.content || item.excerpt || ""),
    page: item.page_number || item.pageNumber,
  }));
});
const selected = computed(() => evidence.value.find(item => item.id === selectedEvidence.value));
const errorMessage = computed(() => String(run.value?.errorMessage || "分析服务没有返回具体错误。"));
const history = computed(() => events.value.filter(event => event.type.startsWith("node.") || event.type.startsWith("run.")).slice(-18).reverse());
const historyLabels: Record<string, string> = { "run.started": "开始分析", "run.queued": "已进入执行队列", "run.completed": "分析完成", "run.failed": "分析失败", "run.cancelled": "已取消", "node.started": "开始", "node.waiting": "等待模型或工具返回", "node.completed": "完成", "node.failed": "失败" };
function time(value: string) { return new Date(value).toLocaleTimeString("zh-CN", { hour12: false }); }
function go(name: string) { void router.push(routeTo(name)); }
watch(() => route.params.runId, () => { selectedEvidence.value = ""; newStep.value = { objective: "", action: "SEARCH_INTERNAL", query: "" }; });

async function control(action: "retry" | "cancel" | "pause" | "append") {
  if (busy.value || !run.value) return;
  busy.value = true;
  try {
    const runId = String(route.params.runId);
    if (action === "retry") {
      const next = await runsApi.retry(workspaceId.value, projectId.value, runId);
      await router.push({ ...routeTo("project-run-detail"), params: { ...routeTo("project-run-detail").params, runId: String(next.id || next.runId) } });
      notify("已重新开始分析，原记录已保留");
    } else if (action === "cancel") {
      await runsApi.cancel(workspaceId.value, projectId.value, runId);
      await refresh();
    } else {
      await runsApi.updatePlan(workspaceId.value, projectId.value, runId, {
        expectedVersion: Number(run.value.planVersion || 0),
        mode: action === "append" ? "APPEND" : run.value.paused ? "RESUME" : "PAUSE",
        ...(action === "append" ? { steps: [{ id: `U${Date.now()}`, ...newStep.value, objective: newStep.value.objective.trim(), query: newStep.value.query.trim() || newStep.value.objective.trim() }] } : {}),
      });
      if (action === "append") newStep.value = { objective: "", action: "SEARCH_INTERNAL", query: "" };
      await refresh();
    }
  } catch (cause) { notify(cause instanceof Error ? cause.message : "操作失败，请重试"); }
  finally { busy.value = false; }
}
async function copyEvidence() {
  try { await navigator.clipboard.writeText(selected.value?.excerpt || ""); notify("引用已复制"); }
  catch { notify("复制失败，请手动选择引用内容"); }
}
function exportReport() {
  const content = [`# ${report.value?.title || "分析报告"}`, summary.value,
    ...reportSections.value.map(section => `## ${section.title || "分析"}\n\n${section.content || ""}`),
    "## 建议", ...recommendations.value.map(value => `- ${value}`), "## 限制与待确认事项", ...limitations.value.map(value => `- ${value}`)].join("\n\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url; link.download = `分析报告-${route.params.runId}.md`; link.click(); URL.revokeObjectURL(url);
}
</script>

<template>
  <div class="analysis-page">
    <PageHeader eyebrow="PROJECT / ANALYSIS" title="智能分析" :subtitle="`${selectedProject?.name || '当前项目'} · 从规划输入到可审查的分析结果`" />
    <div class="analysis-nav">
      <button class="text-button" @click="go('project-planning')"><ArrowLeft :size="15" />返回规划输入</button>
      <button class="text-button" @click="go('project-runs')">分析记录<ArrowRight :size="14" /></button>
    </div>
    <ProjectWorkflow />
    <div v-if="loading && !run" class="analysis-loading" role="status"><LoaderCircle class="spin" :size="22" />正在读取分析进度…</div>
    <div v-else-if="!run" class="analysis-notice is-error" role="alert"><CircleAlert :size="20" /><div><strong>分析详情加载失败</strong><p>{{ error }}</p><button class="text-button" @click="refresh">重新连接</button></div></div>
    <template v-if="run">
      <header class="analysis-heading">
        <div><h1>项目智能分析 <span class="analysis-status" :class="status.toLowerCase()">{{ statusText }}</span></h1><p>{{ selectedProject?.name || '当前项目' }} · 分析 #{{ run.id || run.runId }}<span v-if="lastSynced"> · {{ disconnected ? '同步中断' : active ? '每 2 秒同步' : '记录已同步' }}</span></p></div>
        <div class="analysis-actions">
          <template v-if="editable"><button class="button button-secondary button-sm" :disabled="busy || disconnected" @click="control('pause')"><Play v-if="run.paused" :size="14" /><Pause v-else :size="14" />{{ run.paused ? '继续分析' : '暂停' }}</button><button class="button button-secondary button-sm" :disabled="busy" @click="control('cancel')"><Square :size="13" />取消</button></template>
          <button v-if="['FAILED','CANCELLED'].includes(status)" class="button button-primary button-sm" :disabled="busy" @click="control('retry')"><RefreshCw :size="14" />重新分析</button>
          <button v-if="status === 'COMPLETED'" class="button button-primary button-sm" @click="go('project-review')">进入审查<ArrowRight :size="14" /></button>
        </div>
      </header>
      <section class="analysis-progress" :class="{ 'has-error': status === 'FAILED' }" aria-label="分析进度">
        <div class="analysis-current" role="status" aria-live="polite">
          <span class="activity-icon"><CircleAlert v-if="status === 'FAILED' || disconnected" :size="23" /><Check v-else-if="status === 'COMPLETED'" :size="23" /><LoaderCircle v-else-if="active && status !== 'PAUSED'" class="spin" :size="23" /><Pause v-else :size="23" /></span>
          <div><strong>{{ activityTitle }}</strong><p>{{ disconnected ? '暂时无法取得实时数据，正在自动重连。下方保留最后一次已知状态。' : status === 'FAILED' ? researchErrorHelp(errorMessage) : active ? latestWait || researchStages[stageIndex]?.description || '任务已创建，正在等待执行。你可以离开此页，稍后回来继续查看。' : status === 'COMPLETED' ? '自动分析结果仍需人工确认；请同时检查引用和限制。' : '规划输入与已有分析记录已保留。' }}</p></div>
          <strong class="progress-number">{{ progress }}<small>%</small></strong>
        </div>
        <div class="analysis-progress-track" role="progressbar" aria-label="阶段进度" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100"><span :style="{ width: `${progress}%` }" /></div>
        <ol class="analysis-stages"><li v-for="(stage,index) in researchStages" :key="stage.title" :class="{ done: index < stageIndex, current: index === stageIndex, failed: index === stageIndex && status === 'FAILED' }"><span><Check v-if="index < stageIndex" :size="14" /><CircleAlert v-else-if="index === stageIndex && status === 'FAILED'" :size="14" /><template v-else>{{ index + 1 }}</template></span><div><strong>{{ stage.title }}</strong><small>{{ index < stageIndex ? '已完成' : index === stageIndex ? statusText : '待执行' }}</small></div></li></ol>
        <div class="analysis-stats"><span><Clock3 :size="14" />已运行 <b>{{ elapsed }}</b></span><span><Database :size="14" />已收集 <b>{{ evidence.length }} 条证据</b></span><span>Token <b>{{ run.tokenCount == null ? '暂未返回' : Number(run.tokenCount).toLocaleString() }}</b></span><span class="progress-note">进度随执行阶段更新</span></div>
      </section>
      <div v-if="waiting && !disconnected" class="analysis-notice" role="status"><Clock3 :size="19" /><div><strong>当前步骤已 {{ sinceActivity }} 秒没有新的执行结果</strong><p>正在等待模型或工具返回，尚未完成此步骤。你可以继续等待，也可以取消后检查模型配置。</p></div><button class="text-button" @click="go('settings-models')">模型设置<ArrowRight :size="14" /></button></div>
      <div v-if="status === 'FAILED'" class="analysis-notice is-error" role="alert"><CircleAlert :size="20" /><div><strong>失败原因</strong><p>{{ errorMessage }}</p></div><button class="text-button" @click="go('settings-models')">检查模型连接</button></div>
      <div class="analysis-columns">
        <div class="analysis-main">
          <section class="analysis-section">
            <div class="section-title"><div><h2>执行过程</h2><p>记录实际分配的任务与返回结果</p></div><span>{{ tasks.length }} 项任务</span></div>
            <ol v-if="tasks.length" class="analysis-tasks"><li v-for="task in tasks" :key="task.id" :class="task.status"><span class="task-marker"><Check v-if="task.status === 'completed'" :size="15" /><CircleAlert v-else-if="['failed','interrupted'].includes(task.status)" :size="15" /><LoaderCircle v-else-if="task.status === 'running'" class="spin" :size="15" /><Clock3 v-else :size="15" /></span><div><strong>{{ task.title }}</strong><p>{{ task.error || task.summary || (task.status === 'running' ? '正在执行，等待返回结果…' : task.status === 'interrupted' ? '分析已停止' : '等待执行') }}</p></div><small>{{ task.durationMs != null ? `${Math.max(1,Math.round(task.durationMs / 1000))} 秒` : task.status === 'running' ? '进行中' : '' }}</small></li></ol>
            <div v-else class="analysis-empty"><Clock3 :size="23" /><strong>{{ active ? '等待第一项任务' : '没有可用的任务轨迹' }}</strong><p>{{ active ? '分析服务开始处理后，这里会展示目标拆解、检索、撰写和核验的实际过程。' : '可查看下方执行日志或重新发起分析。' }}</p></div>
            <details v-if="history.length" class="analysis-log"><summary>执行日志 · {{ history.length }} 条最近事件</summary><ol><li v-for="event in history" :key="event.id"><time>{{ time(event.timestamp) }}</time><span>{{ event.title || historyLabels[event.type] || event.type }}<small v-if="event.title"> · {{ historyLabels[event.type] }}</small><p v-if="event.detail">{{ event.detail }}</p></span></li></ol></details>
          </section>
          <section class="analysis-section">
            <div class="section-title"><div><h2>研究计划 <small v-if="plan.length">v{{ run.planVersion }}</small></h2><p>{{ planData?.summary || (active ? '完成目标拆解后，将在这里列出具体研究问题。' : '本次分析尚未生成研究计划。') }}</p></div></div>
            <ol v-if="plan.length" class="analysis-plan"><li v-for="(step,index) in plan" :key="step.id"><span>{{ index + 1 }}</span><div><strong>{{ step.objective }}</strong><p v-if="step.query">{{ step.query }}</p></div></li></ol>
            <details v-if="editable && plan.length" class="analysis-append"><summary><Plus :size="14" />补充研究问题</summary><form @submit.prevent="control('append')"><input v-model="newStep.objective" aria-label="追加计划步骤" placeholder="例如：核对首期试点的实施成本" maxlength="500" required /><select v-model="newStep.action" aria-label="计划动作"><option value="SEARCH_INTERNAL">项目资料</option><option value="SEARCH_GRAPH">知识图谱</option><option value="SEARCH_WEB">外部搜索</option><option value="SYNTHESIZE">整理结论</option></select><button class="button button-primary button-sm" :disabled="busy || disconnected || !newStep.objective.trim()">追加</button></form></details>
          </section>
          <section class="analysis-section analysis-result">
            <div class="section-title"><div><h2>分析结果</h2><p>{{ summary ? '请结合来源与限制审阅以下结论' : '分析完成后显示真实结论、建议和限制' }}</p></div><button v-if="summary" class="text-button" @click="exportReport"><FileText :size="14" />导出</button></div>
            <template v-if="summary"><p class="result-summary">{{ summary }}</p><div v-for="(section,index) in reportSections" :key="index" class="result-section"><h3>{{ section.title }}</h3><p>{{ section.content }}</p></div><div v-if="recommendations.length" class="result-section"><h3>建议</h3><ul><li v-for="(item,index) in recommendations" :key="index">{{ item }}</li></ul></div><div v-if="limitations.length" class="result-section"><h3>限制与待确认事项</h3><ul><li v-for="(item,index) in limitations" :key="index">{{ item }}</li></ul></div></template>
            <p v-else class="result-placeholder">{{ status === 'FAILED' ? '本次分析未完成，尚无可用结论。请处理失败原因后重新分析。' : status === 'COMPLETED' ? '本次运行未返回结论内容，请查看报告记录。' : '尚未生成分析结论。' }}</p>
            <div v-if="status === 'COMPLETED'" class="result-next"><button class="button button-secondary button-sm" @click="go('project-reports')">查看报告<FileText :size="14" /></button><button class="text-button" @click="go('project-review')">下一步：审查定稿<ArrowRight :size="14" /></button></div>
          </section>
        </div>
        <aside class="analysis-sidebar">
          <section class="analysis-section"><div class="section-title"><h2>本次分析目标</h2><FileText :size="16" /></div><details class="analysis-goal"><summary>{{ String(run.title || run.goal || '规划输入') }}</summary><p>{{ run.goal }}</p></details><button class="text-button edit-goal" @click="go('project-planning')">查看规划输入<ArrowRight :size="14" /></button></section>
          <section class="analysis-section"><div class="section-title"><h2>证据与来源</h2><span>{{ evidence.length }}</span></div><div v-if="!evidence.length" class="analysis-empty"><Database :size="24" /><strong>{{ active ? '等待检索结果' : '尚无可引用证据' }}</strong><p>{{ active ? '检索返回后，来源与引用片段会显示在这里。' : '补充项目资料后重新分析，可提高结论的可验证性。' }}</p><button class="text-button" @click="go('project-assets')">查看项目资料<ArrowRight :size="14" /></button></div><div v-else class="analysis-evidence"><button v-for="(item,index) in evidence" :key="item.id" :class="{ selected: selectedEvidence === item.id }" @click="selectedEvidence = selectedEvidence === item.id ? '' : item.id"><span>{{ String(index + 1).padStart(2,'0') }}</span><div><strong>{{ item.title }}</strong><small>{{ item.section }}{{ item.page ? ` · 第 ${item.page} 页` : '' }}</small></div></button><div v-if="selected" class="evidence-excerpt"><p>{{ selected.excerpt }}</p><button class="text-button" @click="copyEvidence"><Copy :size="13" />复制引用</button></div></div></section>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.analysis-page { color: var(--workspace-text); width: 100%; max-width: 90rem; margin: 0 auto; }
.analysis-nav,.analysis-heading,.analysis-actions,.section-title,.analysis-stats,.result-next { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.analysis-nav { margin-bottom: 1rem; }
.analysis-heading { margin: 1.75rem 0 1.1rem; }
.analysis-heading h1 { display: flex; align-items: center; flex-wrap: wrap; gap: .8rem; margin: 0; font-size: 1.4rem; font-weight: 650; letter-spacing: -.025em; }
.analysis-heading p { color: var(--workspace-muted); font-size: .78rem; margin: .6rem 0 0; }
.analysis-actions { justify-content: flex-end; flex-wrap: wrap; gap: .5rem; }
.analysis-status { padding: .25rem .55rem; font-size: .7rem; font-weight: 550; background: var(--surface-soft); border: 1px solid var(--workspace-border); border-radius: .35rem; }
.analysis-status.running,.analysis-status.completed { color: var(--teal-dark); background: color-mix(in srgb,var(--teal) 10%,var(--surface)); }
.analysis-status.failed { color: #ce6464; }
.analysis-progress { border: 1px solid var(--workspace-border); border-radius: .75rem; background: var(--surface); overflow: hidden; }
.analysis-current { display: flex; align-items: center; gap: 1rem; padding: 1.4rem 1.5rem 1.15rem; }
.activity-icon { display: grid; place-items: center; width: 2.9rem; height: 2.9rem; flex-shrink: 0; color: var(--teal-dark); background: color-mix(in srgb,var(--teal) 10%,var(--surface)); border-radius: .65rem; }
.analysis-current > div { flex: 1; min-width: 0; }
.analysis-current strong { font-size: .98rem; font-weight: 600; }
.analysis-current p { font-size: .78rem; line-height: 1.7; color: var(--workspace-muted); margin: .4rem 0 0; }
.analysis-current .progress-number { font-size: 1.8rem; font-variant-numeric: tabular-nums; font-weight: 550; }
.progress-number small { font-size: .8rem; color: var(--workspace-muted); margin-left: .15rem; }
.analysis-progress-track { height: 3px; margin: 0 1.5rem; background: var(--workspace-divider); }
.analysis-progress-track span { display: block; height: 100%; background: var(--teal); transition: width .3s; }
.has-error .analysis-progress-track span { background: #ce6464; }
.analysis-stages { display: grid; grid-template-columns: repeat(4,1fr); gap: .75rem; list-style: none; margin: 0; padding: 1.3rem 1.5rem; }
.analysis-stages li { display: flex; align-items: center; gap: .65rem; color: var(--workspace-muted); }
.analysis-stages li > span { width: 1.8rem; height: 1.8rem; flex-shrink: 0; display: grid; place-items: center; border: 1px solid var(--workspace-border); border-radius: 50%; font-size: .72rem; }
.analysis-stages strong { display: block; font-size: .8rem; font-weight: 550; }
.analysis-stages small { display: block; margin-top: .2rem; font-size: .68rem; }
.analysis-stages .current { color: var(--workspace-text); }
.analysis-stages .current > span,.analysis-stages .done > span { color: var(--teal-dark); border-color: var(--teal); background: color-mix(in srgb,var(--teal) 9%,var(--surface)); }
.analysis-stages .failed > span { color: #ce6464; border-color: #ce6464; }
.analysis-stats { flex-wrap: wrap; justify-content: flex-start; border-top: 1px solid var(--workspace-divider); padding: .85rem 1.5rem; color: var(--workspace-muted); font-size: .72rem; gap: 1.5rem; }
.analysis-stats span { display: inline-flex; align-items: center; gap: .4rem; }
.analysis-stats b { color: var(--workspace-text); font-weight: 500; font-variant-numeric: tabular-nums; }
.analysis-stats .progress-note { margin-left: auto; font-size: .68rem; }
.analysis-columns { display: grid; grid-template-columns: minmax(0,1fr) minmax(16rem,.46fr); gap: 1.25rem; margin-top: 1.25rem; align-items: start; }
.analysis-main,.analysis-sidebar { display: grid; gap: 1.25rem; min-width: 0; }
.analysis-section { background: var(--surface); border: 1px solid var(--workspace-border); border-radius: .65rem; overflow: hidden; min-width: 0; }
.section-title { padding: 1.2rem 1.3rem; gap: .5rem; }
.section-title h2 { margin: 0; font-size: .88rem; font-weight: 600; }
.section-title h2 small { font-size: .7rem; color: var(--workspace-muted); margin-left: .3rem; }
.section-title p { margin: .35rem 0 0; font-size: .73rem; color: var(--workspace-muted); line-height: 1.7; }
.section-title > span,.section-title > svg { color: var(--workspace-muted); font-size: .7rem; flex-shrink: 0; }
.analysis-tasks { list-style: none; margin: 0; padding: 0 1.3rem .4rem; }
.analysis-tasks li { display: flex; gap: .7rem; padding: .95rem 0; border-top: 1px solid var(--workspace-divider); align-items: flex-start; }
.task-marker { display: grid; place-items: center; flex: 0 0 1.4rem; height: 1.4rem; color: var(--workspace-muted); }
.analysis-tasks .completed .task-marker,.analysis-tasks .running .task-marker { color: var(--teal-dark); }
.analysis-tasks .failed .task-marker { color: #ce6464; }
.analysis-tasks li > div { flex: 1; min-width: 0; }
.analysis-tasks strong,.analysis-plan strong { font-size: .79rem; font-weight: 550; line-height: 1.7; }
.analysis-tasks p,.analysis-plan p { font-size: .73rem; line-height: 1.8; color: var(--workspace-muted); margin: .25rem 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.analysis-tasks li > small { font-size: .68rem; color: var(--workspace-muted); white-space: nowrap; padding-top: .25rem; }
.analysis-empty { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 1.2rem 1.5rem 1.6rem; color: var(--workspace-muted); gap: .65rem; }
.analysis-empty strong { font-size: .8rem; font-weight: 500; color: var(--workspace-text); }
.analysis-empty p { max-width: 29rem; font-size: .74rem; line-height: 1.8; margin: 0 0 .3rem; }
.analysis-log { border-top: 1px solid var(--workspace-divider); padding: .85rem 1.3rem; font-size: .74rem; }
.analysis-log summary,.analysis-goal summary,.analysis-append summary { cursor: pointer; line-height: 1.7; }
.analysis-log summary { color: var(--workspace-muted); }
.analysis-log ol { list-style: none; padding: 0; margin: .8rem 0 0; }
.analysis-log li { display: flex; gap: .8rem; padding: .4rem 0; }
.analysis-log time { color: var(--workspace-muted); font-size: .68rem; font-variant-numeric: tabular-nums; }
.analysis-log p { margin: .3rem 0; overflow-wrap: anywhere; }
.analysis-plan { list-style: none; padding: 0 1.3rem 1rem; margin: 0; }
.analysis-plan li { display: flex; gap: .8rem; padding: .7rem 0; border-top: 1px solid var(--workspace-divider); }
.analysis-plan li > span { color: var(--workspace-muted); font-size: .75rem; padding-top: .2rem; }
.analysis-append { border-top: 1px solid var(--workspace-divider); padding: .8rem 1.3rem; }
.analysis-append summary { font-size: .74rem; color: var(--teal-dark); }
.analysis-append summary svg { vertical-align: middle; }
.analysis-append form { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .8rem; }
.analysis-append input,.analysis-append select { border: 1px solid var(--workspace-border); border-radius: .4rem; background: var(--surface); color: var(--workspace-text); font: inherit; font-size: .75rem; padding: .5rem; min-width: 0; }
.analysis-append input { flex: 1; min-width: 10rem; }
.analysis-goal { padding: 0 1.3rem; font-size: .78rem; overflow-wrap: anywhere; }
.analysis-goal summary { font-weight: 500; }
.analysis-goal p { color: var(--workspace-muted); font-size: .75rem; line-height: 1.9; white-space: pre-wrap; }
.edit-goal { margin: 1rem 1.3rem 1.2rem; }
.analysis-evidence { padding: 0 1.3rem 1rem; }
.analysis-evidence > button { display: flex; width: 100%; gap: .6rem; text-align: left; padding: .8rem 0; border: 0; border-top: 1px solid var(--workspace-divider); background: none; color: inherit; cursor: pointer; }
.analysis-evidence > button.selected { color: var(--teal-dark); }
.analysis-evidence > button > span { color: var(--workspace-muted); font-size: .65rem; padding-top: .2rem; }
.analysis-evidence strong { display: block; font-size: .76rem; font-weight: 500; overflow-wrap: anywhere; }
.analysis-evidence small { display: block; margin-top: .3rem; font-size: .66rem; color: var(--workspace-muted); }
.evidence-excerpt { border-top: 1px solid var(--workspace-divider); padding-top: .6rem; }
.evidence-excerpt p { white-space: pre-wrap; font-size: .75rem; line-height: 1.9; overflow-wrap: anywhere; max-height: 25rem; overflow: auto; }
.result-summary,.result-placeholder,.result-section { margin: 0; padding: 0 1.3rem 1.2rem; font-size: .8rem; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; }
.result-placeholder { color: var(--workspace-muted); }
.result-section h3 { font-size: .85rem; margin: .3rem 0; }
.result-section p { margin: 0; }
.result-section ul { white-space: normal; padding-left: 1.1rem; margin: .3rem 0; }
.result-next { padding: 1rem 1.3rem; border-top: 1px solid var(--workspace-divider); flex-wrap: wrap; }
.analysis-notice { display: flex; align-items: flex-start; gap: .75rem; margin-top: 1rem; padding: 1rem 1.2rem; border: 1px solid color-mix(in srgb,#c79b4d 40%,var(--workspace-border)); background: color-mix(in srgb,#c79b4d 6%,var(--surface)); border-radius: .6rem; }
.analysis-notice > svg { flex-shrink: 0; color: #c79b4d; }
.analysis-notice > div { flex: 1; min-width: 0; }
.analysis-notice strong { font-size: .8rem; font-weight: 550; }
.analysis-notice p { margin: .3rem 0 0; font-size: .75rem; line-height: 1.8; color: var(--workspace-muted); overflow-wrap: anywhere; }
.is-error { border-color: color-mix(in srgb,#ce6464 40%,var(--workspace-border)); background: color-mix(in srgb,#ce6464 5%,var(--surface)); }
.is-error > svg { color: #ce6464; }
.analysis-loading { display: flex; justify-content: center; align-items: center; gap: .8rem; min-height: 18rem; color: var(--workspace-muted); }
.analysis-page .text-button { font-size: .74rem; gap: .35rem; }
.analysis-page button:focus-visible,.analysis-page summary:focus-visible,.analysis-page input:focus-visible,.analysis-page select:focus-visible { outline: 2px solid var(--teal); outline-offset: 3px; }
.spin { animation: rotate 1.2s linear infinite; }
@keyframes rotate { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } .analysis-progress-track span { transition: none; } }
@media (max-width: 68rem) { .analysis-columns { grid-template-columns: minmax(0,1fr); } .analysis-sidebar { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 42rem) { .analysis-heading { align-items: flex-start; flex-direction: column; } .analysis-heading h1 { font-size: 1.2rem; } .analysis-sidebar { grid-template-columns: minmax(0,1fr); } .analysis-current { padding: 1rem; gap: .7rem; align-items: flex-start; } .activity-icon { width: 2.2rem; height: 2.2rem; } .analysis-current .progress-number { font-size: 1.2rem; } .analysis-stages { padding: 1rem; grid-template-columns: repeat(2,1fr); gap: 1rem; } .analysis-stats { padding: .8rem 1rem; gap: .8rem; } .analysis-stats .progress-note { margin-left: 0; width: 100%; } .analysis-notice { flex-wrap: wrap; } .analysis-notice > div { min-width: 70%; } }
</style>
