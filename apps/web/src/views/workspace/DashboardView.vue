<script setup lang="ts">
import { ref } from "vue";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  FileText,
  Plus,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import TrendChart from "@/components/common/TrendChart.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { dashboardData, userProfile } from "@/data/mock";

const {
  router,
  routeTo,
  notify,
  stats,
  recentRuns,
  reports,
  iconForStat,
  statusClass,
} = useWorkspace();
const trendRanges = dashboardData.trend.ranges;
const trendRangeIndex = ref(1);
const trendRange = () => trendRanges[trendRangeIndex.value];
function cycleTrendRange() {
  trendRangeIndex.value = (trendRangeIndex.value + 1) % trendRanges.length;
  notify(`已切换到${trendRange()}`);
}
function focusIcon(icon: string) {
  return icon === "activity" ? Activity : ArrowRight;
}
</script>

<template>
  <PageHeader
    eyebrow="WORKSPACE OVERVIEW"
    :title="`${dashboardData.greeting}，${userProfile.name} ${dashboardData.titleSuffix}`"
    :subtitle="dashboardData.subtitle"
  >
    <template #action
      ><button
        class="button button-primary"
        type="button"
        @click="router.push(routeTo('project-new-run'))"
      >
        <Plus :size="17" />创建调研
      </button></template
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
          <h2>{{ dashboardData.trend.title }}</h2>
          <p>{{ dashboardData.trend.description }}</p>
        </div>
        <button
          class="select-button"
          type="button"
          aria-label="切换趋势时间范围"
          @click="cycleTrendRange"
        >
          {{ trendRange() }} <ChevronDown :size="14" />
        </button>
      </div>
      <div class="chart-legend">
        <span v-for="(item, index) in dashboardData.trend.legend" :key="item"
          ><i class="legend-dot" :class="index === 0 ? 'teal' : 'violet'" />{{ item }}</span
        >
      </div>
      <TrendChart
        :labels="dashboardData.trend.xAxis"
        :series="dashboardData.trend.series"
      />
      <div class="chart-summary">
        <div v-for="item in dashboardData.trend.summary" :key="item.label">
          <strong :class="item.tone === 'teal' ? 'teal-text' : undefined">{{ item.value }}</strong
          ><span>{{ item.label }}</span>
        </div>
      </div>
    </section>
    <section class="panel focus-panel">
      <div class="panel-heading">
        <div>
          <h2>本周关注</h2>
          <p>需要你确认的事项</p>
        </div>
        <button
          class="text-button"
          type="button"
          @click="router.push(routeTo('project-action-items'))"
        >
          查看全部 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="focus-list">
        <div v-for="item in dashboardData.focusItems" :key="item.number" class="focus-item">
          <span class="focus-number">{{ item.number }}</span>
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.detail }}</p>
          </div>
          <button
            class="mini-button"
            type="button"
            :aria-label="item.ariaLabel"
            @click="router.push(routeTo(item.route))"
          >
            <component :is="focusIcon(item.icon)" :size="15" />
          </button>
        </div>
      </div>
    </section>
  </div>
  <div class="two-column-grid">
    <section class="panel table-panel" aria-labelledby="recent-runs-title">
      <div class="panel-heading">
        <div>
          <h2 id="recent-runs-title">最近运行</h2>
          <p>跨项目的 Agent 调研活动</p>
        </div>
        <button
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
      </div>
    </section>
    <section class="panel report-panel" aria-labelledby="recent-reports-title">
      <div class="panel-heading">
        <div>
          <h2 id="recent-reports-title">最近报告</h2>
          <p>团队最近沉淀的决策依据</p>
        </div>
        <button
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
          @click="router.push(routeTo('project-reports'))"
        >
          <span class="report-file"><FileText :size="17" /></span
          ><span
            ><strong>{{ report.title }}</strong
            ><small>{{ report.project }} · {{ report.updated }}</small></span
          ><ArrowRight :size="15" />
        </button>
      </div>
    </section>
  </div>
</template>
