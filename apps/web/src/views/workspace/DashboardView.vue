<script setup lang="ts">
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
import { useWorkspace } from "@/composables/useWorkspace";

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
</script>

<template>
  <PageHeader
    eyebrow="WORKSPACE OVERVIEW"
    title="早上好，林默 ✦"
    subtitle="这是 Shinkou Labs 的最新工作状态。"
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
    <article v-for="stat in stats" :key="stat.label" class="stat-card">
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
          <p>过去 30 天的运行量和完成情况</p>
        </div>
        <button
          class="select-button"
          type="button"
          @click="notify('时间范围切换接口待接入')"
        >
          过去 30 天 <ChevronDown :size="14" />
        </button>
      </div>
      <div class="chart-legend">
        <span><i class="legend-dot teal" />完成运行</span
        ><span><i class="legend-dot violet" />总运行</span>
      </div>
      <div class="fake-chart">
        <div class="chart-y">
          <span>60</span><span>40</span><span>20</span><span>0</span>
        </div>
        <div class="chart-area">
          <div class="chart-grid"><i /><i /><i /><i /></div>
          <svg
            viewBox="0 0 620 180"
            preserveAspectRatio="none"
            aria-label="运行趋势图"
          >
            <path
              d="M0 152 C48 143 55 126 94 134 S145 128 170 111 S225 118 251 100 S300 101 330 78 S379 88 408 66 S466 77 492 54 S551 62 620 22"
              fill="none"
              stroke="var(--workspace-chart-line)"
              stroke-width="3"
            />
            <path
              d="M0 152 C48 143 55 126 94 134 S145 128 170 111 S225 118 251 100 S300 101 330 78 S379 88 408 66 S466 77 492 54 S551 62 620 22 L620 180 L0 180Z"
              fill="url(#chartFill)"
              opacity=".16"
            />
            <defs>
              <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stop-color="var(--workspace-chart-fill)" />
                <stop offset="1" stop-color="var(--workspace-chart-fill)" stop-opacity="0" />
              </linearGradient>
            </defs>
          </svg>
          <div class="chart-x">
            <span>7/11</span><span>7/18</span><span>7/25</span><span>8/01</span
            ><span>8/08</span>
          </div>
        </div>
      </div>
      <div class="chart-summary">
        <div><strong>48</strong><span>总运行</span></div>
        <div><strong class="teal-text">91.4%</strong><span>完成率</span></div>
        <div><strong>2.4m</strong><span>平均耗时</span></div>
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
        <div class="focus-item">
          <span class="focus-number">01</span>
          <div>
            <strong>1 个运行需要重试</strong>
            <p>Hybrid 检索基线 · 昨天 18:27</p>
          </div>
          <button
            class="mini-button"
            type="button"
            @click="router.push(routeTo('project-runs'))"
          >
            <Activity :size="15" />
          </button>
        </div>
        <div class="focus-item">
          <span class="focus-number">02</span>
          <div>
            <strong>3 个证据冲突待审核</strong>
            <p>消息队列技术选型 · 运行 #2408</p>
          </div>
          <button
            class="mini-button"
            type="button"
            @click="router.push(routeTo('project-run-detail'))"
          >
            <ArrowRight :size="15" />
          </button>
        </div>
        <div class="focus-item">
          <span class="focus-number">03</span>
          <div>
            <strong>2 个行动项即将到期</strong>
            <p>最近截止日期为今天</p>
          </div>
          <button
            class="mini-button"
            type="button"
            @click="router.push(routeTo('project-action-items'))"
          >
            <ArrowRight :size="15" />
          </button>
        </div>
      </div>
    </section>
  </div>
  <div class="two-column-grid">
    <section class="panel table-panel">
      <div class="panel-heading">
        <div>
          <h2>最近运行</h2>
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
    <section class="panel report-panel">
      <div class="panel-heading">
        <div>
          <h2>最近报告</h2>
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
