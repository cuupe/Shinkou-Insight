<script setup lang="ts">
import { ArrowRight, BarChart3, CheckCircle2, Plus } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { evaluationCases, notify } = useWorkspace();
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
        @click="notify('新建评估集接口待接入')"
      >
        <Plus :size="17" />新建评估
      </button></template
    ></PageHeader
  >
  <div class="evaluation-metrics">
    <div>
      <span>平均召回率</span><strong>87.5%</strong><small>+4.2% 较上次</small>
    </div>
    <div>
      <span>引用准确率</span><strong>81.5%</strong><small>+6.8% 较上次</small>
    </div>
    <div><span>结构化输出</span><strong>93.8%</strong><small>稳定</small></div>
  </div>
  <section class="panel table-panel">
    <div class="panel-heading">
      <div>
        <h2>评估用例</h2>
        <p>最近一次运行：今天 09:30</p>
      </div>
      <button
        class="text-button"
        type="button"
        @click="notify('运行评估接口待接入')"
      >
        <BarChart3 :size="15" />运行评估
      </button>
    </div>
    <div class="data-table evaluation-table">
      <div class="table-row table-header">
        <span>问题</span><span>召回</span><span>引用</span><span>JSON</span
        ><span>状态</span>
      </div>
      <div v-for="item in evaluationCases" :key="item.id" class="table-row">
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
            item.status === "passed"
              ? "通过"
              : item.status === "review"
                ? "待复核"
                : "失败"
          }}</span
        ><button
          class="icon-button small"
          type="button"
          @click="notify('评估详情接口待接入')"
        >
          <ArrowRight :size="15" />
        </button>
      </div>
    </div>
  </section>
  <div class="success-note">
    <CheckCircle2 :size="16" />评估数据接口已预留，接入后可替换本地演示数据。
  </div>
</template>
