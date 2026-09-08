<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  Search,
  ShieldCheck,
  Upload,
  Users,
  Zap,
} from "@lucide/vue";
import { useWorkspace } from "@/composables/useWorkspace";
import PageHeader from "@/components/common/PageHeader.vue";
const { selectedProject, router, routeTo, assets, recentRuns, actionItems, statusClass, statistics } =
  useWorkspace();

const quickActions = [
  { label: "上传资料", description: "PDF、Markdown、TXT", route: "project-assets", tone: "teal" },
  { label: "检索测试", description: "验证知识库召回", route: "project-playground", tone: "violet" },
];

const indexedCount = computed(
  () => assets.filter((item) => item.status === "indexed").length,
);
const indexCompletion = computed(() => {
  if (!assets.length) return "0%";
  return `${Math.round((indexedCount.value / assets.length) * 100)}%`;
});
const projectSummary = computed(() => statistics.value?.summary);
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
        <Upload v-if="index === 0" :size="18" />
        <Search v-else-if="index === 1" :size="18" />
        <Zap v-else :size="18" />
      </span>
      <span><strong>{{ action.label }}</strong><small>{{ action.description }}</small></span>
      <ArrowRight :size="15" />
    </button>
  </div>
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
.overview-grid > .panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
}
.project-statistics-panel {
  margin-bottom: 0.75rem;
}
.statistics-source {
  color: var(--teal-dark);
  font-size: 0.5625rem;
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
  font-size: 0.5rem;
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
  font-size: 0.5625rem;
}
.breakdown-item,
.breakdown-empty {
  padding: 0.25rem 0.4375rem;
  border-radius: 999px;
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  color: var(--teal-dark);
  font-size: 0.5rem;
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
  font-size: 0.5625rem;
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
  font-size: 0.5rem;
}
.health-progress strong {
  color: var(--teal-dark);
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
  font-weight: 650;
}
.follow-up-copy small,
.follow-up-priority {
  color: var(--workspace-muted);
  font-size: 0.5rem;
}
.follow-up-priority {
  flex: 0 0 auto;
  color: var(--teal-dark);
}
.recent-run-copy strong {
  color: var(--workspace-text);
  font-size: 0.5625rem;
  font-weight: 650;
}
.recent-run-copy small {
  color: var(--workspace-muted);
  font-size: 0.5rem;
}
.capability-list strong {
  color: var(--workspace-text);
  font-size: 0.625rem;
}
.capability-list small {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
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
  font-size: 0.625rem;
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
  font-size: 0.625rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mini-run small {
  color: #9aa7a9;
  font-size: 0.5625rem;
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
  font-size: 0.6875rem;
}
.report-highlight p {
  color: #899fa0;
  font-size: 0.5625rem;
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
  font-size: 0.6875rem;
}
.upload-zone p {
  color: #89a7a3;
  font-size: 0.5625rem;
  margin: 0.375rem 0 0;
}

@media (max-width: 47.5rem) {
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
