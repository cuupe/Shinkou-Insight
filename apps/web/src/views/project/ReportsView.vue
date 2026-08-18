<script setup lang="ts">
import {
  CheckCircle2,
  Download,
  FileText,
  SlidersHorizontal,
} from "@lucide/vue";
import { computed, ref } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { reportFilters, reportReaderCopy } from "@/data/mock";
const { reports, notify } = useWorkspace();
const selectedReportId = ref(reports[0]?.id ?? "");
const filterIndex = ref(0);
const filters = reportFilters;
const filterLabel = computed(() => filters[filterIndex.value]);
const filteredReports = computed(() =>
  filterLabel.value === "全部"
    ? reports
    : reports.filter((report) => report.status === filterLabel.value),
);
const selectedReport = computed(
  () => reports.find((report) => report.id === selectedReportId.value) ?? reports[0],
);

function cycleFilter() {
  filterIndex.value = (filterIndex.value + 1) % filters.length;
}

function exportReport() {
  if (!selectedReport.value) return;
  const content = `# ${selectedReport.value.title}\n\n项目：${selectedReport.value.project}\n版本：${selectedReport.value.version}\n`;
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${selectedReport.value.title}.md`;
  link.click();
  URL.revokeObjectURL(url);
  notify("报告已导出");
}

function editReport() {
  if (!selectedReport.value) return;
  const title = window.prompt("请输入报告标题", selectedReport.value.title);
  if (!title?.trim()) return;
  selectedReport.value.title = title.trim();
  notify("报告标题已更新");
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / OUTPUT"
    title="报告"
    subtitle="把可验证的证据组织成可执行的决策依据"
    ><template #action
      ><button
        class="button button-secondary"
        type="button"
        @click="exportReport"
      >
        <Download :size="16" />导出报告
      </button></template
    ></PageHeader
  >
  <div class="reports-layout">
    <section class="panel reports-list-panel">
      <div class="panel-heading">
        <div>
          <h2>全部报告</h2>
          <p>{{ filteredReports.length }} 份报告 · {{ filterLabel }} · 按更新时间排序</p>
        </div>
        <button
          class="icon-button small"
          type="button"
          @click="cycleFilter"
        >
          <SlidersHorizontal :size="16" />
        </button>
      </div>
      <div class="report-list full-list">
        <button
          v-for="report in filteredReports"
          :key="report.id"
          class="report-item"
          :class="{ 'report-item-selected': report.id === selectedReportId }"
          type="button"
          @click="selectedReportId = report.id"
        >
          <span class="report-file"><FileText :size="17" /></span
          ><span
            ><strong>{{ report.title }}</strong
            ><small>{{ report.project }} · {{ report.updated }}</small
            ><em>{{ report.version }} · {{ report.citations }} 条引用</em></span
          ><span
            class="status-badge"
            :class="
              report.status === '已发布' ? 'status-indexed' : 'status-muted'
            "
            ><i />{{ report.status }}</span
          >
        </button>
      </div>
    </section>
    <section class="panel report-reader">
      <div class="reader-toolbar">
        <span
          class="status-badge"
          :class="selectedReport?.status === '已发布' ? 'status-indexed' : 'status-muted'"
          ><i />{{ selectedReport?.status }} · {{ selectedReport?.version }}</span
        ><button
          class="text-button"
          type="button"
          @click="editReport"
        >
          编辑
        </button>
      </div>
      <article class="markdown-body">
        <p class="eyebrow">{{ reportReaderCopy.eyebrow }}</p>
        <h2>{{ selectedReport?.title }}</h2>
        <p class="lead">{{ selectedReport?.lead }}</p>
        <hr />
        <h3>{{ reportReaderCopy.summaryHeading }}</h3>
        <p>{{ selectedReport?.summary }}</p>
        <div class="recommendation-box">
          <span class="quick-icon teal-bg"><CheckCircle2 :size="18" /></span>
          <div>
            <strong>{{ selectedReport?.recommendation }}</strong>
            <p>{{ selectedReport?.recommendationDetail }}</p>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>
