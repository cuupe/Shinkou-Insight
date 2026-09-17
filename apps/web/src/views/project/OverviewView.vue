<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Database,
  Download,
  FileCheck2,
  MessageCircle,
  ShieldCheck,
  Users,
  Zap,
} from "@lucide/vue";
import { useWorkspace } from "@/composables/useWorkspace";
import PageHeader from "@/components/common/PageHeader.vue";
import TokenUsageChart from "@/components/common/TokenUsageChart.vue";
const { selectedProject, router, routeTo, assets, recentRuns, reports, actionItems, statusClass, statistics } =
  useWorkspace();

const quickActions = [
  { label: "启动项目 Agent", description: "从目标开始，串联规划、搜集与审查", route: "project-agent-chat", tone: "violet", icon: MessageCircle },
  { label: "查看规划中枢", description: "目标、竞品、可行性与计划书", route: "project-planning", tone: "teal", icon: ClipboardList },
  { label: "查看审查中心", description: "引用门禁与反虚构规则", route: "project-review", tone: "amber", icon: FileCheck2 },
  { label: "上传项目资料", description: "PDF、Markdown、TXT", route: "project-assets", tone: "blue", icon: Database },
];

const indexedCount = computed(
  () => assets.filter((item) => item.status === "indexed").length,
);
const indexCompletion = computed(() => {
  if (!assets.length) return "0%";
  return `${Math.round((indexedCount.value / assets.length) * 100)}%`;
});
const projectSummary = computed(() => statistics.value?.summary);
const tokenUsage = computed(() => statistics.value?.tokenUsage);
const tokenDaily = computed(() => statistics.value?.tokenDaily || []);
const tokenUsers = computed(() => statistics.value?.tokenUsers || []);
const tokenBreakdown = computed(() => {
  if (statistics.value?.tokenBreakdown?.length) return statistics.value.tokenBreakdown;
  return tokenUsers.value.map((user) => ({
    projectId: selectedProject.value?.id || 0,
    projectName: selectedProject.value?.name || "当前项目",
    userId: user.userId,
    userName: user.userName,
    modelName: "模型未标注",
    totalTokens: user.totalTokens,
    inputTokens: 0,
    outputTokens: 0,
    runCount: user.runCount,
  }));
});
const tokenChartItems = computed(() => tokenBreakdown.value.map((item) => ({
  label: `${item.userName || `用户 ${item.userId}`} · ${item.modelName || "模型未标注"}`,
  detail: `${item.projectName || "当前项目"} · ${item.runCount} 次运行`,
  tokens: Number(item.totalTokens) || 0,
})));
const maxDailyTokens = computed(() => Math.max(1, ...tokenDaily.value.map((item) => Number(item.tokens) || 0)));
const maxHeatTokens = computed(() => Math.max(1, ...tokenDaily.value.map((item) => Number(item.tokens) || 0)));
const qualityAverage = computed(() => {
  const values = [
    projectSummary.value?.avgRecall,
    projectSummary.value?.avgCitation,
    projectSummary.value?.avgJsonScore,
  ].filter((value): value is number => typeof value === "number");
  if (!values.length) return "—";
  return `${(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)}%`;
});
function statisticStatusLabel(status: string) {
  return (
    {
      QUEUED: "排队中",
      PENDING: "待处理",
      RUNNING: "运行中",
      PROCESSING: "处理中",
      COMPLETED: "已完成",
      SUCCESS: "成功",
      FAILED: "失败",
      CANCELLED: "已取消",
      CANCELED: "已取消",
      INDEXING: "索引中",
      INDEXED: "已索引",
      DRAFT: "草稿",
      TODO: "待办",
      IN_PROGRESS: "进行中",
      DONE: "已完成",
    } as Record<string, string>
  )[status] || status;
}
const capabilities = computed(() => [
  {
    title: assets.length ? "知识库已就绪" : "知识库暂无资料",
    description: assets.length ? "支持查看真实索引状态" : "上传资料后这里会显示索引状态",
    icon: "database",
  },
  {
    title: recentRuns.length ? "已有调研运行" : "暂无调研运行",
    description: recentRuns.length ? "可查看项目内真实任务进展" : "已有调研运行后这里会显示进展",
    icon: "zap",
  },
]);

function overviewIcon(icon: string) {
  return icon === "database" ? Database : Zap;
}

function formatTokens(value: number | string | undefined) {
  return Number(value || 0).toLocaleString();
}

function heatLevel(value: number | string | undefined) {
  const ratio = (Number(value) || 0) / maxHeatTokens.value;
  if (ratio <= 0) return "level-0";
  if (ratio < 0.25) return "level-1";
  if (ratio < 0.5) return "level-2";
  if (ratio < 0.75) return "level-3";
  return "level-4";
}

function downloadText(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function exportTokenCsv() {
  const rows = ["date,tokens,runs", ...tokenDaily.value.map((item) => `${item.date},${item.tokens},${item.runs}`)];
  downloadText("project-token-usage.csv", `\ufeff${rows.join("\n")}\n`, "text/csv;charset=utf-8");
}

function exportProjectSnapshot() {
  const snapshot = {
    exportedAt: new Date().toISOString(),
    project: selectedProject.value,
    statistics: statistics.value,
    assets: assets,
    runs: recentRuns,
    reports,
    actionItems,
  };
  downloadText(
    `${selectedProject.value?.name || "project"}-snapshot.json`,
    JSON.stringify(snapshot, null, 2),
    "application/json;charset=utf-8",
  );
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / ACTIVE"
    :title="selectedProject?.name || '暂无项目'"
    :subtitle="selectedProject?.description || ''"
  >
  </PageHeader>
  <div class="quick-actions">
    <button
      v-for="(action, index) in quickActions"
      :key="action.label"
      type="button"
      @click="router.push(routeTo(action.route))"
    >
      <span class="quick-icon" :class="`${action.tone}-bg`">
        <component :is="action.icon" :size="18" />
      </span>
      <span><strong>{{ action.label }}</strong><small>{{ action.description }}</small></span>
      <ArrowRight :size="15" />
    </button>
  </div>
  <section class="planning-callout panel">
    <div class="planning-callout-icon"><ClipboardList :size="18" /></div>
    <div><strong>把一次调研升级为可审查的项目计划</strong><p>系统会沿着目标、证据、市场对比、可行性和人工签署逐步收敛，引用不足的结论不会直接进入发布版本。</p></div>
    <button class="button button-primary button-sm" type="button" @click="router.push(routeTo('project-agent-chat'))">启动 Agent <ArrowRight :size="14" /></button>
  </section>
  <section class="panel project-statistics-panel">
    <div class="panel-heading">
      <div>
        <h2>项目统计</h2>
        <p>当前项目累计数据与近 30 天业务状态</p>
      </div>
      <span class="statistics-source">实时汇总</span>
    </div>
    <div class="project-stat-grid">
      <div><strong>{{ projectSummary?.assetCount ?? 0 }}</strong><span>资料 · {{ projectSummary?.chunkCount ?? 0 }} 个分块</span></div>
      <div><strong>{{ projectSummary?.runCount ?? 0 }}</strong><span>调研运行 · {{ projectSummary?.completedRunCount ?? 0 }} 个完成</span></div>
      <div><strong>{{ projectSummary?.reportCount ?? 0 }}</strong><span>报告 · {{ projectSummary?.publishedReportCount ?? 0 }} 份已发布</span></div>
      <div><strong>{{ projectSummary?.openActionItemCount ?? 0 }}</strong><span>待跟进行动 · {{ projectSummary?.overdueActionItemCount ?? 0 }} 个逾期</span></div>
      <div><strong>{{ qualityAverage }}</strong><span>评估综合均值 · {{ projectSummary?.evaluationCaseCount ?? 0 }} 个用例</span></div>
      <div><strong>{{ projectSummary?.unreadNotificationCount ?? 0 }}</strong><span>未读通知</span></div>
    </div>
    <div class="statistics-breakdowns">
      <div>
        <span class="breakdown-title">运行状态</span>
        <span v-for="item in (statistics?.runStatuses || [])" :key="`run-${item.status}`" class="breakdown-item">{{ statisticStatusLabel(item.status) }} {{ item.count }}</span>
        <span v-if="!statistics?.runStatuses?.length" class="breakdown-empty">暂无运行数据</span>
      </div>
      <div>
        <span class="breakdown-title">资料索引</span>
        <span v-for="item in (statistics?.assetStatuses || [])" :key="`asset-${item.status}`" class="breakdown-item">{{ statisticStatusLabel(item.status) }} {{ item.count }}</span>
        <span v-if="!statistics?.assetStatuses?.length" class="breakdown-empty">暂无资料数据</span>
      </div>
      <div>
        <span class="breakdown-title">行动状态</span>
        <span v-for="item in (statistics?.actionItemStatuses || [])" :key="`action-${item.status}`" class="breakdown-item">{{ statisticStatusLabel(item.status) }} {{ item.count }}</span>
        <span v-if="!statistics?.actionItemStatuses?.length" class="breakdown-empty">暂无行动数据</span>
      </div>
    </div>
  </section>
  <section class="panel token-usage-panel">
    <div class="panel-heading">
      <div>
        <h2>项目 Token 使用</h2>
        <p>按真实运行记录统计；颜色越深表示当天消耗越高</p>
      </div>
      <div class="usage-actions">
        <button class="text-button" type="button" @click="exportTokenCsv"><Download :size="14" />导出 CSV</button>
        <button class="text-button" type="button" @click="exportProjectSnapshot"><Download :size="14" />导出项目快照</button>
      </div>
    </div>
    <div class="token-summary-grid">
      <div><strong>{{ formatTokens(tokenUsage?.totalTokens) }}</strong><span>总 Tokens</span></div>
      <div><strong>{{ formatTokens(tokenUsage?.inputTokens) }}</strong><span>输入 Tokens</span></div>
      <div><strong>{{ formatTokens(tokenUsage?.outputTokens) }}</strong><span>输出 Tokens</span></div>
      <div><strong>{{ formatTokens(tokenUsage?.compressedContextTokens) }}</strong><span>压缩节省估算</span></div>
      <div><strong>{{ formatTokens(tokenUsage?.runCount) }}</strong><span>计费运行次数</span></div>
    </div>
    <div class="token-usage-grid">
      <div class="token-heatmap-card">
        <div class="usage-subheading"><strong>近 {{ tokenDaily.length || 30 }} 天</strong><span>每日使用量</span></div>
        <div v-if="tokenDaily.length" class="token-heatmap" aria-label="每日 Token 使用热力图">
          <span
            v-for="point in tokenDaily"
            :key="point.date"
            class="heat-cell"
            :class="heatLevel(point.tokens)"
            :title="`${point.date} · ${formatTokens(point.tokens)} tokens · ${point.runs} 次运行`"
          />
        </div>
        <p v-else class="usage-empty">暂无真实 Token 记录</p>
        <div class="heatmap-legend"><span>少</span><i class="level-0" /><i class="level-1" /><i class="level-2" /><i class="level-3" /><i class="level-4" /><span>多</span></div>
        <div v-if="tokenDaily.length" class="daily-bars" aria-label="每日 Token 柱状图">
          <span v-for="point in tokenDaily" :key="`bar-${point.date}`" :title="`${point.date} · ${formatTokens(point.tokens)} tokens`"><i :style="{ height: `${Math.max(3, ((Number(point.tokens) || 0) / maxDailyTokens) * 100)}%` }" /></span>
        </div>
      </div>
      <div class="token-users-card">
        <div class="usage-subheading"><strong>按项目 / 用户 / 模型</strong><span>每条均来自真实运行记录</span></div>
        <TokenUsageChart v-if="tokenChartItems.length" :items="tokenChartItems" />
        <p v-else class="usage-empty">暂无真实 Token 记录</p>
        <div v-if="tokenBreakdown.length" class="token-breakdown-table">
          <div class="token-breakdown-row token-breakdown-header"><span>用户</span><span>模型</span><span>运行 / Tokens</span></div>
          <div v-for="item in tokenBreakdown" :key="`${item.projectId}-${item.userId}-${item.modelName}`" class="token-breakdown-row">
            <span>{{ item.userName || `用户 ${item.userId}` }}<small>{{ item.projectName }}</small></span>
            <span class="model-label">{{ item.modelName || "模型未标注" }}</span>
            <span>{{ item.runCount }} 次 · {{ formatTokens(item.totalTokens) }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
  <div class="overview-grid">
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>知识库状态</h2>
          <p>当前项目的真实资料索引状态</p>
        </div>
        <button
          class="text-button"
          type="button"
          @click="router.push(routeTo('project-assets'))"
        >
          管理资产 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="asset-health">
        <div>
          <strong>{{ assets.length }}</strong
          ><span>全部资料</span>
        </div>
        <div>
          <strong class="teal-text">{{ indexedCount }}</strong
          ><span>已索引</span>
        </div>
        <div><strong>{{ indexCompletion }}</strong><span>索引完成率</span></div>
      </div>
      <div class="health-progress" aria-label="索引完成率">
        <div><span>索引进度</span><strong>{{ indexCompletion }}</strong></div>
        <i><b :style="{ width: indexCompletion }" /></i>
      </div>
    </section>
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>项目能力</h2>
          <p>从知识到决策的完整闭环</p>
        </div>
      </div>
      <div class="capability-list">
        <div v-for="capability in capabilities" :key="capability.title">
          <component :is="overviewIcon(capability.icon)" :size="18" /><span
            ><strong>{{ capability.title }}</strong
            ><small>{{ capability.description }}</small></span
          >
        </div>
      </div>
    </section>
    <section class="panel recent-runs-panel">
      <div class="panel-heading">
        <div>
          <h2>最近调研</h2>
          <p>项目内最近的 Agent 任务</p>
        </div>
        <button class="text-button" type="button" @click="router.push(routeTo('project-runs'))">
          查看队列 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="recent-run-list">
        <button
          v-for="run in recentRuns.slice(0, 3)"
          :key="run.id"
          class="recent-run-item"
          type="button"
          @click="router.push(routeTo('project-runs'))"
        >
          <span class="recent-run-status" :class="statusClass(run.status)"><i /></span>
          <span class="recent-run-copy"><strong>{{ run.title }}</strong><small>{{ run.time }} · {{ run.duration }}</small></span>
          <ArrowRight :size="13" />
        </button>
        <div v-if="!recentRuns.length" class="empty-detail-state panel-empty-state">
          <Clock3 :size="18" /><strong>暂无调研运行</strong>
          <span>已有调研运行后，这里会显示真实的运行记录。</span>
        </div>
      </div>
    </section>
    <section class="panel follow-up-panel">
      <div class="panel-heading">
        <div>
          <h2>下一步行动</h2>
          <p>把调研结论继续推进到可执行事项</p>
        </div>
        <button class="text-button" type="button" @click="router.push(routeTo('project-action-items'))">
          查看行动项 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="follow-up-list">
        <button
          v-for="item in actionItems.slice(0, 3)"
          :key="item.id"
          class="follow-up-item"
          type="button"
          @click="router.push(routeTo('project-action-items'))"
        >
          <span class="follow-up-status" :class="`status-${item.status}`"><i /></span>
          <span class="follow-up-copy"><strong>{{ item.title }}</strong><small>{{ item.owner }} · {{ item.due }}</small></span>
          <span class="follow-up-priority">{{ item.priority }}优先级</span>
        </button>
        <div v-if="!actionItems.length" class="empty-detail-state panel-empty-state">
          <CheckCircle2 :size="18" /><strong>暂无行动项</strong>
          <span>产生行动项后，这里会显示待跟进事项。</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  align-items: stretch;
}
.planning-callout {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  padding: 0.875rem 1.25rem;
  border-color: color-mix(in oklab, var(--teal) 24%, var(--workspace-border));
  background: color-mix(in oklab, var(--teal) 6%, var(--surface));
}
.planning-callout-icon {
  display: grid;
  width: 2.25rem;
  height: 2.25rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.625rem;
  background: #e3f7f3;
  color: var(--teal-dark);
}
.planning-callout > div:nth-child(2) {
  min-width: 0;
  flex: 1;
}
.planning-callout strong,
.planning-callout p {
  display: block;
}
.planning-callout strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.planning-callout p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.55;
}
.overview-grid > .panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
}
.project-statistics-panel {
  margin-bottom: 0.75rem;
}
.token-usage-panel {
  margin-bottom: 0.75rem;
}
.usage-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}
.usage-actions .text-button {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}
.token-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.625rem;
  padding: 0.125rem 1.25rem 1rem;
}
.token-summary-grid > div {
  min-width: 0;
  padding: 0.6875rem 0.75rem;
  border: 0.0625rem solid var(--workspace-divider);
  border-radius: 0.5rem;
  background: var(--surface-raised);
}
.token-summary-grid strong,
.token-summary-grid span {
  display: block;
}
.token-summary-grid strong {
  color: var(--workspace-text);
  font-size: 1rem;
  letter-spacing: -0.04em;
}
.token-summary-grid span {
  margin-top: 0.3125rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.token-usage-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(18rem, 0.8fr);
  gap: 1rem;
  padding: 0 1.25rem 1.125rem;
}
.token-heatmap-card,
.token-users-card {
  min-width: 0;
  padding: 0.75rem;
  border: 0.0625rem solid var(--workspace-divider);
  border-radius: 0.625rem;
  background: var(--surface-raised);
}
.usage-subheading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.usage-subheading strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.usage-subheading span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.token-heatmap {
  display: grid;
  grid-template-columns: repeat(10, minmax(0, 1fr));
  gap: 0.25rem;
}
.heat-cell,
.heatmap-legend i {
  display: block;
  aspect-ratio: 1;
  min-width: 0.5rem;
  border-radius: 0.1875rem;
  background: var(--workspace-divider);
}
.heat-cell.level-0,
.heatmap-legend i.level-0 { background: color-mix(in oklab, var(--teal) 5%, var(--surface)); }
.heat-cell.level-1,
.heatmap-legend i.level-1 { background: color-mix(in oklab, var(--teal) 20%, var(--surface)); }
.heat-cell.level-2,
.heatmap-legend i.level-2 { background: color-mix(in oklab, var(--teal) 38%, var(--surface)); }
.heat-cell.level-3,
.heatmap-legend i.level-3 { background: color-mix(in oklab, var(--teal) 62%, var(--surface)); }
.heat-cell.level-4,
.heatmap-legend i.level-4 { background: var(--teal); }
.heatmap-legend {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.25rem;
  margin-top: 0.5rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.heatmap-legend i {
  width: 0.625rem;
  min-width: 0.625rem;
}
.daily-bars {
  display: flex;
  height: 4.25rem;
  align-items: flex-end;
  gap: 0.1875rem;
  margin-top: 0.875rem;
  padding-top: 0.5rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.daily-bars > span {
  display: flex;
  min-width: 0;
  height: 100%;
  flex: 1 1 0;
  align-items: flex-end;
}
.daily-bars i {
  display: block;
  width: 100%;
  min-height: 0.125rem;
  border-radius: 0.1875rem 0.1875rem 0 0;
  background: color-mix(in oklab, var(--teal) 72%, var(--surface));
}
.user-bars {
  display: grid;
  gap: 0.75rem;
}
.user-bar-row {
  display: grid;
  grid-template-columns: minmax(5rem, 0.6fr) minmax(5rem, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
}
.user-bar-row > div:first-child {
  display: grid;
  min-width: 0;
  gap: 0.1875rem;
}
.user-bar-row strong,
.user-bar-row small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-bar-row strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.user-bar-row small,
.user-bar-row > span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.user-bar-track {
  height: 0.4375rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--workspace-divider);
}
.user-bar-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--teal);
}
.usage-empty {
  margin: 1rem 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.token-usage-chart {
  width: 100%;
  min-height: 15rem;
}
.token-breakdown-table {
  display: grid;
  gap: 0.25rem;
  margin-top: 0.75rem;
  padding-top: 0.625rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.token-breakdown-row {
  display: grid;
  grid-template-columns: minmax(6rem, 1fr) minmax(7rem, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.token-breakdown-row > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.token-breakdown-row > span:first-child {
  color: var(--workspace-text);
}
.token-breakdown-row small {
  display: block;
  margin-top: 0.125rem;
  overflow: hidden;
  color: var(--workspace-subtle);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.token-breakdown-header {
  padding-bottom: 0.25rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.token-breakdown-header > span:first-child {
  color: var(--workspace-subtle);
}
.model-label {
  color: var(--teal-dark);
}
.statistics-source {
  color: var(--teal-dark);
  font-size: 0.75rem;
  white-space: nowrap;
}
.project-stat-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.625rem;
  padding: 0.125rem 1.25rem 1rem;
}
.project-stat-grid > div {
  min-width: 0;
  padding: 0.75rem 0.8125rem;
  border: 0.0625rem solid var(--workspace-divider);
  border-radius: 0.5rem;
  background: var(--surface-raised);
}
.project-stat-grid strong,
.project-stat-grid span {
  display: block;
}
.project-stat-grid strong {
  color: var(--workspace-text);
  font-size: 1.125rem;
  letter-spacing: -0.04em;
}
.project-stat-grid span {
  margin-top: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.45;
}
.statistics-breakdowns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin: 0 1.25rem 1.125rem;
  padding-top: 0.875rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.statistics-breakdowns > div {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.375rem;
}
.breakdown-title {
  width: 100%;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.breakdown-item,
.breakdown-empty {
  padding: 0.25rem 0.4375rem;
  border-radius: 999px;
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  color: var(--teal-dark);
  font-size: 0.75rem;
}
.breakdown-empty {
  color: var(--workspace-muted);
  background: var(--surface-raised);
}
.overview-grid .overview-report {
  grid-column: 1 / -1;
}
.asset-health {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.625rem 1.25rem 1rem;
}
.asset-health > div {
  display: grid;
  gap: 0.375rem;
  min-width: 0;
}
.asset-health strong {
  color: var(--workspace-text);
  font-size: 1.5rem;
  letter-spacing: -0.05em;
}
.asset-health span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.health-progress {
  display: grid;
  gap: 0.375rem;
  padding: 0 1.25rem 1.125rem;
}
.health-progress > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.health-progress strong {
  color: var(--teal-dark);
  font-size: 0.75rem;
}
.health-progress > i {
  display: block;
  height: 0.3125rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--workspace-divider);
}
.health-progress > i b {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--teal);
}
.capability-list {
  flex: 1 1 auto;
  display: grid;
  align-content: space-evenly;
  gap: 0;
  padding: 0.125rem 1.5rem 0.875rem;
}
.capability-list > div {
  display: flex;
  align-items: center;
  gap: 0.6875rem;
  padding: 0.8125rem 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.capability-list > div:last-child {
  border-bottom: 0;
}
.capability-list svg {
  flex: 0 0 auto;
  color: var(--teal-dark);
}
.capability-list span {
  min-width: 0;
}
.capability-list strong,
.capability-list small {
  display: block;
}
.recent-runs-panel {
  min-width: 0;
}
.recent-run-list {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  justify-content: space-evenly;
  padding: 0.125rem 1rem 0.75rem;
}
.recent-run-list > .panel-empty-state {
  flex: 1 1 auto;
  min-height: 0;
}
.recent-run-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.25rem;
  border: 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.recent-run-item:last-child {
  border-bottom: 0;
}
.recent-run-item:hover .recent-run-copy strong {
  color: var(--teal-dark);
}
.recent-run-item > svg {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
}
.recent-run-status {
  display: grid;
  width: 1.25rem;
  height: 1.25rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.375rem;
  background: var(--surface-soft);
}
.recent-run-status i {
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: var(--workspace-subtle);
}
.recent-run-status.status-indexed {
  background: #e2f7f3;
}
.recent-run-status.status-indexed i {
  background: var(--teal);
}
.recent-run-status.status-running {
  background: #fff4da;
}
.recent-run-status.status-running i {
  background: #d89224;
}
.recent-run-status.status-failed {
  background: #fff0f0;
}
.recent-run-status.status-failed i {
  background: var(--red);
}
.recent-run-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.1875rem;
}
.recent-run-copy strong,
.recent-run-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.follow-up-panel {
  grid-column: 1 / -1;
}
.follow-up-list {
  flex: 1 1 auto;
  display: grid;
  align-content: space-evenly;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: 0.125rem 1rem 0.75rem;
  gap: 0.625rem;
}
.follow-up-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6875rem 0.75rem;
  border: 0.0625rem solid var(--workspace-divider);
  border-radius: 0.5rem;
  background: var(--surface-raised);
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.follow-up-item:hover {
  border-color: color-mix(in oklab, var(--teal) 40%, var(--workspace-border));
  background: color-mix(in oklab, var(--teal) 5%, var(--surface));
}
.follow-up-status {
  display: grid;
  width: 1.125rem;
  height: 1.125rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: #fff4da;
}
.follow-up-status i {
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: #d89224;
}
.follow-up-status.status-done {
  background: #e2f7f3;
}
.follow-up-status.status-done i {
  background: var(--teal);
}
.follow-up-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.1875rem;
}
.follow-up-copy strong,
.follow-up-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.follow-up-copy strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
}
.follow-up-copy small,
.follow-up-priority {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.follow-up-priority {
  flex: 0 0 auto;
  color: var(--teal-dark);
}
.recent-run-copy strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
}
.recent-run-copy small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.capability-list strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.capability-list small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  margin-top: 0.25rem;
}
.health-ring {
  width: 8.125rem;
  height: 8.125rem;
  border-radius: 50%;
  background: conic-gradient(var(--teal) 0 86%, #eaf1f1 86% 100%);
  display: grid;
  place-items: center;
  position: relative;
}
.health-ring::after {
  content: "";
  position: absolute;
  width: 6rem;
  height: 6rem;
  border-radius: 50%;
  background: white;
}
.health-ring span {
  z-index: 1;
  text-align: center;
}
.health-ring strong,
.health-ring small {
  display: block;
}
.health-ring strong {
  color: #1d3938;
  font-size: 1.375rem;
  letter-spacing: -0.06em;
}
.health-ring small {
  color: #91a2a3;
  font-size: 0.75rem;
  margin-top: 0.1875rem;
}
.health-list {
  display: grid;
  gap: 0.9375rem;
  flex: 1;
}
.health-list div {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.health-list span {
  color: #849398;
  font-size: 0.75rem;
}
.health-list strong {
  color: #3a4d52;
  font-size: 0.875rem;
}
.health-list i {
  margin-right: 0.4375rem;
}
.dot.teal {
  background: var(--teal);
}
.dot.amber {
  background: #e4a02a;
}
.dot.red {
  background: var(--red);
}
.mini-run-list {
  padding: 0.375rem 1.5rem 1.25rem;
}
.mini-run {
  min-height: 3.5rem;
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  border-bottom: 0.0625rem solid #edf1f1;
}
.mini-run:last-child {
  border-bottom: 0;
}
.mini-run > span:nth-child(2) {
  min-width: 0;
  flex: 1;
}
.mini-run strong,
.mini-run small {
  display: block;
}
.mini-run strong {
  color: #3c4d52;
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mini-run small {
  color: #9aa7a9;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}
.report-highlight {
  margin: 0.125rem 1.5rem 1.5rem;
  padding: 1.125rem 1.25rem;
  background: #f5fbfa;
  border: 0.0625rem solid #dcefeb;
  border-radius: 0.5625rem;
  display: flex;
  align-items: center;
  gap: 0.6875rem;
}
.report-file.large {
  width: 2.375rem;
  height: 2.375rem;
  background: #dff5f0;
  color: var(--teal-dark);
}
.report-highlight > div {
  flex: 1;
}
.report-highlight strong {
  color: #315052;
  font-size: 0.8125rem;
}
.report-highlight p {
  color: #899fa0;
  font-size: 0.75rem;
  margin: 0.375rem 0 0;
}

.upload-zone {
  border: 0.0625rem dashed #9ecfca;
  background: #f2fbfa;
  border-radius: 0.6875rem;
  min-height: 6.375rem;
  display: flex;
  align-items: center;
  gap: 0.8125rem;
  padding: 1.125rem 1.4375rem;
  margin-bottom: 1.3125rem;
  cursor: pointer;
}
.upload-zone:hover {
  background: #eaf8f6;
}
.upload-zone > div:nth-child(2) {
  flex: 1;
}
.upload-icon {
  display: grid;
  place-items: center;
  width: 2.4375rem;
  height: 2.4375rem;
  border-radius: 0.625rem;
  background: #d5f2ec;
  color: var(--teal-dark);
}
.upload-zone strong {
  color: #37625f;
  font-size: 0.8125rem;
}
.upload-zone p {
  color: #89a7a3;
  font-size: 0.75rem;
  margin: 0.375rem 0 0;
}

@media (max-width: 47.5rem) {
  .token-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding-inline: 0.875rem;
  }
  .token-usage-grid {
    grid-template-columns: 1fr;
    padding-inline: 0.875rem;
  }
  .planning-callout {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .planning-callout .button {
    margin-left: 3rem;
  }
  .project-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .statistics-breakdowns {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .overview-grid .overview-report {
    grid-column: auto;
  }
}

@media (max-width: 68.75rem) and (min-width: 47.51rem) {
  .token-summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .token-usage-grid {
    grid-template-columns: 1fr;
  }
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .recent-runs-panel {
    grid-column: 1 / -1;
  }

  .follow-up-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 47.5rem) {
  .follow-up-list {
    grid-template-columns: 1fr;
  }
}
</style>
