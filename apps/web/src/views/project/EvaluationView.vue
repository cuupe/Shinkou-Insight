<script setup lang="ts">
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  MessageCircle,
  Plus,
  RefreshCw,
  Target,
  Zap,
} from "@lucide/vue";
import { computed, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import PageHeader from "@/components/common/PageHeader.vue";
import ProjectWorkflow from "@/components/project/ProjectWorkflow.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";
import { evaluationApi } from "@/api/evaluation";
import { statisticsApi } from "@/api/statistics";
import { formatDateTime } from "@/lib/utils";

const {
  evaluationCases: evaluationSeed,
  notify,
  workspaceId,
  projectId,
  statistics,
  router,
  routeTo,
} = useWorkspace();
const route = useRoute();
const evaluationCases = reactive(evaluationSeed);
const selectedCaseId = ref(evaluationCases[0]?.id ?? "");
const statusFilter = ref("all");
const isRunning = ref(false);
const isUpdatingCase = ref(false);
const lastRunLabel = ref("尚未同步评估数据");
const caseDialogOpen = ref(false);
const caseForm = reactive({ query: "", expectedAnswer: "" });

watch(
  () => evaluationCases.map((item) => item.id),
  (ids) => {
    const requestedCaseId = route.query.caseId;
    if (typeof requestedCaseId === "string" && ids.includes(requestedCaseId)) {
      selectedCaseId.value = requestedCaseId;
    } else if (!selectedCaseId.value || !ids.includes(selectedCaseId.value)) {
      selectedCaseId.value = ids[0] || "";
    }
  },
  { immediate: true },
);
watch(
  () => route.query.caseId,
  (id) => {
    if (typeof id === "string") selectedCaseId.value = id;
  },
);

const statusLabels: Record<string, string> = {
  passed: "已通过",
  review: "待复核",
  failed: "未通过",
};

const statusFilters = [
  { label: "全部用例", value: "all" },
  { label: "已通过", value: "passed" },
  { label: "待复核", value: "review" },
  { label: "未通过", value: "failed" },
];

const selectedCase = computed(() =>
  evaluationCases.find((item) => item.id === selectedCaseId.value),
);

const filteredCases = computed(() => {
  if (statusFilter.value === "all") return evaluationCases;
  return evaluationCases.filter((item) => item.status === statusFilter.value);
});

const parsePercent = (value: unknown) => {
  const parsed = Number.parseFloat(String(value));
  return Number.isFinite(parsed) ? parsed : null;
};

function averageMetric(field: "recall" | "citation" | "json") {
  const values = evaluationCases
    .map((item) => parsePercent(item[field]))
    .filter((value): value is number => value !== null);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatMetric(value: number | null) {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

const qualityRows = computed(() => [
  { label: "召回率", value: averageMetric("recall"), tone: "teal" },
  { label: "引用准确率", value: averageMetric("citation"), tone: "violet" },
  { label: "结构化输出", value: averageMetric("json"), tone: "amber" },
]);

const overallScore = computed(() => {
  const values = qualityRows.value
    .map((item) => item.value)
    .filter((value): value is number => value !== null);
  if (!values.length) return "—";
  return `${(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)}%`;
});

const metricCards = computed(() => [
  {
    label: "综合质量分",
    value: overallScore.value,
    change: "基于全部用例均值",
    icon: Target,
    tone: "teal",
  },
  {
    label: "平均召回率",
    value: formatMetric(averageMetric("recall")),
    change: "覆盖检索结果",
    icon: BarChart3,
    tone: "blue",
  },
  {
    label: "引用准确率",
    value: formatMetric(averageMetric("citation")),
    change: "基于证据匹配",
    icon: ClipboardCheck,
    tone: "violet",
  },
  {
    label: "通过用例",
    value: `${evaluationCases.filter((item) => item.status === "passed").length}/${evaluationCases.length}`,
    change: "人工核验状态",
    icon: Zap,
    tone: "amber",
  },
]);

const qualityTrendPoints = computed(() => {
  const points = (statistics.value?.dailyTrend || []).filter(
    (point) =>
      point.recall != null || point.citation != null || point.jsonScore != null,
  );
  return points.map((point, index) => ({
    ...point,
    x: points.length <= 1 ? 50 : (index / (points.length - 1)) * 100,
    recallY: 100 - Number(point.recall ?? 0),
    citationY: 100 - Number(point.citation ?? 0),
    jsonY: 100 - Number(point.jsonScore ?? 0),
  }));
});
const qualityTrendHasData = computed(() => qualityTrendPoints.value.length > 0);
const qualityRecallLine = computed(() =>
  qualityTrendPoints.value
    .filter((point) => point.recall != null)
    .map((point) => `${point.x},${point.recallY}`)
    .join(" "),
);
const qualityCitationLine = computed(() =>
  qualityTrendPoints.value
    .filter((point) => point.citation != null)
    .map((point) => `${point.x},${point.citationY}`)
    .join(" "),
);
const qualityJsonLine = computed(() =>
  qualityTrendPoints.value
    .filter((point) => point.jsonScore != null)
    .map((point) => `${point.x},${point.jsonY}`)
    .join(" "),
);
const qualityTrendLabels = computed(() => {
  const points = qualityTrendPoints.value;
  if (points.length <= 5) return points;
  return [
    points[0],
    points[Math.floor((points.length - 1) / 2)],
    points[points.length - 1],
  ].filter((point): point is (typeof points)[number] => Boolean(point));
});

function displayQuery(item: { id: string; query: string }) {
  return item.query || item.id;
}

function evaluationStatusLabel(status: string) {
  return statusLabels[status] || status;
}

function createEvaluation() {
  caseForm.query = "";
  caseForm.expectedAnswer = "";
  caseDialogOpen.value = true;
}

async function saveEvaluationCase() {
  const query = caseForm.query.trim();
  if (!query) return;
  try {
    const created = await evaluationApi.create(workspaceId.value, {
      projectId: projectId.value > 0 ? projectId.value : undefined,
      query,
      expectedAnswer: caseForm.expectedAnswer.trim() || undefined,
    });
    const id = String(created.id ?? "—");
    evaluationCases.unshift({
      id,
      projectId: projectId.value > 0 ? projectId.value : undefined,
      query: String(created.query || query),
      expectedAnswer: String(created.expectedAnswer || caseForm.expectedAnswer.trim()),
      recall: created.recall == null ? "—" : `${String(created.recall)}%`,
      citation: created.citation == null ? "—" : `${String(created.citation)}%`,
      json: created.jsonScore == null ? "—" : `${String(created.jsonScore)}%`,
      status: String(created.status || "review").toLowerCase(),
    });
    selectedCaseId.value = id;
    statusFilter.value = "all";
    caseDialogOpen.value = false;
    notify("评估用例已创建");
  } catch (error) {
    notify(error instanceof Error ? error.message : "评估用例创建失败");
  }
}

async function syncEvaluationData() {
  if (isRunning.value) return;
  isRunning.value = true;
  try {
    const remote = await evaluationApi.list(workspaceId.value);
    evaluationCases.splice(
      0,
      evaluationCases.length,
      ...remote
        .filter(
          (item) =>
            projectId.value <= 0 ||
            item.projectId == null ||
            Number(item.projectId) === projectId.value,
        )
        .map((item) => ({
          id: String(item.id),
          projectId:
            item.projectId == null ? undefined : Number(item.projectId),
          query: String(item.query || ""),
          expectedAnswer: String(item.expectedAnswer || ""),
          recall: item.recall == null ? "—" : `${String(item.recall)}%`,
          citation: item.citation == null ? "—" : `${String(item.citation)}%`,
          json: item.jsonScore == null ? "—" : `${String(item.jsonScore)}%`,
          status: String(item.status || "review").toLowerCase(),
        })),
    );
    const latest = remote
      .map((item) => String(item.updatedAt || ""))
      .filter(Boolean)
      .sort()
      .at(-1);
    statistics.value = await (projectId.value > 0
      ? statisticsApi.project(workspaceId.value, projectId.value)
      : statisticsApi.workspace(workspaceId.value));
    lastRunLabel.value = latest
      ? `最近同步：${formatDateTime(latest, "—")}`
      : "评估数据已同步";
    notify("已有评估结果已同步");
  } catch (error) {
    notify(error instanceof Error ? error.message : "评估结果同步失败");
  } finally {
    isRunning.value = false;
  }
}

function openSelectedCaseInPlayground() {
  if (!selectedCase.value) return;
  void router.push({
    ...routeTo("project-playground"),
    query: {
      query: selectedCase.value.query,
      evaluationCaseId: selectedCase.value.id,
    },
  });
}

function openSelectedCaseInAgent() {
  if (!selectedCase.value) return;
  void router.push({
    ...routeTo("project-agent-chat"),
    query: {
      prompt: selectedCase.value.query,
      evaluationCaseId: selectedCase.value.id,
    },
  });
}

async function updateSelectedCaseStatus(
  status: "passed" | "review" | "failed",
) {
  const item = selectedCase.value;
  if (!item || isUpdatingCase.value || item.status === status) return;
  isUpdatingCase.value = true;
  try {
    const updated = await evaluationApi.update(workspaceId.value, item.id, {
      status: status.toUpperCase(),
    });
    item.status = String(updated.status || status).toLowerCase();
    notify(
      status === "passed"
        ? "用例已标记通过"
        : status === "failed"
          ? "用例已标记未通过"
          : "用例已设为待复核",
    );
  } catch (error) {
    notify(error instanceof Error ? error.message : "用例状态更新失败");
  } finally {
    isUpdatingCase.value = false;
  }
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / QUALITY"
    title="评估"
    subtitle="维护回归问题集，可分别检查知识库召回或 Agent（含联网搜索）回答"
  >
    <template #action>
      <button
        class="button button-primary"
        type="button"
        @click="createEvaluation"
      >
        <Plus :size="17" />新建评估
      </button>
    </template>
  </PageHeader>

  <ProjectWorkflow />

  <div class="evaluation-overview">
    <div class="evaluation-overview-copy">
      <div class="overview-status">
        <i />{{ evaluationCases.length ? "评估集已同步" : "暂无评估用例" }}
      </div>
      <strong>{{
        evaluationCases.length ? "当前评估数据已加载" : "等待后端评估数据"
      }}</strong>
      <p>
        {{
          evaluationCases.length
            ? "选择用例可单测知识库召回，也可进入 Agent 检查联网搜索与无依据时的回答边界。"
            : "添加真实问题建立回归集，记录它应命中知识库、联网查找，还是明确答复缺少依据。"
        }}
      </p>
    </div>
    <div class="overview-run">
      <span>{{ lastRunLabel }}</span>
      <button class="text-button" type="button" :disabled="isRunning" @click="syncEvaluationData">
        <RefreshCw :size="14" :class="{ 'is-spinning': isRunning }" />{{
          isRunning ? "同步中…" : "同步已有结果"
        }}
      </button>
    </div>
  </div>

  <div class="evaluation-metrics">
    <div v-for="metric in metricCards" :key="metric.label" class="metric-card">
      <div class="metric-card-top">
        <span>{{ metric.label }}</span
        ><span class="metric-icon" :class="`metric-icon-${metric.tone}`"
          ><component :is="metric.icon" :size="15"
        /></span>
      </div>
      <strong>{{ metric.value }}</strong>
      <small><ArrowUpRight :size="12" />{{ metric.change }}</small>
    </div>
  </div>

  <div class="evaluation-dashboard-grid">
    <section class="panel trend-panel">
      <div class="panel-heading">
        <div>
          <div class="section-kicker">QUALITY TREND</div>
          <h2>质量趋势</h2>
          <p>按评估用例创建日期展示历史指标变化</p>
        </div>
      </div>
      <div v-if="qualityTrendHasData" class="quality-trend-content">
        <div class="chart-legend">
          <span><i style="background: #14a28f" />召回率</span
          ><span><i style="background: #8175e8" />引用准确率</span
          ><span><i style="background: #e5a13a" />结构化输出</span>
        </div>
        <div class="quality-trend-chart">
          <div class="quality-axis">
            <span>100</span><span>50</span><span>0</span>
          </div>
          <div class="quality-chart-area">
            <div class="chart-grid"><i /><i /><i /></div>
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-label="质量趋势图"
            >
              <polyline
                v-if="qualityRecallLine"
                :points="qualityRecallLine"
                fill="none"
                stroke="#14a28f"
                stroke-width="1.5"
                vector-effect="non-scaling-stroke"
              />
              <polyline
                v-if="qualityCitationLine"
                :points="qualityCitationLine"
                fill="none"
                stroke="#8175e8"
                stroke-width="1.5"
                vector-effect="non-scaling-stroke"
              />
              <polyline
                v-if="qualityJsonLine"
                :points="qualityJsonLine"
                fill="none"
                stroke="#e5a13a"
                stroke-width="1.5"
                vector-effect="non-scaling-stroke"
              />
            </svg>
            <div class="quality-x">
              <span v-for="point in qualityTrendLabels" :key="point.date">{{
                point.date
              }}</span>
            </div>
          </div>
        </div>
        <div class="chart-footer">
          <div>
            <strong>{{ formatMetric(averageMetric("recall")) }}</strong
            ><span>当前召回均值</span>
          </div>
          <div>
            <strong>{{ formatMetric(averageMetric("citation")) }}</strong
            ><span>当前引用均值</span>
          </div>
          <div>
            <strong>{{ evaluationCases.length }}</strong
            ><span>评估用例</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-cases trend-empty">
        <BarChart3 :size="20" /><strong>暂无质量趋势数据</strong
        ><span>创建带有评估指标的用例后，这里会展示真实的历史趋势。</span>
      </div>
    </section>

    <section class="panel quality-panel">
      <div class="panel-heading">
        <div>
          <div class="section-kicker">CURRENT BASELINE</div>
          <h2>质量拆解</h2>
          <p>按维度查看当前基线</p>
        </div>
        <span class="baseline-score">{{ overallScore }}</span>
      </div>
      <div class="quality-list">
        <div v-for="item in qualityRows" :key="item.label" class="quality-item">
          <div>
            <span>{{ item.label }}</span
            ><strong>{{ formatMetric(item.value) }}</strong>
          </div>
          <div class="quality-track">
            <i
              :class="`quality-fill-${item.tone}`"
              :style="{ width: `${item.value ?? 0}%` }"
            />
          </div>
        </div>
      </div>
      <div class="quality-note">
        <CheckCircle2 :size="15" /><span>{{
          evaluationCases.length
            ? "指标由当前评估用例实时计算"
            : "暂无数据可用于计算质量指标"
        }}</span>
      </div>
    </section>
  </div>

  <section class="panel table-panel">
    <div class="panel-heading table-heading">
      <div>
        <div class="section-kicker">EVALUATION SET</div>
        <h2>评估用例</h2>
        <p>{{ evaluationCases.length }} 个用例 · {{ lastRunLabel }}</p>
      </div>
      <button
        class="button button-secondary button-sm"
        type="button"
        :disabled="isRunning"
        @click="syncEvaluationData"
      >
        <RefreshCw :size="15" />{{ isRunning ? "同步中…" : "同步已有结果" }}
      </button>
    </div>
    <div class="table-toolbar">
      <div class="filter-tabs" role="tablist" aria-label="评估状态筛选">
        <button
          v-for="filter in statusFilters"
          :key="filter.value"
          class="filter-tab"
          :class="{ active: statusFilter === filter.value }"
          type="button"
          role="tab"
          :aria-selected="statusFilter === filter.value"
          @click="statusFilter = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>
      <span class="result-count"
        >显示 {{ filteredCases.length }} / {{ evaluationCases.length }}</span
      >
    </div>
    <div class="data-table evaluation-table">
      <div class="table-row table-header">
        <span>问题</span><span>召回率</span><span>引用准确率</span
        ><span>结构化输出</span><span>状态</span><span />
      </div>
      <button
        v-for="item in filteredCases"
        :key="item.id"
        class="table-row table-row-button"
        :class="{ 'table-row-selected': item.id === selectedCaseId }"
        type="button"
        @click="selectedCaseId = item.id"
      >
        <span class="case-question"
          ><strong>{{ displayQuery(item) }}</strong
          ><small>{{ item.id }}</small></span
        ><span class="score-cell">{{ item.recall }}</span
        ><span class="score-cell">{{ item.citation }}</span
        ><span class="score-cell">{{ item.json }}</span
        ><span class="status-badge" :class="`status-${item.status}`"
          ><i />{{ evaluationStatusLabel(item.status) }}</span
        ><span class="row-arrow"><ArrowRight :size="15" /></span>
      </button>
      <div v-if="!filteredCases.length" class="empty-cases">
        <CircleAlert :size="18" />暂无符合条件的评估用例
      </div>
    </div>
  </section>

  <div v-if="selectedCase" class="selected-case">
    <span class="selected-case-icon"><ClipboardCheck :size="17" /></span>
    <div>
      <small>当前选中用例 · {{ selectedCase.id }}</small
      ><strong>{{ displayQuery(selectedCase) }}</strong>
      <p v-if="selectedCase.expectedAnswer" class="selected-case-expected">
        验收标准：{{ selectedCase.expectedAnswer }}
      </p>
    </div>
    <span
      class="selected-case-status"
      :class="`status-${selectedCase.status}`"
      >{{ evaluationStatusLabel(selectedCase.status) }}</span
    >
    <button
      class="button button-secondary button-sm"
      type="button"
      @click="openSelectedCaseInPlayground"
    >
      <ArrowRight :size="14" />载入 Playground 检索
    </button>
    <button
      class="button button-primary button-sm"
      type="button"
      @click="openSelectedCaseInAgent"
    >
      <MessageCircle :size="14" />带入 Agent 验证
    </button>
    <button
      class="button button-primary button-sm"
      type="button"
      :disabled="isUpdatingCase || selectedCase.status === 'passed'"
      @click="updateSelectedCaseStatus('passed')"
    >
      <CheckCircle2 :size="14" />标记通过
    </button>
    <button
      class="button button-secondary button-sm"
      type="button"
      :disabled="isUpdatingCase || selectedCase.status === 'failed'"
      @click="updateSelectedCaseStatus('failed')"
    >
      <CircleAlert :size="14" />标记未通过
    </button>
    <button
      v-if="selectedCase.status !== 'review'"
      class="text-button"
      type="button"
      :disabled="isUpdatingCase"
      @click="updateSelectedCaseStatus('review')"
    >
      重新复核
    </button>
  </div>

  <Dialog v-model:open="caseDialogOpen">
    <DialogContent class="evaluation-case-dialog">
      <DialogHeader>
        <DialogTitle>新建评估用例</DialogTitle>
        <DialogDescription>
          记录真实问题和验收边界，之后可分别载入知识库检索或 Agent 完整流程验证。
        </DialogDescription>
      </DialogHeader>
      <div class="evaluation-case-form">
        <label>
          测试问题
          <textarea
            v-model="caseForm.query"
            rows="3"
            placeholder="例如：整理公司差旅报销的住宿标准"
          />
        </label>
        <label>
          期望答案或验收标准（可选）
          <textarea
            v-model="caseForm.expectedAnswer"
            rows="4"
            placeholder="如：应命中项目资料；应联网查找最新来源；没有可信来源时应明确说无法确认。"
          />
        </label>
      </div>
      <DialogFooter>
        <button
          class="button button-secondary"
          type="button"
          @click="caseDialogOpen = false"
        >
          取消
        </button>
        <button
          class="button button-primary"
          type="button"
          :disabled="!caseForm.query.trim()"
          @click="saveEvaluationCase"
        >
          <Plus :size="15" />保存用例
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.evaluation-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  margin: 0.125rem 0 1rem;
  padding: 1rem 1.25rem;
  border: 0.0625rem solid #dcecea;
  border-radius: 0.75rem;
  background: linear-gradient(105deg, #effbf8 0%, #f8fbfb 72%);
}
.evaluation-overview-copy {
  min-width: 0;
}
.overview-status {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
  color: #168a7d;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.overview-status i {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 50%;
  background: #18b49f;
  box-shadow: 0 0 0 0.25rem rgb(20 184 166 / 12%);
}
.evaluation-overview-copy > strong {
  display: block;
  margin-top: 0.4375rem;
  color: #18302f;
  font-size: 0.875rem;
}
.evaluation-overview-copy > p {
  margin: 0.3125rem 0 0;
  color: #64757b;
  font-size: 0.8125rem;
}
.overview-run {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  flex: 0 0 auto;
  color: #64757b;
  font-size: 0.75rem;
}
.overview-run .text-button {
  font-size: 0.8125rem;
}
.is-spinning {
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.evaluation-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.8125rem;
  margin-bottom: 1.125rem;
}
.metric-card {
  min-width: 0;
  padding: 1rem 1.125rem 0.9375rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: 0 0.4375rem 1.4375rem rgb(21 53 52 / 3.5%);
}
.metric-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.metric-card-top > span:first-child {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.metric-icon {
  display: inline-grid;
  width: 1.75rem;
  height: 1.75rem;
  place-items: center;
  border-radius: 0.5625rem;
}
.metric-icon-teal {
  color: #078477;
  background: #e2f8f4;
}
.metric-icon-blue {
  color: #4677bd;
  background: #eaf2ff;
}
.metric-icon-violet {
  color: #7668d4;
  background: #efedff;
}
.metric-icon-amber {
  color: #b97818;
  background: #fff4df;
}
.metric-card strong {
  display: block;
  margin-top: 0.75rem;
  color: var(--workspace-text);
  font-size: 1.5rem;
  font-weight: 680;
  letter-spacing: -0.055em;
  line-height: 1;
}
.metric-card small {
  display: flex;
  align-items: center;
  gap: 0.1875rem;
  margin-top: 0.625rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.metric-card small svg {
  color: #14a28f;
}
.evaluation-dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(17rem, 0.85fr);
  gap: 1.125rem;
  margin-bottom: 1.125rem;
}
.trend-panel,
.quality-panel {
  min-width: 0;
  overflow: hidden;
}
.panel-heading {
  min-height: 5.25rem;
  padding: 1.125rem 1.25rem 0.875rem;
}
.panel-heading h2 {
  margin: 0.25rem 0 0;
  color: var(--workspace-text);
  font-size: 0.875rem;
  letter-spacing: -0.025em;
}
.panel-heading p {
  margin: 0.3125rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.section-kicker {
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.14em;
}
.chart-legend {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  padding-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  white-space: nowrap;
}
.chart-legend i {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 50%;
}
.trend-panel :deep(.trend-chart) {
  height: 13rem;
  padding: 0 0.75rem;
}
.chart-footer {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin: 0 1.25rem 1.125rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.chart-footer div {
  display: grid;
  gap: 0.25rem;
  padding: 0.75rem 0.75rem 0 0;
  border-right: 0.0625rem solid var(--workspace-divider);
}
.chart-footer div + div {
  padding-left: 0.875rem;
}
.chart-footer div:last-child {
  border-right: 0;
}
.chart-footer strong {
  color: var(--workspace-text);
  font-size: 0.875rem;
  letter-spacing: -0.04em;
}
.chart-footer span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.trend-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 13rem;
  flex-direction: column;
  gap: 0.5rem;
  border: 1px dashed var(--workspace-border);
  border-radius: 0.625rem;
  margin: 0 1.25rem 1.125rem;
  text-align: center;
}
.trend-empty svg {
  color: var(--workspace-muted);
}
.trend-empty strong {
  color: var(--workspace-text);
}
.trend-empty span {
  max-width: 24rem;
  font-size: 0.75rem;
  line-height: 1.6;
}
.quality-panel .panel-heading {
  display: flex;
  justify-content: space-between;
}
.baseline-score {
  color: var(--teal-dark);
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: -0.04em;
}
.quality-list {
  display: grid;
  gap: 1.1875rem;
  padding: 0.875rem 1.25rem 1.25rem;
}
.quality-item > div:first-child {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.quality-item strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.quality-track {
  height: 0.4375rem;
  margin-top: 0.5rem;
  overflow: hidden;
  border-radius: 99rem;
  background: var(--surface-soft);
}
.quality-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  transition: width 350ms ease;
}
.quality-fill-teal {
  background: #14b8a6;
}
.quality-fill-violet {
  background: #8175e8;
}
.quality-fill-amber {
  background: #e5a13a;
}
.quality-note {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
  margin: 0 1.25rem 1.25rem;
  padding: 0.625rem 0.6875rem;
  border-radius: 0.5rem;
  background: #f0faf8;
  color: #188a7e;
  font-size: 0.75rem;
}
.table-panel {
  overflow: hidden;
}
.table-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0 1.25rem 0.75rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.filter-tabs {
  display: flex;
  align-items: center;
  gap: 0.1875rem;
  overflow-x: auto;
}
.filter-tab {
  padding: 0.375rem 0.5625rem;
  border: 0;
  border-radius: 0.375rem;
  background: transparent;
  color: var(--workspace-muted);
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
  white-space: nowrap;
}
.filter-tab:hover {
  background: var(--surface-soft);
  color: var(--workspace-text);
}
.filter-tab.active {
  background: #e5f7f4;
  color: var(--teal-dark);
  font-weight: 700;
}
.result-count {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.evaluation-table .table-row {
  grid-template-columns: minmax(0, 2.1fr) 0.8fr 0.95fr 0.95fr 0.85fr 1.25rem;
}
.table-row-button {
  width: 100%;
  border: 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.table-row-button:last-child {
  border-bottom: 0;
}
.table-row-button:hover {
  background: #f7fbfb;
}
.case-question {
  min-width: 0;
}
.case-question strong,
.case-question small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.case-question strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
  font-weight: 600;
}
.case-question small {
  margin-top: 0.3125rem;
  color: var(--workspace-subtle);
  font:
    700 0.75rem ui-monospace,
    monospace;
  letter-spacing: 0.04em;
}
.score-cell {
  color: var(--workspace-text);
  font-size: 0.8125rem;
  font-weight: 600;
}
.status-badge,
.selected-case-status {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  width: fit-content;
  padding: 0.25rem 0.4375rem;
  border-radius: 0.3125rem;
  font-size: 0.75rem;
  font-weight: 650;
  white-space: nowrap;
}
.status-badge i {
  width: 0.3125rem;
  height: 0.3125rem;
  border-radius: 50%;
}
.status-passed {
  color: #158376;
  background: #e5f8f4;
}
.status-passed i {
  background: #18ab98;
}
.status-review {
  color: #a4701d;
  background: #fff5df;
}
.status-review i {
  background: #d7962a;
}
.status-failed {
  color: #b75a5a;
  background: #fff0ef;
}
.status-failed i {
  background: #dc7171;
}
.row-arrow {
  display: inline-grid;
  width: 1.75rem;
  height: 1.75rem;
  place-items: center;
  border-radius: 0.5rem;
  color: var(--workspace-muted);
}
.table-row-button:hover .row-arrow {
  background: #e9f7f5;
  color: var(--teal-dark);
}
.empty-cases {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 5rem;
  color: var(--workspace-muted);
  font-size: 0.8125rem;
}
.selected-case {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6875rem;
  margin-top: 0.875rem;
  padding: 0.75rem 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface);
}
.selected-case-icon {
  display: grid;
  width: 1.875rem;
  height: 1.875rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5625rem;
  background: #e5f8f4;
  color: var(--teal-dark);
}
.selected-case div {
  min-width: 0;
  flex: 1;
}
.selected-case small,
.selected-case strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.selected-case small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.selected-case strong {
  margin-top: 0.1875rem;
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.selected-case-expected {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.45;
  white-space: pre-line;
}
.selected-case-status {
  margin-left: auto;
}
@media (max-width: 62rem) {
  .evaluation-dashboard-grid {
    grid-template-columns: 1fr;
  }
  .quality-panel {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .quality-panel .panel-heading {
    grid-column: 1/-1;
  }
  .quality-list {
    padding-top: 0;
  }
  .quality-note {
    align-self: end;
    margin-top: 0;
  }
}
@media (max-width: 47.5rem) {
  .evaluation-overview {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.75rem;
  }
  .overview-run {
    width: 100%;
    justify-content: space-between;
  }
  .evaluation-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .metric-card {
    padding-inline: 0.875rem;
  }
  .panel-heading {
    padding-inline: 1rem;
  }
  .chart-legend {
    gap: 0.5rem;
  }
  .table-toolbar {
    align-items: flex-start;
    flex-direction: column;
    padding-inline: 1rem;
  }
  .result-count {
    align-self: flex-end;
  }
  .evaluation-table {
    overflow-x: auto;
  }
  .evaluation-table .table-row {
    min-width: 47rem;
  }
  .quality-panel {
    display: block;
  }
  .quality-panel .panel-heading {
    display: flex;
  }
  .quality-list {
    padding: 0.25rem 1rem 1.125rem;
  }
  .quality-note {
    margin: 0 1rem 1rem;
  }
  .selected-case {
    align-items: flex-start;
  }
  .selected-case-status {
    margin-top: 0.1rem;
  }
}
@media (max-width: 30rem) {
  .evaluation-metrics {
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }
  .metric-card strong {
    font-size: 1.25rem;
  }
  .metric-card-top > span:first-child {
    font-size: 0.75rem;
  }
  .chart-footer {
    margin-inline: 1rem;
  }
  .chart-footer div + div {
    padding-left: 0.5rem;
  }
}
.evaluation-dashboard-grid {
  align-items: stretch;
}
.trend-panel {
  display: flex;
  flex-direction: column;
}
.trend-panel .trend-empty {
  flex: 1;
  min-height: 9.5rem;
}
.evaluation-overview {
  border-color: color-mix(in oklab, var(--teal) 22%, var(--workspace-border));
  background: linear-gradient(
    105deg,
    color-mix(in oklab, var(--teal) 11%, var(--surface)),
    var(--surface)
  );
}
.evaluation-overview-copy > strong {
  color: var(--workspace-text);
}
.evaluation-overview-copy > p,
.overview-run {
  color: var(--workspace-muted);
}
.quality-note {
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
  color: var(--teal-dark);
}
.filter-tab.active,
.selected-case-icon {
  background: color-mix(in oklab, var(--teal) 13%, var(--surface));
  color: var(--teal-dark);
}
.table-row-button:hover {
  background: color-mix(in oklab, var(--teal) 5%, var(--surface));
}
.status-passed {
  color: var(--teal-dark);
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
}
.status-review {
  color: #b98229;
  background: color-mix(in oklab, #d7962a 15%, var(--surface));
}
.status-failed {
  color: #d27878;
  background: color-mix(in oklab, #dc7171 14%, var(--surface));
}
.trend-panel,
.quality-panel {
  min-height: 24rem;
}
.evaluation-case-dialog {
  max-width: 40rem !important;
}
.evaluation-case-form {
  display: grid;
  gap: 0.875rem;
}
.evaluation-case-form label {
  display: grid;
  gap: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.evaluation-case-form textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  outline: 0;
  padding: 0.625rem 0.75rem;
  background: var(--surface-soft);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.8125rem;
}
.evaluation-case-form textarea:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 16%, transparent);
}
.quality-trend-content {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}
.quality-trend-content > .chart-legend {
  padding: 0.125rem 1.25rem 0.5rem;
}
.quality-trend-chart {
  display: flex;
  height: 13rem;
  padding: 0 1.25rem;
}
.quality-axis {
  display: flex;
  width: 1.75rem;
  flex-direction: column;
  justify-content: space-between;
  padding-bottom: 1.5rem;
  color: var(--workspace-chart-axis);
  font-size: 0.75rem;
}
.quality-chart-area {
  position: relative;
  min-width: 0;
  flex: 1;
}
.quality-chart-area .chart-grid {
  inset: 0 0 1.5rem;
}
.quality-chart-area svg {
  position: absolute;
  inset: 0 0 1.5rem;
  width: 100%;
  height: calc(100% - 1.5rem);
  overflow: visible;
}
.quality-x {
  position: absolute;
  bottom: 0;
  left: 0;
  display: flex;
  width: 100%;
  justify-content: space-between;
  color: var(--workspace-chart-axis);
  font-size: 0.75rem;
}
.quality-trend-content .chart-footer {
  margin-top: auto;
}
</style>
