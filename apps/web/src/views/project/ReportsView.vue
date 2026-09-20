<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  Archive,
  CheckCircle2,
  Clipboard,
  Download,
  Edit3,
  FileText,
  Search,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useWorkspace } from "@/composables/useWorkspace";
import { reportsApi } from "@/api/reports";
import { useRoute } from "vue-router";
import { formatDateTime } from "@/lib/utils";

const { reports, notify, workspaceId, projectId } = useWorkspace();
const route = useRoute();
const reportItems = reactive(reports);
const filters = ["全部", "已发布", "草稿"];
const searchQuery = ref("");
const filterLabel = ref(filters[0] || "全部");
const selectedReportId = ref(reportItems[0]?.id ?? "");
const editorOpen = ref(false);

watch(
  () => route.query.reportId,
  (reportId) => {
    if (reportId) selectedReportId.value = String(reportId);
  },
  { immediate: true },
);

const editForm = reactive({
  title: "",
  lead: "",
  summary: "",
  recommendation: "",
  recommendationDetail: "",
});

const filteredReports = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return reportItems.filter((report) => {
    const matchesStatus =
      filterLabel.value === "全部" || report.status === filterLabel.value;
    const matchesQuery =
      !query ||
      [report.title, report.project, report.lead]
        .join(" ")
        .toLowerCase()
        .includes(query);
    return matchesStatus && matchesQuery;
  });
});

const selectedReport = computed(
  () =>
    filteredReports.value.find(
      (report) => report.id === selectedReportId.value,
    ) ??
    filteredReports.value[0] ??
    reportItems[0],
);

const publishedCount = computed(
  () => reportItems.filter((report) => report.status === "已发布").length,
);
const citationCount = computed(() =>
  reportItems.some((report) => report.citations != null)
    ? reportItems.reduce((total, report) => total + (report.citations || 0), 0)
    : null,
);
function citationLabel(citations: number | null) {
  return citations == null ? "引用信息未提供" : `${citations} 条引用`;
}
function citationFooter(citations: number | null) {
  return citations == null
    ? "后端未提供引用信息"
    : `结论已关联 ${citations} 条可验证引用`;
}

function openEditor() {
  if (!selectedReport.value) return;
  Object.assign(editForm, {
    title: selectedReport.value.title,
    lead: selectedReport.value.lead,
    summary: selectedReport.value.summary,
    recommendation: selectedReport.value.recommendation,
    recommendationDetail: selectedReport.value.recommendationDetail,
  });
  editorOpen.value = true;
}

async function saveReport() {
  const report = selectedReport.value;
  if (!report || !editForm.title.trim()) return;
  const content = [
    editForm.lead.trim(),
    editForm.summary.trim(),
    editForm.recommendation.trim(),
    editForm.recommendationDetail.trim(),
  ]
    .filter(Boolean)
    .join("\n\n");
  try {
    const updated = await reportsApi.update(
      workspaceId.value,
      projectId.value,
      report.id,
      {
        title: editForm.title.trim(),
        content,
        lead: editForm.lead.trim(),
        summary: editForm.summary.trim(),
        recommendation: editForm.recommendation.trim(),
        recommendationDetail: editForm.recommendationDetail.trim(),
      },
    );
    Object.assign(report, {
      title: updated.title || editForm.title.trim(),
      lead: String(updated.lead ?? editForm.lead.trim()),
      summary: String(updated.summary ?? (editForm.summary.trim() || content)),
      recommendation: String(
        updated.recommendation ?? editForm.recommendation.trim(),
      ),
      recommendationDetail: String(
        updated.recommendationDetail ?? editForm.recommendationDetail.trim(),
      ),
      updated: formatDateTime(updated.updatedAt || report.updated, "—"),
    });
  } catch (error) {
    notify(error instanceof Error ? error.message : "报告保存失败");
    return;
  }
  editorOpen.value = false;
  notify("报告内容已保存");
}

async function toggleReportStatus() {
  const report = selectedReport.value;
  if (!report) return;
  const nextStatus = report.status === "已发布" ? "DRAFT" : "PUBLISHED";
  try {
    const updated = await reportsApi.update(
      workspaceId.value,
      projectId.value,
      report.id,
      { status: nextStatus },
    );
    report.status =
      String(updated.status || nextStatus) === "PUBLISHED" ? "已发布" : "草稿";
    notify(report.status === "已发布" ? "报告已发布" : "报告已移回草稿");
  } catch (error) {
    notify(error instanceof Error ? error.message : "报告状态更新失败");
  }
}

async function exportReport() {
  const report = selectedReport.value;
  if (!report) return;
  try {
    const blob = await reportsApi.export(
      workspaceId.value,
      projectId.value,
      report.id,
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${report.title}.md`;
    link.click();
    URL.revokeObjectURL(url);
    notify("报告已导出");
  } catch (error) {
    notify(error instanceof Error ? error.message : "报告导出失败");
  }
}

async function copySummary() {
  const report = selectedReport.value;
  if (!report) return;
  try {
    await navigator.clipboard.writeText(`${report.title}\n\n${report.summary}`);
    notify("摘要已复制");
  } catch {
    notify("当前环境不支持复制");
  }
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / OUTPUT"
    title="报告"
    subtitle="把可验证的证据组织成可执行的决策依据"
  >
    <template #action>
      <div class="heading-actions">
        <button
          class="button button-secondary"
          type="button"
          @click="copySummary"
        >
          <Clipboard :size="16" />复制摘要
        </button>
        <button
          class="button button-primary"
          type="button"
          @click="exportReport"
        >
          <Download :size="16" />导出报告
        </button>
      </div>
    </template>
  </PageHeader>

  <div class="report-metrics">
    <div class="report-metric">
      <span class="metric-icon teal-bg"><FileText :size="16" /></span>
      <div>
        <strong>{{ reportItems.length }}</strong
        ><span>全部报告</span>
      </div>
    </div>
    <div class="report-metric">
      <span class="metric-icon violet-bg"><Send :size="16" /></span>
      <div>
        <strong>{{ publishedCount }}</strong
        ><span>已发布</span>
      </div>
    </div>
    <div class="report-metric">
      <span class="metric-icon amber-bg"><Archive :size="16" /></span>
      <div>
        <strong>{{ reportItems.length - publishedCount }}</strong
        ><span>待完善草稿</span>
      </div>
    </div>
    <div class="report-metric">
      <span class="metric-icon blue-bg"><CheckCircle2 :size="16" /></span>
      <div>
        <strong>{{ citationCount == null ? "—" : citationCount }}</strong
        ><span>证据引用</span>
      </div>
    </div>
  </div>

  <div class="reports-layout">
    <section class="panel reports-list-panel">
      <div class="panel-heading report-list-heading">
        <div>
          <div class="section-kicker">RESEARCH LIBRARY</div>
          <h2>
            全部报告
            <span class="count-pill">{{ filteredReports.length }}</span>
          </h2>
          <p>按更新时间排序，选择一份报告查看决策摘要</p>
        </div>
      </div>
      <div class="report-toolbar">
        <label class="search-control"
          ><Search :size="15" /><input
            v-model="searchQuery"
            type="search"
            placeholder="搜索报告或项目"
            aria-label="搜索报告或项目"
        /></label>
        <Select v-model="filterLabel">
          <SelectTrigger class="report-filter-select" aria-label="筛选报告状态"
            ><SelectValue placeholder="全部报告"
          /></SelectTrigger>
          <SelectContent
            ><SelectItem
              v-for="filter in filters"
              :key="filter"
              :value="filter"
              >{{ filter }}</SelectItem
            ></SelectContent
          >
        </Select>
      </div>
      <div class="report-list full-list">
        <button
          v-for="report in filteredReports"
          :key="report.id"
          class="report-item"
          :class="{ 'report-item-selected': report.id === selectedReport?.id }"
          type="button"
          @click="selectedReportId = report.id"
        >
          <span class="report-file"><FileText :size="17" /></span>
          <span class="report-item-copy"
            ><strong>{{ report.title }}</strong
            ><small>{{ report.project || "—" }} · {{ report.updated }}</small
            ><em
              >{{ report.version }} · {{ citationLabel(report.citations) }}</em
            ></span
          >
          <span
            class="status-badge"
            :class="
              report.status === '已发布' ? 'status-indexed' : 'status-muted'
            "
            ><i />{{ report.status }}</span
          >
        </button>
        <p v-if="!filteredReports.length" class="empty-state">
          {{
            reportItems.length
              ? "没有匹配的报告，试试其他关键词或筛选条件。"
              : "暂无报告，完成调研并生成报告后会显示后端返回的内容。"
          }}
        </p>
      </div>
    </section>

    <section class="panel report-reader">
      <div class="reader-toolbar">
        <div class="reader-status">
          <span
            class="status-badge"
            :class="
              selectedReport?.status === '已发布'
                ? 'status-indexed'
                : 'status-muted'
            "
            ><i />{{ selectedReport?.status }}</span
          ><span class="reader-updated"
            >{{ selectedReport?.version }} · 更新于
            {{ selectedReport?.updated }}</span
          >
        </div>
        <div class="heading-actions">
          <button class="text-button" type="button" @click="openEditor">
            <Edit3 :size="14" />编辑</button
          ><button
            class="text-button"
            type="button"
            @click="toggleReportStatus"
          >
            {{ selectedReport?.status === "已发布" ? "移回草稿" : "发布报告" }}
          </button>
        </div>
      </div>
      <article v-if="selectedReport" class="markdown-body">
        <p class="eyebrow">TECHNICAL DECISION REPORT</p>
        <h2>{{ selectedReport.title }}</h2>
        <p v-if="selectedReport.lead" class="lead">{{ selectedReport.lead }}</p>
        <div class="reader-meta-grid">
          <div>
            <span>所属项目</span
            ><strong>{{ selectedReport.project || "—" }}</strong>
          </div>
          <div>
            <span>报告版本</span><strong>{{ selectedReport.version }}</strong>
          </div>
          <div>
            <span>证据引用</span
            ><strong>{{
              selectedReport.citations == null
                ? "—"
                : selectedReport.citations + " 条"
            }}</strong>
          </div>
        </div>
        <hr />
        <h3>01 / 报告正文</h3>
        <p v-if="selectedReport.summary">{{ selectedReport.summary }}</p>
        <div v-else class="empty-state">该报告暂无正文内容。</div>
        <div
          v-if="
            selectedReport.recommendation || selectedReport.recommendationDetail
          "
          class="recommendation-box"
        >
          <span class="quick-icon teal-bg"><CheckCircle2 :size="18" /></span>
          <div>
            <strong>{{ selectedReport.recommendation }}</strong>
            <p>{{ selectedReport.recommendationDetail }}</p>
          </div>
        </div>
        <div class="reader-footer-note">
          <span
            ><CheckCircle2 :size="14" />{{
              citationFooter(selectedReport.citations)
            }}</span
          >
        </div>
      </article>
      <div v-else class="empty-reader">选择一份报告开始阅读</div>
    </section>
  </div>

  <Dialog v-model:open="editorOpen">
    <DialogContent class="report-editor-dialog">
      <DialogHeader
        ><DialogTitle>编辑报告</DialogTitle
        ><DialogDescription
          >更新报告内容后保存，版本和引用数量保持不变。</DialogDescription
        ></DialogHeader
      >
      <div class="editor-form">
        <label>报告标题<input v-model="editForm.title" type="text" /></label
        ><label>导语<textarea v-model="editForm.lead" rows="3" /></label
        ><label>执行摘要<textarea v-model="editForm.summary" rows="4" /></label>
        <div class="form-grid">
          <label
            >推荐方案<input
              v-model="editForm.recommendation"
              type="text" /></label
          ><label
            >下一步建议<input
              v-model="editForm.recommendationDetail"
              type="text"
          /></label>
        </div>
      </div>
      <DialogFooter
        ><button
          class="button button-secondary"
          type="button"
          @click="editorOpen = false"
        >
          取消</button
        ><button
          class="button button-primary"
          type="button"
          @click="saveReport"
        >
          保存更改
        </button></DialogFooter
      >
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.heading-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.report-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.125rem;
}
.report-metric {
  display: flex;
  align-items: center;
  gap: 0.6875rem;
  padding: 0.9375rem 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.6875rem;
  background: var(--surface);
}
.report-metric > div {
  display: grid;
  gap: 0.1875rem;
}
.report-metric strong {
  color: var(--workspace-text);
  font-size: 1.125rem;
  letter-spacing: -0.04em;
}
.report-metric span:not(.metric-icon) {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.metric-icon {
  display: grid;
  place-items: center;
  width: 1.9375rem;
  height: 1.9375rem;
  border-radius: 0.5rem;
}
.blue-bg {
  color: #4b86c8;
  background: #e8f2fd;
}
.reports-layout {
  display: grid;
  grid-template-columns: minmax(18rem, 0.7fr) minmax(0, 1.55fr);
  gap: 1.125rem;
  align-items: stretch;
}
.reports-list-panel {
  overflow: hidden;
}
.report-list-heading {
  padding-bottom: 1rem;
}
.section-kicker {
  margin-bottom: 0.4rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.13em;
}
.report-list-heading h2 {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
}
.count-pill {
  display: inline-grid;
  place-items: center;
  min-width: 1.25rem;
  height: 1.125rem;
  padding: 0 0.3125rem;
  border-radius: 0.3125rem;
  background: var(--surface-soft);
  color: var(--workspace-muted);
  font-size: 0.75rem;
  font-weight: 700;
}
.report-toolbar {
  display: flex;
  gap: 0.5rem;
  padding: 0 1.5rem 1rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.search-control {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  min-width: 0;
  flex: 1;
  padding: 0 0.625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  color: var(--workspace-muted);
  background: var(--surface-soft);
}
.search-control input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  padding: 0.4375rem 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.75rem;
}
.search-control input::placeholder {
  color: var(--workspace-subtle);
}
.report-filter-select {
  width: 6.75rem;
  flex: 0 0 auto;
}
.full-list {
  padding: 0.5rem 1rem 0.625rem;
}
.report-item {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  width: 100%;
  padding: 0.75rem 0.5rem;
  border: 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  border-radius: 0.5rem;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    background 160ms ease,
    transform 160ms ease;
}
.report-item:last-child {
  border-bottom: 0;
}
.report-item:hover {
  background: color-mix(in oklab, var(--teal) 5%, var(--surface));
  transform: translateX(0.125rem);
}
.report-item-selected {
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  box-shadow: inset 0.125rem 0 var(--teal);
}
.report-file {
  display: grid;
  place-items: center;
  width: 1.875rem;
  height: 1.875rem;
  flex: 0 0 auto;
  border-radius: 0.5rem;
  color: #739396;
  background: #edf7f5;
}
.report-item-copy {
  min-width: 0;
  flex: 1;
}
.report-item-copy strong,
.report-item-copy small,
.report-item-copy em {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.report-item-copy strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.report-item-copy small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.report-item-copy em {
  margin-top: 0.25rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  font-style: normal;
}
.report-item .status-badge {
  flex: 0 0 auto;
  align-self: flex-start;
  margin-top: 0.125rem;
}
.empty-state,
.empty-reader {
  color: var(--workspace-muted);
  font-size: 0.8125rem;
  line-height: 1.6;
  text-align: center;
}
.empty-state {
  padding: 1.5rem 0.75rem;
}
.report-reader {
  min-height: 38.75rem;
  overflow: hidden;
}
.reader-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.5625rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.reader-status {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  min-width: 0;
  flex: 1;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
}
.reader-updated {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.markdown-body {
  max-width: 52rem;
  padding: 2.25rem 3.375rem 2.5rem;
  color: var(--workspace-muted);
  font-family: Georgia, "Songti SC", serif;
  font-size: 0.75rem;
  line-height: 1.85;
}
.markdown-body .eyebrow {
  margin-bottom: 0.875rem;
  font-family: "Geist", "Microsoft YaHei", sans-serif;
}
.markdown-body h2 {
  margin: 0 0 0.875rem;
  color: var(--workspace-text);
  font-family: "Geist", "Microsoft YaHei", sans-serif;
  font-size: 1.5rem;
  letter-spacing: -0.045em;
  line-height: 1.3;
}
.markdown-body .lead {
  color: var(--workspace-muted);
  font-size: 0.875rem;
  line-height: 1.7;
}
.reader-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin: 1.5rem 0;
  padding: 0.875rem 0;
  border-top: 0.0625rem solid var(--workspace-divider);
  border-bottom: 0.0625rem solid var(--workspace-divider);
  font-family: "Geist", "Microsoft YaHei", sans-serif;
}
.reader-meta-grid div {
  display: grid;
  gap: 0.25rem;
}
.reader-meta-grid span {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.reader-meta-grid strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.markdown-body hr {
  margin: 1.625rem 0;
  border: 0;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.markdown-body h3 {
  margin: 1.5625rem 0 0.5625rem;
  color: var(--workspace-text);
  font-family: "Geist", "Microsoft YaHei", sans-serif;
  font-size: 0.8125rem;
}
.recommendation-box {
  display: flex;
  align-items: center;
  gap: 0.6875rem;
  margin: 1.25rem 0;
  padding: 0.9375rem;
  border: 0.0625rem solid
    color-mix(in oklab, var(--teal) 22%, var(--workspace-border));
  border-radius: 0.5rem;
  background: color-mix(in oklab, var(--teal) 8%, var(--surface));
  font-family: "Geist", "Microsoft YaHei", sans-serif;
}
.recommendation-box strong,
.recommendation-box p {
  display: block;
}
.recommendation-box strong {
  color: var(--teal-dark);
  font-size: 0.8125rem;
}
.recommendation-box p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.reader-footer-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  font-family: "Geist", "Microsoft YaHei", sans-serif;
  font-size: 0.75rem;
}
.reader-footer-note > span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  color: var(--workspace-muted);
}
.empty-reader {
  display: grid;
  min-height: 30rem;
  place-items: center;
}
.report-editor-dialog {
  max-width: 42rem !important;
}
.editor-form {
  display: grid;
  gap: 0.875rem;
}
.editor-form label {
  display: grid;
  gap: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.editor-form input,
.editor-form textarea {
  width: 100%;
  resize: vertical;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  outline: 0;
  padding: 0.625rem 0.6875rem;
  background: var(--surface-soft);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.8125rem;
}
.editor-form input:focus,
.editor-form textarea:focus,
.search-control:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 16%, transparent);
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
@media (max-width: 68.75rem) {
  .reports-layout {
    grid-template-columns: 1fr;
  }
  .report-reader {
    min-height: 0;
  }
}
@media (max-width: 47.5rem) {
  .heading-actions {
    flex-wrap: wrap;
  }
  .report-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .reader-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
  .reader-status {
    width: 100%;
  }
  .markdown-body {
    padding: 1.5625rem 1.4375rem 2.5rem;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 30rem) {
  .report-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .report-filter-select {
    width: 100%;
  }
  .reader-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
