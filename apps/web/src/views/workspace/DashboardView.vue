<script setup lang="ts">
import { computed } from "vue";
import { Activity, ArrowDownRight, ArrowRight, FileText } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import TokenUsageChart from "@/components/common/TokenUsageChart.vue";

const {
  router,
  routeTo,
  workspaceId,
  stats,
  recentRuns,
  reports,
  projects,
  workspace,
  statistics,
  displayName,
  iconForStat,
  statusClass,
} = useWorkspace();

function openReport(report: { id: string; projectId?: number }) {
  if (report.projectId) {
    router.push({
      name: "project-reports",
      params: { workspaceId: workspaceId.value, projectId: report.projectId },
      query: { reportId: report.id },
    });
    return;
  }
  router.push(routeTo("project-reports"));
}
const trendPoints = computed(() => {
  const points = statistics.value?.dailyTrend || [];
  const max = Math.max(
    1,
    ...points.map((point) =>
      Math.max(Number(point.runs) || 0, Number(point.reports) || 0),
    ),
  );
  return points.map((point, index) => ({
    ...point,
    x: points.length <= 1 ? 50 : (index / (points.length - 1)) * 100,
    runsY: 100 - ((Number(point.runs) || 0) / max) * 100,
    reportsY: 100 - ((Number(point.reports) || 0) / max) * 100,
  }));
});
const runLine = computed(() =>
  trendPoints.value.map((point) => `${point.x},${point.runsY}`).join(" "),
);
const reportLine = computed(() =>
  trendPoints.value.map((point) => `${point.x},${point.reportsY}`).join(" "),
);
const hasTrendData = computed(() =>
  trendPoints.value.some(
    (point) =>
      (Number(point.runs) || 0) > 0 || (Number(point.reports) || 0) > 0,
  ),
);
const trendLabels = computed(() => {
  const points = trendPoints.value;
  if (points.length <= 5) return points;
  const indexes = [
    0,
    Math.floor((points.length - 1) / 3),
    Math.floor(((points.length - 1) * 2) / 3),
    points.length - 1,
  ];
  return indexes
    .filter((index, position) => indexes.indexOf(index) === position)
    .map((index) => points[index])
    .filter((point): point is (typeof points)[number] => Boolean(point));
});
const trendTotal = computed(() =>
  trendPoints.value.reduce(
    (total, point) => total + (Number(point.runs) || 0),
    0,
  ),
);
const trendReportTotal = computed(() =>
  trendPoints.value.reduce(
    (total, point) => total + (Number(point.reports) || 0),
    0,
  ),
);
const tokenBreakdown = computed(() => statistics.value?.tokenBreakdown || []);
const tokenChartItems = computed(() =>
  tokenBreakdown.value.map((item) => ({
    label: `${item.projectName || "未命名项目"} · ${item.userName || `用户 ${item.userId}`}`,
    detail: `${item.modelName || "模型未标注"} · ${item.runCount} 次运行`,
    tokens: Number(item.totalTokens) || 0,
  })),
);
function formatTokens(value: number | string | undefined) {
  return Number(value || 0).toLocaleString("zh-CN");
}
const greeting = computed(() => {
  const hour = new Date().getHours();
  if (hour < 5) return "夜深了";
  if (hour < 12) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
});
const dashboardSubtitle = computed(() =>
  workspace.name
    ? `这是 ${workspace.name} 的最新工作状态。`
    : "工作区信息加载后，这里会显示最新工作状态。",
);
/* 本周关注：基于项目真实汇总数据生成 */
const focusItems = computed(() => {
  const totalRuns = projects.reduce(
    (sum, project) => sum + (Number(project.runs) || 0),
    0,
  );
  const totalReports = projects.reduce(
    (sum, project) => sum + (Number(project.reports) || 0),
    0,
  );
  const items = [
    {
      number: "01",
      title: `跟进 ${projects.length} 个活跃项目`,
      detail: "查看各项目的知识资产与调研进展",
      route: "workspace-projects",
      icon: "arrow",
      ariaLabel: "查看项目",
    },
    {
      number: "02",
      title: `${totalRuns} 次调研运行记录`,
      detail: "查看运行结果并处理失败任务",
      route: "project-runs",
      icon: "activity",
      ariaLabel: "查看任务队列",
    },
    {
      number: "03",
      title: `${totalReports} 份报告已沉淀`,
      detail: "查看最新结论和决策依据",
      route: "project-reports",
      icon: "arrow",
      ariaLabel: "查看报告",
    },
  ];
  return projects.length ? items : [];
});
function focusIcon(icon: string) {
  return icon === "activity" ? Activity : ArrowRight;
}
</script>

<template>
  <PageHeader
    eyebrow="WORKSPACE OVERVIEW"
    :title="`${greeting}，${displayName}`"
    :subtitle="dashboardSubtitle"
  >
  </PageHeader>
  <div class="stat-grid">
    <article
      v-for="stat in stats"
      :key="stat.label"
      class="stat-card"
      :class="`stat-tone-${stat.tone}`"
    >
      <div class="stat-top">
        <span>{{ stat.label }}</span
        ><span class="stat-icon" :class="`tone-${stat.tone}`"
          ><component :is="iconForStat(stat.icon)" :size="17"
        /></span>
      </div>
      <strong>{{ stat.value }}</strong>
      <div class="stat-trend">
        <ArrowDownRight :size="14" class="trend-up" />{{ stat.trend }}
      </div>
    </article>
  </div>
  <div class="dashboard-grid">
    <section class="panel chart-panel">
      <div class="panel-heading">
        <div>
          <h2>运行与洞察趋势</h2>
          <p>展示后端已记录的运行趋势</p>
        </div>
      </div>
      <div v-if="hasTrendData" class="trend-chart-wrap">
        <div class="chart-legend">
          <span><i class="legend-dot teal" />调研运行</span>
          <span><i class="legend-dot violet" />报告沉淀</span>
        </div>
        <div class="trend-chart">
          <div class="chart-y">
            <span>高</span><span>中</span><span>低</span>
          </div>
          <div class="chart-area">
            <div class="chart-grid"><i /><i /><i /></div>
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-label="运行与报告趋势图"
            >
              <polyline
                :points="runLine"
                fill="none"
                stroke="var(--teal)"
                stroke-width="1.5"
                vector-effect="non-scaling-stroke"
              />
              <polyline
                :points="reportLine"
                fill="none"
                stroke="var(--violet)"
                stroke-width="1.5"
                vector-effect="non-scaling-stroke"
              />
            </svg>
            <div class="chart-x">
              <span v-for="point in trendLabels" :key="point.date">{{
                point.date
              }}</span>
            </div>
          </div>
        </div>
        <div class="chart-summary">
          <div>
            <strong>{{ trendTotal }}</strong
            ><span>近 {{ trendPoints.length }} 天调研运行</span>
          </div>
          <div>
            <strong>{{ trendReportTotal }}</strong
            ><span>近 {{ trendPoints.length }} 天新增报告</span>
          </div>
          <div>
            <strong>{{ statistics?.summary?.openActionItemCount ?? 0 }}</strong
            ><span>待跟进行动项</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-state chart-empty">
        <Activity :size="20" />
        <strong>暂无运行趋势数据</strong>
        <span>完成调研运行或生成报告后，这里会展示真实的按日趋势。</span>
      </div>
    </section>
  </div>
  <section class="panel workspace-token-panel">
    <div class="panel-heading">
      <div>
        <h2>Token 使用明细</h2>
        <p>按项目、成员和模型查看真实运行消耗</p>
      </div>
      <span class="statistics-source">工作区范围</span>
    </div>
    <div v-if="tokenChartItems.length" class="workspace-token-content">
      <TokenUsageChart :items="tokenChartItems" />
      <div class="workspace-token-table">
        <div class="workspace-token-row workspace-token-header">
          <span>项目 / 成员</span><span>模型</span><span>输入 / 输出</span
          ><span>合计</span>
        </div>
        <div
          v-for="item in tokenBreakdown"
          :key="`${item.projectId}-${item.userId}-${item.modelName}`"
          class="workspace-token-row"
        >
          <span
            ><strong>{{ item.projectName || "未命名项目" }}</strong
            ><small
              >{{ item.userName || `用户 ${item.userId}` }} ·
              {{ item.runCount }} 次运行</small
            ></span
          >
          <span class="model-label">{{ item.modelName || "模型未标注" }}</span>
          <span
            >{{ formatTokens(item.inputTokens) }} /
            {{ formatTokens(item.outputTokens) }}</span
          >
          <strong>{{ formatTokens(item.totalTokens) }}</strong>
        </div>
      </div>
    </div>
    <div v-else class="empty-state workspace-token-empty">
      <Activity :size="20" />
      <strong>暂无真实 Token 记录</strong>
      <span>完成一次 Agent 运行后，这里会按项目、成员和模型展示用量。</span>
    </div>
  </section>
  <div class="two-column-grid">
    <section class="panel table-panel" aria-labelledby="recent-runs-title">
      <div class="panel-heading">
        <div>
          <h2 id="recent-runs-title">最近运行</h2>
          <p>跨项目的 Agent 调研活动</p>
        </div>
        <button
          v-if="projects.length"
          class="text-button"
          type="button"
          @click="router.push(routeTo('project-runs'))"
        >
          查看全部 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="data-table">
        <div class="table-row table-header">
          <span>调研运行</span><span>项目</span><span>状态</span
          ><span>时间</span>
        </div>
        <div v-for="run in recentRuns" :key="run.id" class="table-row">
          <div class="run-title">
            <span class="run-icon"><Activity :size="15" /></span>
            <div>
              <strong>{{ run.title }}</strong
              ><small>{{ run.id }}</small>
            </div>
          </div>
          <span class="muted-cell">{{ run.project }}</span
          ><span class="status-badge" :class="statusClass(run.status)"
            ><i />{{ run.statusLabel }}</span
          ><span class="muted-cell">{{ run.time }}</span>
        </div>
        <div v-if="!recentRuns.length" class="empty-state panel-empty-state">
          <Activity :size="18" /><strong>暂无调研运行</strong>
          <span>有调研运行后，这里会显示真实运行记录。</span>
        </div>
      </div>
    </section>
    <section class="panel report-panel" aria-labelledby="recent-reports-title">
      <div class="panel-heading">
        <div>
          <h2 id="recent-reports-title">最近报告</h2>
          <p>团队最近沉淀的决策依据</p>
        </div>
        <button
          v-if="projects.length"
          class="text-button"
          type="button"
          @click="router.push(routeTo('project-reports'))"
        >
          查看全部 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="report-list">
        <button
          v-for="report in reports"
          :key="report.id"
          class="report-item"
          type="button"
          :aria-label="`打开报告：${report.title}`"
          @click="openReport(report)"
        >
          <span class="report-file"><FileText :size="17" /></span
          ><span
            ><strong>{{ report.title }}</strong
            ><small>{{ report.project }} · {{ report.updated }}</small></span
          ><ArrowRight :size="15" />
        </button>
        <div v-if="!reports.length" class="empty-state panel-empty-state">
          <FileText :size="18" /><strong>暂无报告</strong>
          <span>完成调研并生成报告后，这里会显示真实报告。</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.875rem;
  margin-bottom: 1.125rem;
}
.stat-card {
  position: relative;
  overflow: hidden;
  background: var(--surface);
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.6875rem;
  padding: 1rem 1.125rem;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}
.stat-card::before {
  position: absolute;
  inset: 0 0 auto;
  height: 0.125rem;
  content: "";
  background: var(--stat-accent, var(--teal));
  opacity: 0.7;
}
.stat-card:hover {
  transform: translateY(-0.125rem);
  border-color: color-mix(
    in oklab,
    var(--stat-accent, var(--teal)) 42%,
    var(--workspace-border)
  );
  box-shadow: 0 0.625rem 1.5rem rgba(21, 53, 52, 0.07);
}
.stat-tone-teal {
  --stat-accent: #15b8a6;
}
.stat-tone-violet {
  --stat-accent: #8b7cf6;
}
.stat-tone-amber {
  --stat-accent: #f59e0b;
}
.stat-tone-blue {
  --stat-accent: #4b86c8;
}
.stat-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.stat-icon {
  width: 1.875rem;
  height: 1.875rem;
  display: grid;
  place-items: center;
  border-radius: 0.5rem;
}
.tone-teal,
.teal-bg {
  color: #078b7d;
  background: #e2f7f3;
}
.tone-violet,
.violet-bg {
  color: #6e62d6;
  background: #eeebff;
}
.tone-amber,
.amber-bg {
  color: #bb7911;
  background: #fff2da;
}
.tone-blue {
  color: #4b86c8;
  background: #e8f2fd;
}
.stat-card > strong {
  display: block;
  font-size: 1.5625rem;
  letter-spacing: -0.05em;
  color: var(--workspace-text);
  margin: 0.75rem 0 0.25rem;
}
.stat-trend {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--workspace-muted);
}
.trend-up {
  color: var(--teal);
  transform: rotate(180deg);
}
.dashboard-grid {
  grid-template-columns: minmax(0, 1.55fr) minmax(18.75rem, 0.9fr);
  gap: 0.875rem;
  margin-bottom: 0.875rem;
}
.chart-panel {
  min-height: 18rem;
}
.chart-empty {
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 0.5rem;
  min-height: 12rem;
  margin: 0 1.25rem 1.25rem;
  border: 0.0625rem dashed var(--workspace-border);
  border-radius: 0.625rem;
}
.chart-empty svg {
  color: var(--workspace-muted);
}
.chart-empty strong {
  color: var(--workspace-text);
}
.chart-empty span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.6;
}
.dashboard-empty {
  display: grid;
  justify-items: center;
  gap: 0.375rem;
  padding: 1.25rem 1rem;
}
.dashboard-empty svg {
  color: var(--workspace-muted);
}
.dashboard-empty strong {
  color: var(--workspace-text);
}
.dashboard-empty span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.chart-panel .panel-heading {
  padding: 1.125rem 1.25rem 0.75rem;
}
.chart-legend {
  gap: 1rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.chart-panel .chart-legend {
  padding: 0 1.25rem;
  justify-content: flex-end;
  margin-top: 0;
  margin-bottom: 0.5rem;
}
.legend-dot {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 50%;
  display: inline-block;
  margin-right: 0.3125rem;
}
.legend-dot.teal {
  background: var(--teal);
}
.legend-dot.violet {
  background: var(--violet);
}
.fake-chart {
  display: flex;
  height: 11.5rem;
  padding: 0.75rem 1.25rem 0;
}
.trend-chart {
  width: 100%;
  height: 13.75rem;
  padding: 0 0.625rem;
}
.chart-y {
  width: 1.5625rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding-bottom: 1.5625rem;
  color: var(--workspace-chart-axis);
  font-size: 0.75rem;
}
.chart-area {
  min-width: 0;
  flex: 1;
  position: relative;
}
.chart-grid {
  position: absolute;
  inset: 0 0 1.5625rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.chart-grid i {
  border-top: 0.0625rem dashed var(--workspace-chart-grid);
}
.chart-area svg {
  position: absolute;
  inset: 0 0 1.5625rem;
  width: 100%;
  height: calc(100% - 1.5625rem);
  overflow: visible;
}
.chart-x {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  display: flex;
  justify-content: space-between;
  color: var(--workspace-chart-axis);
  font-size: 0.75rem;
}
.chart-summary {
  display: flex;
  gap: 2.5rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  margin: 0 1.5rem;
  padding: 1.125rem 0 1.375rem;
}
.chart-summary div {
  display: grid;
  gap: 0.25rem;
}
.chart-summary strong {
  color: var(--workspace-text);
  font-size: 1rem;
}
.chart-summary span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.teal-text {
  color: var(--teal-dark) !important;
}
.violet-text {
  color: var(--violet) !important;
}
.amber-text {
  color: var(--amber) !important;
}
.red-text {
  color: var(--red) !important;
}
.focus-panel {
  min-height: 21.125rem;
}
.focus-list {
  padding: 0.375rem 1.5rem 1.5rem;
}
.focus-empty {
  margin: 0;
  padding: 0.75rem 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.focus-item {
  display: flex;
  align-items: center;
  gap: 0.6875rem;
  padding: 0.9375rem 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.focus-item:last-child {
  border-bottom: 0;
}
.focus-number {
  font-size: 0.75rem;
  color: var(--workspace-muted);
  font-weight: 700;
  align-self: flex-start;
  padding-top: 0.125rem;
}
.focus-item > div {
  min-width: 0;
  flex: 1;
}
.focus-item strong {
  display: block;
  color: var(--workspace-text);
  font-size: 0.8125rem;
  font-weight: 650;
}
.focus-item p {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  margin: 0.3125rem 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mini-button {
  display: inline-grid;
  place-items: center;
  width: 1.6875rem;
  height: 1.6875rem;
  background: var(--surface-soft);
  color: var(--workspace-muted);
  border: 0;
  border-radius: 0.4375rem;
  cursor: pointer;
}
.mini-button:hover {
  color: var(--teal-dark);
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
}
.workspace-token-panel {
  margin-bottom: 1.125rem;
}
.workspace-token-content {
  display: grid;
  grid-template-columns: minmax(20rem, 1fr) minmax(24rem, 1.1fr);
  gap: 1rem;
  padding: 0 1.5rem 1.25rem;
}
.workspace-token-table {
  display: grid;
  align-content: start;
  gap: 0.25rem;
  padding: 0.75rem;
  border: 0.0625rem solid var(--workspace-divider);
  border-radius: 0.625rem;
  background: var(--surface-raised);
}
.workspace-token-row {
  display: grid;
  grid-template-columns: minmax(8rem, 1.25fr) minmax(7rem, 1fr) minmax(
      6rem,
      0.8fr
    ) auto;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  min-height: 2.25rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.workspace-token-row:last-child {
  border-bottom: 0;
}
.workspace-token-row > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-token-row strong {
  display: block;
  overflow: hidden;
  color: var(--workspace-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-token-row small {
  display: block;
  margin-top: 0.125rem;
  overflow: hidden;
  color: var(--workspace-subtle);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-token-header {
  min-height: 1.75rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.workspace-token-header strong {
  color: var(--workspace-subtle);
}
.workspace-token-empty {
  min-height: 12rem;
  margin: 0 1.5rem 1.25rem;
  border: 0.0625rem dashed var(--workspace-border);
  border-radius: 0.625rem;
}
.two-column-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(18.75rem, 0.9fr);
  gap: 1.125rem;
}
.table-panel,
.report-panel {
  overflow: hidden;
}
.table-panel .data-table {
  overflow-x: auto;
  padding-bottom: 0.625rem;
}
.data-table {
  width: 100%;
}
.table-row {
  display: grid;
  grid-template-columns: 1.7fr 1.1fr 0.75fr 0.85fr;
  gap: 1rem;
  align-items: center;
  min-height: 3.6875rem;
  padding: 0 1.5rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  font-size: 0.75rem;
}
.table-panel .table-row {
  min-width: 40.625rem;
}
.table-row.table-header {
  min-height: 2.25rem;
  border-top: 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  background: var(--surface-raised);
}
.run-title,
.member-cell,
.asset-name-cell {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  min-width: 0;
}
.run-title > div,
.member-cell > span:last-child,
.asset-name-cell > span:last-child {
  min-width: 0;
}
.run-title strong,
.member-cell strong,
.asset-name-cell strong {
  display: block;
  color: var(--workspace-text);
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.run-title small,
.member-cell small,
.asset-name-cell small {
  display: block;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  margin-top: 0.25rem;
}
.run-icon,
.report-file,
.config-icon {
  display: grid;
  place-items: center;
  width: 1.8125rem;
  height: 1.8125rem;
  border-radius: 0.5rem;
  color: #739396;
  background: #edf7f5;
  flex: 0 0 auto;
}
.muted-cell {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  white-space: nowrap;
  font-size: 0.75rem;
}
.status-badge i {
  display: inline-block;
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: #a7b1b4;
}
.status-indexed {
  color: #0d9586;
}
.status-indexed i {
  background: #18b39f;
}
.status-running,
.status-indexing {
  color: #bc7d1d;
}
.status-running i,
.status-indexing i {
  background: #eeaa32;
}
.status-failed {
  color: #ce5b5b;
}
.status-failed i {
  background: #e36d6d;
}
.status-completed {
  color: #0d9586;
}
.status-completed i {
  background: #18b39f;
}
.status-muted {
  color: #9ba7aa;
}
.status-muted i {
  background: #b6c0c2;
}
.report-list {
  padding: 0.25rem 1.375rem 1rem;
}
.report-item {
  width: 100%;
  padding: 0.8125rem 0;
  border: 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  background: none;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  text-align: left;
  color: inherit;
  cursor: pointer;
  border-radius: 0.4375rem;
  transition:
    background 0.2s ease,
    padding 0.2s ease;
}
.report-item:hover {
  padding-inline: 0.5rem;
  background: color-mix(in oklab, var(--teal) 7%, var(--surface));
}
.report-item:last-child {
  border-bottom: 0;
}
.report-item > span:nth-child(2) {
  min-width: 0;
  flex: 1;
}
.report-item strong,
.report-item small,
.report-item em {
  display: block;
}
.report-item strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.report-item small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  margin-top: 0.25rem;
}
.report-item em {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  font-style: normal;
  margin-top: 0.375rem;
}
.report-item > svg {
  color: var(--workspace-muted);
}
.report-item:hover strong {
  color: var(--teal-dark);
}

@media (max-width: 68.75rem) {
  .dashboard-grid,
  .workspace-token-content,
  .two-column-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 47.5rem) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid,
  .two-column-grid {
    grid-template-columns: 1fr;
  }

  .workspace-token-content {
    padding-inline: 0.875rem;
  }

  .workspace-token-row {
    grid-template-columns: minmax(7rem, 1fr) minmax(6rem, 1fr) auto;
  }

  .workspace-token-row > span:nth-child(3) {
    display: none;
  }

  .chart-summary {
    gap: 1.5rem;
  }

  .focus-list {
    padding-inline: 1.125rem;
  }
}

@media (max-width: 30rem) {
  .stat-grid {
    grid-template-columns: 1fr;
  }

  .chart-summary {
    gap: 1.125rem;
  }

  .chart-summary strong {
    font-size: 0.875rem;
  }
}
</style>
