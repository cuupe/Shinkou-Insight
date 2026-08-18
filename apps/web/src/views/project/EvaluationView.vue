<script setup lang="ts">
import { ArrowRight, BarChart3, CheckCircle2, Plus } from "@lucide/vue";
import { computed, ref } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { evaluationStatusLabels, evaluationSummary } from "@/data/mock";
const { evaluationCases, notify } = useWorkspace();
const selectedCaseId = ref(evaluationCases[0]?.id ?? "");
const isRunning = ref(false);
const selectedCase = computed(() =>
  evaluationCases.find((item) => item.id === selectedCaseId.value),
);
function evaluationStatusLabel(status: string) {
  return evaluationStatusLabels[status as keyof typeof evaluationStatusLabels] || status;
}

function createEvaluation() {
  const query = window.prompt("请输入评估问题");
  if (!query?.trim()) return;
  evaluationCases.push({
    id: `eval-local-${Date.now()}`,
    query: query.trim(),
    recall: "—",
    citation: "—",
    json: "—",
    status: "review",
  });
  notify("评估用例已创建");
}

function runEvaluation() {
  if (isRunning.value) return;
  isRunning.value = true;
  notify("评估运行中");
  window.setTimeout(() => {
    evaluationCases.forEach((item) => {
      if (item.recall === "—") {
        item.recall = "88%";
        item.citation = "84%";
        item.json = "通过";
        item.status = "passed";
      }
    });
    isRunning.value = false;
    notify("评估已完成");
  }, 900);
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / QUALITY"
    title="评估"
    subtitle="用可重复的测试集衡量检索和回答质量"
    ><template #action
      ><button
        class="button button-primary"
        type="button"
        @click="createEvaluation"
      >
        <Plus :size="17" />新建评估
      </button></template
    ></PageHeader
  >
  <div class="evaluation-metrics">
    <div v-for="metric in evaluationSummary.metrics" :key="metric.label">
      <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.change }}</small>
    </div>
  </div>
  <section class="panel table-panel">
    <div class="panel-heading">
      <div>
        <h2>评估用例</h2>
        <p>{{ evaluationSummary.lastRun }}</p>
      </div>
      <button
        class="text-button"
        type="button"
        @click="runEvaluation"
      >
        <BarChart3 :size="15" />{{ isRunning ? "评估中..." : "运行评估" }}
      </button>
    </div>
    <div class="data-table evaluation-table">
      <div class="table-row table-header">
        <span>问题</span><span>召回</span><span>引用</span><span>JSON</span
        ><span>状态</span>
      </div>
      <div
        v-for="item in evaluationCases"
        :key="item.id"
        class="table-row"
        :class="{ 'table-row-selected': item.id === selectedCaseId }"
        @click="selectedCaseId = item.id"
      >
        <div>
          <strong>{{ item.query }}</strong
          ><small>{{ item.id }}</small>
        </div>
        <span>{{ item.recall }}</span
        ><span>{{ item.citation }}</span
        ><span>{{ item.json }}</span
        ><span
          class="status-badge"
          :class="item.status === 'passed' ? 'status-indexed' : 'status-muted'"
          ><i />{{
            evaluationStatusLabel(item.status)
          }}</span
        ><button
          class="icon-button small"
          type="button"
          @click.stop="selectedCaseId = item.id"
        >
          <ArrowRight :size="15" />
        </button>
      </div>
    </div>
  </section>
  <div class="success-note">
    <CheckCircle2 :size="16" />{{ selectedCase ? `已选择：${selectedCase.query}` : "请选择一个评估用例" }}
  </div>
</template>
