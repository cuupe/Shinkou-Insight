<script setup lang="ts">
import { ArrowRight, MoreHorizontal, Plus, RefreshCw } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { recentRuns, statusClass, router, routeTo, notify } = useWorkspace();
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
      <div><strong>48</strong><span>总运行</span></div>
      <div><strong>91.4%</strong><span>完成率</span></div>
      <div><strong>2.4m</strong><span>平均耗时</span></div>
      <button
        class="select-button"
        type="button"
        @click="notify('运行筛选接口待接入')"
      >
        全部状态 <MoreHorizontal :size="15" />
      </button>
    </div>
    <div class="data-table run-table">
      <div class="table-row table-header">
        <span>调研运行</span><span>状态</span><span>耗时</span
        ><span>Tokens</span><span>时间</span>
      </div>
      <div v-for="run in recentRuns" :key="run.id" class="table-row">
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
