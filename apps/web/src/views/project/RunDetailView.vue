<script setup lang="ts">
import { ArrowLeft, Check, Copy, FileText, X } from "@lucide/vue";
import { useRouter } from "vue-router";
import { recentRuns } from "@/data/mock";
import { runDetailData } from "@/data/mock";
import { useWorkspace } from "@/composables/useWorkspace";
const router = useRouter();
const { copied, selectedEvidence, copyEvidence, notify, statusClass } = useWorkspace();
const run = recentRuns[0]!;
const evidence = runDetailData.evidence;

function generateReport() {
  const content = `# ${run.title}\n\n${run.project}\n\n${runDetailData.summary}`;
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${run.title}.md`;
  link.click();
  URL.revokeObjectURL(url);
  notify("报告已生成并下载");
}
</script>

<template>
  <button class="text-button back-button" type="button" @click="router.back()">
    <ArrowLeft :size="15" />返回调研运行
  </button>
  <div class="run-detail-top">
    <div>
      <p class="eyebrow">RESEARCH / RUN DETAIL</p>
      <h1>{{ run.title }}</h1>
      <p class="page-subtitle">
        {{ run.id }} · {{ run.project }} · {{ run.time }}
      </p>
    </div>
    <span class="status-badge" :class="statusClass(run.status)"><i />{{ run.statusLabel }}</span>
  </div>
  <div class="run-metrics">
    <div v-for="metric in runDetailData.metrics" :key="metric.label">
      <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong>
    </div>
  </div>
  <div class="research-workspace">
    <section class="panel markdown-body">
      <p class="eyebrow">FINAL SUMMARY</p>
      <h2>结论摘要</h2>
      <p>{{ runDetailData.summary }}</p>
      <h3>关键判断</h3>
      <ul>
        <li v-for="point in runDetailData.keyPoints" :key="point">{{ point }}</li>
      </ul>
      <button
        class="button button-secondary button-sm"
        type="button"
        @click="generateReport"
      >
        <FileText :size="14" />生成报告
      </button>
    </section>
    <aside class="panel evidence-panel">
      <div class="panel-heading">
        <div>
          <h2>证据与冲突</h2>
          <p>点击证据查看引用片段</p>
        </div>
      </div>
      <button
        v-for="(item, index) in evidence"
        :key="item.code"
        class="evidence-card"
        :class="{ selected: selectedEvidence === index }"
        type="button"
        @click="selectedEvidence = index"
      >
        <div>
          <span
            class="evidence-code"
            :class="{ conflict: item.code === 'C1' }"
            >{{ item.code }}</span
          ><strong>{{ item.title }}</strong>
        </div>
        <small>{{ item.source }}</small>
      </button>
      <div v-if="selectedEvidence >= 0" class="evidence-drawer">
        <div>
          <span class="eyebrow">EVIDENCE</span>
          <h2>{{ evidence[selectedEvidence]?.title }}</h2>
          <p>
            {{ runDetailData.evidenceDetail }}
          </p>
        </div>
        <div>
          <button
            class="button button-secondary button-sm"
            type="button"
            @click="copyEvidence"
          >
            <Copy :size="14" />{{ copied ? "已复制" : "复制引用" }}</button
          ><button
            class="icon-button small"
            type="button"
            @click="selectedEvidence = -1"
          >
            <X :size="17" />
          </button>
        </div>
      </div>
    </aside>
  </div>
</template>
