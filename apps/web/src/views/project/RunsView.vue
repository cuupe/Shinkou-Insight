<script setup lang="ts">
import { ArrowRight, MoreHorizontal, Plus, RefreshCw } from "@lucide/vue";
import { computed, ref } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { runStatusFilters, runSummary } from "@/data/mock";
const { recentRuns, statusClass, router, routeTo, notify } = useWorkspace();
const filterIndex = ref(0);
const filters = runStatusFilters;
const filterLabel = computed(() => filters[filterIndex.value]);
const filteredRuns = computed(() =>
  filterLabel.value === "全部状态"
    ? recentRuns
    : recentRuns.filter((run) => run.statusLabel === filterLabel.value),
);

function cycleFilter() {
  filterIndex.value = (filterIndex.value + 1) % filters.length;
  notify(`已切换到${filterLabel.value}`);
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / RESEARCH"
    title="调研运行"
    subtitle="查看 Agent 任务进度、耗时和输出"
    ><template #action
      ><button
        class="button button-primary"
        type="button"
        @click="router.push(routeTo('project-new-run'))"
      >
        <Plus :size="17" />创建调研
      </button></template
    ></PageHeader
  >
  <section class="panel table-panel">
    <div class="run-summary-row">
      <div v-for="item in runSummary" :key="item.label">
        <strong>{{ item.value }}</strong><span>{{ item.label }}</span>
      </div>
      <button
        class="select-button"
        type="button"
        @click="cycleFilter"
      >
        {{ filterLabel }} <MoreHorizontal :size="15" />
      </button>
    </div>
    <div class="data-table run-table">
      <div class="table-row table-header">
        <span>调研运行</span><span>状态</span><span>耗时</span
        ><span>Tokens</span><span>时间</span>
      </div>
      <div v-for="run in filteredRuns" :key="run.id" class="table-row">
        <div class="run-title">
          <span class="run-icon"><RefreshCw :size="15" /></span>
          <div>
            <strong>{{ run.title }}</strong
            ><small>{{ run.id }} · {{ run.project }}</small>
          </div>
        </div>
        <span class="status-badge" :class="statusClass(run.status)"
          ><i />{{ run.statusLabel }}</span
        ><span class="muted-cell">{{ run.duration }}</span
        ><span class="muted-cell">{{ run.tokens }}</span
        ><span class="muted-cell">{{ run.time }}</span
        ><button
          class="icon-button small"
          type="button"
          @click="
            router.push({
              name: 'project-run-detail',
              params: {
                ...routeTo('project-run-detail').params,
                runId: run.id,
              },
            })
          "
        >
          <ArrowRight :size="15" />
        </button>
      </div>
    </div>
  </section>
</template>
