<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { CheckCircle2, CircleAlert, History, Play, ShieldCheck, XCircle } from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { securityApi, type AuditLogEntry, type HarnessCase, type HarnessResult, type HarnessRun } from "@/api/security";
import { projectApi } from "@/api/projects";
import { getLastProjectId } from "@/utils/lastProject";
import { formatDateTime } from "@/lib/utils";

const { workspaceId, projectId, selectedProject, notify } = useWorkspace();
const cases = ref<HarnessCase[]>([]);
const runs = ref<HarnessRun[]>([]);
const detail = ref<{ run: HarnessRun; results: HarnessResult[] } | null>(null);
const auditLogs = ref<AuditLogEntry[]>([]);
const projectOptions = ref<{ id: number; name: string }[]>([]);
const selectedProjectId = ref<number | null>(projectId.value > 0 ? projectId.value : null);
const loading = ref(false);
const includeModelProbes = ref(false);
const error = ref("");

const latest = computed(() => detail.value?.run || runs.value[0] || null);
const passRate = computed(() => latest.value && latest.value.totalCases ? Math.round((latest.value.passedCases / latest.value.totalCases) * 100) : 0);
const failedResults = computed(() => detail.value?.results.filter((item) => item.status === "FAIL") || []);

function resultIcon(status: string) {
  if (status === "PASS") return CheckCircle2;
  if (status === "FAIL") return XCircle;
  return CircleAlert;
}

function resultClass(status: string) {
  return status.toLowerCase();
}

function formatTime(value?: string) {
  return formatDateTime(value, "暂无");
}

async function refresh() {
  const [remoteCases, remoteRuns, logs] = await Promise.all([
    securityApi.cases(workspaceId.value),
    securityApi.runs(workspaceId.value),
    securityApi.auditLogs(workspaceId.value, 30),
  ]);
  cases.value = remoteCases;
  runs.value = remoteRuns;
  auditLogs.value = logs;
  if (remoteRuns[0]) detail.value = await securityApi.detail(workspaceId.value, remoteRuns[0].id);
}

async function waitForRun(runId: number | string) {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    const next = await securityApi.detail(workspaceId.value, runId);
    detail.value = next;
    if (next.run.status !== "RUNNING") {
      runs.value = [next.run, ...runs.value.filter((item) => String(item.id) !== String(runId))];
      auditLogs.value = await securityApi.auditLogs(workspaceId.value, 30);
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 800));
  }
  throw new Error("安全审计仍在运行，请稍后刷新查看结果");
}

async function runHarness() {
  error.value = "";
  if (!selectedProjectId.value) {
    error.value = "请先选择一个项目作为运行时范围";
    return;
  }
  loading.value = true;
  try {
    const run = await securityApi.start(workspaceId.value, { projectId: selectedProjectId.value, includeModelProbes: includeModelProbes.value });
    await waitForRun(run.id);
    notify("安全审计 Harness 已完成");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "安全审计启动失败";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    const projects = await projectApi.list(workspaceId.value);
    projectOptions.value = projects.map((project) => ({ id: Number(project.id), name: project.name }));
    if (!selectedProjectId.value) {
      selectedProjectId.value =
        selectedProject.value?.id ||
        projects.find((project) => project.id === getLastProjectId(workspaceId.value))?.id ||
        projects[0]?.id ||
        null;
    }
    await refresh();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "安全审计数据加载失败";
  }
});
</script>

<template>
  <Layout eyebrow="WORKSPACE / SECURITY" title="安全审计 Harness" subtitle="用可重复的应用安全用例检查提示词、工具、租户边界、模型参数、网络出口和秘密脱敏。">
    <section class="settings-section security-hero">
      <div class="security-hero-copy"><span class="security-icon"><ShieldCheck :size="20" /></span><div><h2>安全基线</h2><p>标准 Harness 默认只执行本地确定性检查，不会调用外部模型；模型行为探针需由管理员主动开启。</p></div></div>
      <div class="security-controls"><label class="field-label">运行时项目<select v-model="selectedProjectId"><option :value="null">请选择项目</option><option v-for="project in projectOptions" :key="project.id" :value="project.id">{{ project.name }}</option></select></label><label class="probe-toggle"><input v-model="includeModelProbes" type="checkbox" />运行模型行为探针<small>会消耗模型额度并发送测试提示词</small></label><button class="button button-primary" type="button" :disabled="loading" @click="runHarness"><Play :size="14" />{{ loading ? "审计运行中" : "运行安全审计" }}</button></div>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    </section>
    <section class="security-summary">
      <div class="summary-card"><strong>{{ latest?.score ?? 0 }}%</strong><span>安全得分</span></div><div class="summary-card"><strong>{{ passRate }}%</strong><span>通过率</span></div><div class="summary-card"><strong>{{ latest?.failedCases ?? 0 }}</strong><span>失败用例</span></div><div class="summary-card"><strong>{{ latest ? formatTime(latest.createdAt) : "暂无" }}</strong><span>最近运行</span></div>
    </section>
    <section class="settings-section">
      <div class="section-intro"><div><h2>Harness 用例</h2><p>失败项会保留最小化证据；敏感凭证不会进入结果或审计详情。</p></div></div>
      <div class="harness-list"><div v-for="item in cases" :key="item.code" class="harness-row"><span class="case-status"><component :is="resultIcon(detail?.results.find((result) => result.caseCode === item.code)?.status || 'SKIPPED')" :size="15" /></span><div><strong>{{ item.name }}</strong><small>{{ item.category }} · {{ item.severity }} · {{ item.description }}</small></div><span class="case-result" :class="resultClass(detail?.results.find((result) => result.caseCode === item.code)?.status || '未运行')">{{ detail?.results.find((result) => result.caseCode === item.code)?.status || "未运行" }}</span></div></div>
      <div v-if="failedResults.length" class="failure-list"><strong>需要处理</strong><p v-for="item in failedResults" :key="item.caseCode">{{ item.name }}：{{ item.message }}</p></div>
    </section>
    <section class="settings-section split-section">
      <div><div class="section-title-line"><History :size="15" /><h2>运行记录</h2></div><div class="compact-list"><div v-for="run in runs" :key="run.id" class="compact-row"><span>#{{ run.id }}</span><strong>{{ run.status }}</strong><small>{{ run.passedCases }}/{{ run.totalCases }} 通过 · {{ formatTime(run.createdAt) }}</small></div><p v-if="!runs.length" class="muted">暂无运行记录</p></div></div>
      <div><div class="section-title-line"><ShieldCheck :size="15" /><h2>审计事件</h2></div><div class="compact-list"><div v-for="log in auditLogs.slice(0, 8)" :key="log.id" class="compact-row"><strong>{{ log.action }}</strong><small>{{ formatTime(log.createdAt) }}</small></div><p v-if="!auditLogs.length" class="muted">暂无审计事件</p></div></div>
    </section>
  </Layout>
</template>

<style scoped>
.security-hero { display: grid; gap: 1rem; }
.security-hero-copy, .security-controls, .section-title-line { display: flex; align-items: center; gap: .75rem; }
.security-icon { display: grid; place-items: center; width: 2.5rem; height: 2.5rem; border-radius: .625rem; color: var(--teal-dark); background: #e4f6f3; }
.security-hero h2, .section-title-line h2 { margin: 0; color: var(--workspace-text); font-size: .875rem; }
.security-hero p { margin: .25rem 0 0; color: var(--workspace-muted); font-size: 0.75rem; }
.security-controls { align-items: end; flex-wrap: wrap; }
.security-controls .field-label { min-width: 15rem; }
.probe-toggle { display: grid; grid-template-columns: auto 1fr; column-gap: .375rem; align-items: center; color: var(--workspace-text); font-size: 0.75rem; font-weight: 650; }
.probe-toggle small { grid-column: 2; color: var(--workspace-muted); font-size: 0.75rem; font-weight: 400; }
.security-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: .625rem; padding: 1rem 1.25rem; border-bottom: .0625rem solid #edf1f1; }
.summary-card { display: grid; gap: .25rem; padding: .75rem; border: .0625rem solid var(--workspace-border); border-radius: .5rem; background: var(--surface); }
.summary-card strong { color: var(--workspace-text); font-size: 1rem; }
.summary-card span { color: var(--workspace-muted); font-size: 0.75rem; }
.harness-list, .compact-list { border: .0625rem solid #e7eeee; border-radius: .5rem; }
.harness-row, .compact-row { display: flex; align-items: center; gap: .625rem; min-height: 3.125rem; padding: .5rem .75rem; border-bottom: .0625rem solid #edf1f1; }
.harness-row:last-child, .compact-row:last-child { border-bottom: 0; }
.harness-row > div { flex: 1; min-width: 0; }
.harness-row strong, .harness-row small { display: block; }
.harness-row strong { color: var(--workspace-text); font-size: 0.8125rem; }
.harness-row small { margin-top: .1875rem; color: var(--workspace-muted); font-size: 0.75rem; }
.case-status { color: var(--workspace-muted); }
.case-result { min-width: 3rem; text-align: right; color: var(--workspace-muted); font-size: 0.75rem; font-weight: 700; }
.case-result.pass { color: #0c9b8d; }.case-result.fail { color: #c75a5a; }.case-result.blocked, .case-result.skipped { color: #a87932; }
.failure-list { margin-top: .75rem; padding: .75rem; border: .0625rem solid #f2d3d3; border-radius: .5rem; background: #fff8f8; color: #a14d4d; font-size: 0.75rem; }
.failure-list p { margin: .3125rem 0 0; }
.split-section { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.section-title-line { margin-bottom: .625rem; color: var(--teal-dark); }
.compact-row { min-height: 2.5rem; }.compact-row strong { color: var(--workspace-text); font-size: 0.75rem; }.compact-row span, .compact-row small, .muted { color: var(--workspace-muted); font-size: 0.75rem; }.compact-row small { margin-left: auto; }
@media (max-width: 48rem) { .security-summary, .split-section { grid-template-columns: 1fr 1fr; }.security-controls .field-label { min-width: 100%; } }
</style>
