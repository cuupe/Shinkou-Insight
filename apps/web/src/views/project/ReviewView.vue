<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from "vue-router";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  FileText,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  ChevronDown,
  History,
  Settings2,
  X,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldSet,
  FieldLegend,
} from "@/components/ui/field";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import ReviewReportBody from "@/components/project/ReviewReportBody.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { reviewApi } from "@/api/review";
import { reportsApi } from "@/api/reports";
import { getApiErrorMessage } from "@/api/core";
import type {
  ProjectReviewPolicy,
  ProjectReviewRun,
  ProjectReviewCheck,
  Report,
} from "@/api/types";
import { formatDateTime } from "@/lib/utils";

const { workspaceId, projectId, selectedProject, notify, router, routeTo } =
  useWorkspace();
const route = useRoute();
const reports = ref<Report[]>([]);
const history = ref<ProjectReviewRun[]>([]);
const policy = ref<ProjectReviewPolicy | null>(null);
const reportId = ref("");
const reviewId = ref("");
const loading = ref(false);
const checking = ref(false);
const saving = ref(false);
const submitting = ref(false);
const loadError = ref("");
const actionError = ref("");
const decisionError = ref("");
const comment = ref("");
const confirmations = ref<string[]>([]);
const showCurrentBody = ref(false);
const policyDraft = reactive({
  requireCitations: true,
  verifyNumbers: true,
  escalateConflicts: true,
  labelExternal: true,
});
let scope = 0;
let loadVersion = 0;
const ruleDefinitions = [
  {
    key: "requireCitations" as const,
    label: "引用与事实对应",
    detail: "无引用依据时阻断；存在引用时需人工核对原文与结论。",
  },
  {
    key: "verifyNumbers" as const,
    label: "数字与日期核验",
    detail: "定位正文数字片段，由审查人确认单位、条件和计算。",
  },
  {
    key: "escalateConflicts" as const,
    label: "冲突与限制核验",
    detail: "要求确认冲突来源、未证实的假设及资料缺口。",
  },
  {
    key: "labelExternal" as const,
    label: "外部来源标注",
    detail: "发现网页链接时，要求核对来源机构和时间范围。",
  },
];
const selectedReport = computed(() =>
  reports.value.find((report) => String(report.id) === reportId.value),
);
const reportHistory = computed(() =>
  history.value.filter((run) => String(run.reportId || "") === reportId.value),
);
const legacyHistory = computed(() =>
  history.value.filter((run) => !run.reportId),
);
const latest = computed(() => reportHistory.value[0]);
const selectedRun = computed(
  () =>
    reportHistory.value.find((run) => String(run.id) === reviewId.value) ||
    latest.value,
);
const requiredChecks = computed(() =>
  (selectedRun.value?.checks || []).filter(
    (check) => check.status === "REVIEW",
  ),
);
const dirty = computed(
  () =>
    !!policy.value &&
    ruleDefinitions.some(
      (rule) => policyDraft[rule.key] !== policy.value![rule.key],
    ),
);
const busy = computed(
  () => loading.value || checking.value || saving.value || submitting.value,
);
const canDecide = computed(
  () =>
    !!policy.value?.canManage &&
    !!selectedRun.value &&
    selectedRun.value.id === latest.value?.id &&
    !selectedRun.value.stale &&
    !selectedRun.value.decidedAt &&
    !dirty.value &&
    !busy.value,
);
const canApprove = computed(
  () =>
    canDecide.value &&
    selectedRun.value!.blockedCount === 0 &&
    !!comment.value.trim() &&
    comment.value.length <= 4000 &&
    requiredChecks.value.every((check) =>
      confirmations.value.includes(check.key),
    ),
);
const isHistorical = computed(
  () => !!selectedRun.value && selectedRun.value.id !== latest.value?.id,
);
const labels: Record<string, string> = {
  BLOCKED: "存在阻断",
  REVIEW: "待人工签署",
  APPROVED: "签署通过",
  CHANGES_REQUESTED: "退回修改",
  PASSED: "结构检查通过",
  SKIPPED: "按需跳过",
};
const routeLabels: Record<string, string> = {
  "project-reports": "报告",
  "project-assets": "知识库",
  "project-evaluation": "检索评估",
  "project-runs": "分析记录",
  "project-planning": "项目规划",
  "project-action-items": "行动项",
};
const checkLabels: Record<string, string> = {
  BLOCKED: "需先修正",
  REVIEW: "人工核验",
  PASSED: "检查通过",
  SKIPPED: "本次跳过",
};
const viewingSnapshot = computed(
  () =>
    !!selectedRun.value?.reportSnapshot &&
    "content" in selectedRun.value.reportSnapshot &&
    !showCurrentBody.value,
);
const reportBody = computed(() =>
  viewingSnapshot.value
    ? String(selectedRun.value?.reportSnapshot?.content || "")
    : String(
        selectedReport.value?.content ||
          selectedReport.value?.markdownContent ||
          "",
      ),
);
const confirmedCount = computed(
  () =>
    requiredChecks.value.filter((check) =>
      confirmations.value.includes(check.key),
    ).length,
);

function resetDecision() {
  showCurrentBody.value = false;
  confirmations.value = [...(selectedRun.value?.confirmations || [])];
  comment.value = selectedRun.value?.decisionComment || "";
  actionError.value = "";
  decisionError.value = "";
}
watch(() => selectedRun.value?.id, resetDecision);
watch(reportId, () => {
  reviewId.value = "";
  resetDecision();
});
async function refresh() {
  const currentScope = scope;
  const version = ++loadVersion;
  const workspace = workspaceId.value;
  const project = projectId.value;
  loading.value = true;
  loadError.value = "";
  try {
    const [rules, records, availableReports] = await Promise.all([
      reviewApi.policy(workspace, project),
      reviewApi.history(workspace, project),
      reportsApi.list(workspace, project),
    ]);
    if (currentScope !== scope || version !== loadVersion) return;
    policy.value = rules;
    Object.assign(policyDraft, {
      requireCitations: rules.requireCitations,
      verifyNumbers: rules.verifyNumbers,
      escalateConflicts: rules.escalateConflicts,
      labelExternal: rules.labelExternal,
    });
    reports.value = availableReports;
    history.value = records;
    if (
      !availableReports.some((report) => String(report.id) === reportId.value)
    )
      reportId.value = String(availableReports[0]?.id || "");
    if (!reportHistory.value.some((run) => String(run.id) === reviewId.value))
      reviewId.value = String(reportHistory.value.find(run=>String(run.id)===String(route.query.reviewRunId||""))?.id || reportHistory.value[0]?.id || "");
    resetDecision();
  } catch (error) {
    if (currentScope === scope && version === loadVersion)
      loadError.value = getApiErrorMessage(error, "审查数据读取失败，请重试");
  } finally {
    if (currentScope === scope && version === loadVersion)
      loading.value = false;
  }
}
async function savePolicy() {
  if (busy.value || !dirty.value || !policy.value?.canManage) return;
  const currentScope = scope;
  saving.value = true;
  policyError.value = "";
  try {
    const saved = await reviewApi.savePolicy(
      workspaceId.value,
      projectId.value,
      { ...policyDraft },
    );
    if (currentScope !== scope) return;
    policy.value = saved;
    await refresh();
    if (currentScope === scope) {
      rulesOpen.value = false;
      notify("检查规则已保存，请按新规则重新检查当前报告");
    }
  } catch (error) {
    if (currentScope === scope)
      policyError.value = getApiErrorMessage(error, "保存规则失败");
  } finally {
    if (currentScope === scope) saving.value = false;
  }
}
async function runReview() {
  if (
    !selectedReport.value ||
    busy.value ||
    dirty.value ||
    !policy.value?.canManage
  )
    return;
  if (!(await allowDiscard("decision"))) return;
  resetDecision();
  const currentScope = scope;
  const id = reportId.value;
  let newReviewId = "";
  checking.value = true;
  actionError.value = "";
  try {
    const run = await reviewApi.run(workspaceId.value, projectId.value, id);
    if (currentScope !== scope) return;
    await refresh();
    if (currentScope === scope && reportId.value === id) {
      reviewId.value = String(run.id);
      newReviewId = String(run.id);
      resetDecision();
      activeTab.value = "checks";
      checkFilter.value = "attention";
      notify("检查完成，请处理明确缺口并核验人工确认项");
    }
  } catch (error) {
    if (currentScope === scope)
      actionError.value = getApiErrorMessage(
        error,
        "运行检查失败，未生成审查结果",
      );
  } finally {
    if (currentScope === scope) checking.value = false;
  }
  if (currentScope === scope && reportId.value === id && newReviewId) {
    await router.replace({ ...routeTo("project-review"), query: { reportId: id, reviewRunId: newReviewId } });
  }
}
async function decide(decision: "APPROVED" | "CHANGES_REQUESTED") {
  const run = selectedRun.value;
  if (
    !run ||
    !canDecide.value ||
    !comment.value.trim() ||
    comment.value.length > 4000 ||
    (decision === "APPROVED" && !canApprove.value)
  )
    return;
  const currentScope = scope;
  const pendingComment = comment.value;
  const pendingConfirmations = [...confirmations.value];
  submitting.value = true;
  actionError.value = "";
  decisionError.value = "";
  try {
    const saved = await reviewApi.decide(
      workspaceId.value,
      projectId.value,
      run.id,
      {
        decision,
        comment: comment.value.trim(),
        confirmations: [...confirmations.value],
      },
    );
    if (currentScope !== scope) return;
    const index = history.value.findIndex((item) => item.id === saved.id);
    if (index >= 0) history.value.splice(index, 1, saved);
    resetDecision();
    notify(
      decision === "APPROVED"
        ? "签署已保存，可前往报告页发布"
        : "退回意见已保存，请修改报告后重新检查",
    );
  } catch (error) {
    if (currentScope === scope) {
      const message = getApiErrorMessage(error, "签署未保存，请刷新后重试");
      await refresh();
      if (currentScope === scope) {
        decisionError.value = message;
        if (selectedRun.value?.id === run.id && !selectedRun.value.decidedAt) {
          comment.value = pendingComment;
          confirmations.value = pendingConfirmations;
        }
      }
    }
  } finally {
    if (currentScope === scope) submitting.value = false;
  }
}
function go(name: string) {
  void router.push({
    ...routeTo(name),
    ...(["project-reports","project-action-items"].includes(name) && reportId.value
      ? { query: { reportId: reportId.value } }
      : {}),
  });
}
function createAction() {
  if (!policy.value?.canManage || !selectedRun.value || !selectedReport.value) return;
  const run = selectedRun.value;
  const issues = (run.checks || [])
    .filter((check) => check.status === "BLOCKED")
    .map((check) => `${check.title}：${check.detail}`);
  const description = [
    `来源报告：${selectedReport.value.title} · 版本 ${run.reportVersion || "未编号"}`,
    `审查记录：#${run.id}`,
    ...issues,
    run.decisionComment && `审查意见：${run.decisionComment}`,
  ]
    .filter(Boolean)
    .join("\n\n")
    .slice(0, 1000);
  void router.push({
    ...routeTo("project-action-items"),
    query: {
      actionTitle: `跟进报告审查：${selectedReport.value.title}`.slice(0, 180),
      actionDescription: description,
      sourceReportId: String(selectedReport.value.id),
      sourceReviewRunId: String(run.id),
    },
  });
}

const activeTab = ref("checks");
const checkFilter = ref("attention");
const rulesOpen = ref(false);
const policyError = ref("");
const discardOpen = ref(false);
const discardKind = ref<"decision" | "rules" | "all">("all");
const workbenchElement = ref<HTMLElement | null>(null);
const signoffElement = ref<HTMLElement | null>(null);
const checksElement = ref<HTMLElement | null>(null);
let discardResolver: ((allow: boolean) => void) | null = null;
const decisionDirty = computed(() => !!policy.value?.canManage && !!selectedRun.value && !selectedRun.value.decidedAt && (
  comment.value !== (selectedRun.value.decisionComment || "") ||
  JSON.stringify([...confirmations.value].sort()) !== JSON.stringify([...(selectedRun.value.confirmations || [])].sort())
));
const passedChecks = computed(() => (selectedRun.value?.checks || []).filter(check => check.status === "PASSED"));
const skippedChecks = computed(() => (selectedRun.value?.checks || []).filter(check => check.status === "SKIPPED"));
const remainingCount = computed(() => requiredChecks.value.length - confirmedCount.value);
const displayedChecks = computed(() => {
  const order = { BLOCKED: 0, REVIEW: 1, PASSED: 2, SKIPPED: 3 };
  return [...(selectedRun.value?.checks || [])].filter(check =>
    checkFilter.value === "all" || (checkFilter.value === "attention"
      ? check.status === "BLOCKED" || check.status === "REVIEW"
      : checkFilter.value === "unconfirmed"
        ? check.status === "REVIEW" && !confirmations.value.includes(check.key)
        : check.status === checkFilter.value)
  ).sort((left, right) => order[left.status] - order[right.status]);
});
const enabledRules = computed(() => ruleDefinitions.filter(rule => policy.value?.[rule.key]).length);
const statusTitle = computed(() => isHistorical.value ? "正在查看历史检查"
  : selectedRun.value?.stale ? "报告或依据已变化，请重新检查"
    : selectedRun.value?.status === "APPROVED" ? "审查已通过，可以发布报告"
      : selectedRun.value?.status === "CHANGES_REQUESTED" ? "报告已退回，修正后重新检查"
        : selectedRun.value?.blockedCount ? "先处理阻断问题，再完成核验"
          : "逐项核验依据，完成后签署");
const signoffHint = computed(() => !policy.value?.canManage ? "当前仅可查看，运行检查与签署由项目创建者或管理员完成。"
  : isHistorical.value ? "历史记录保留当时的正文和意见。切换到最新检查后继续处理。"
    : selectedRun.value?.stale ? "本次检查已失效，请重新检查当前报告后签署。"
      : selectedRun.value?.decidedAt ? "此签署已保存。需要调整结论时，请重新运行检查。"
        : selectedRun.value?.blockedCount ? "仍有阻断问题，不能签署通过。可以填写意见并退回修改。"
          : remainingCount.value ? "请在检查卡片中逐项核验并确认，再填写审查意见。"
            : !comment.value.trim() ? "核验已完成，请填写审查意见后签署。" : "核验和意见已齐备，可以签署通过。");
const discardDescription = computed(() => discardKind.value === "rules"
  ? "检查规则的修改尚未保存，放弃后恢复已保存的规则。"
  : discardKind.value === "decision" ? "核验勾选和审查意见尚未签署，放弃后恢复本条记录。"
    : "当前核验意见或检查规则尚未保存。继续处理可以保留输入。");

function resetPolicyDraft() {
  if (!policy.value) return;
  ruleDefinitions.forEach(rule => { policyDraft[rule.key] = policy.value![rule.key]; });
  policyError.value = "";
}
function allowDiscard(kind: "decision" | "rules" | "all" = "all") {
  const changed = kind === "decision" ? decisionDirty.value : kind === "rules" ? dirty.value : decisionDirty.value || dirty.value;
  if (!changed) return Promise.resolve(true);
  if (discardResolver) return Promise.resolve(false);
  discardKind.value = kind;
  discardOpen.value = true;
  return new Promise<boolean>(resolve => { discardResolver = resolve; });
}
function decideDiscard(allow: boolean) {
  discardOpen.value = false;
  const resolve = discardResolver;
  discardResolver = null;
  resolve?.(allow);
}
async function refreshPage() {
  if (busy.value || !(await allowDiscard())) return;
  resetPolicyDraft();
  await refresh();
}
async function openRules() {
  if (busy.value || !(await allowDiscard("decision"))) return;
  resetDecision();
  resetPolicyDraft();
  rulesOpen.value = true;
}
async function closeRules() {
  if (saving.value || !(await allowDiscard("rules"))) return;
  resetPolicyDraft();
  rulesOpen.value = false;
}
async function selectReport(event: Event) {
  const element = event.target as HTMLSelectElement;
  const nextId = element.value;
  element.value = reportId.value;
  if (busy.value || nextId === reportId.value || !(await allowDiscard())) return;
  resetPolicyDraft();
  reportId.value = nextId;
  activeTab.value = "checks";
  await nextTick();
  void router.replace({ ...routeTo("project-review"), query: { reportId: nextId } });
}
async function selectRun(run: ProjectReviewRun) {
  if (busy.value || run.id === selectedRun.value?.id || !(await allowDiscard("decision"))) return;
  reviewId.value = String(run.id);
  activeTab.value = "checks";
  await nextTick();
  void router.replace({ ...routeTo("project-review"), query: { reportId: reportId.value, reviewRunId: String(run.id) } });
}
function setConfirmation(key: string, checked: boolean | "indeterminate") {
  if (!canDecide.value) return;
  confirmations.value = confirmations.value.filter(value => value !== key);
  if (checked === true) confirmations.value.push(key);
}
function openCheckSource(check: ProjectReviewCheck) {
  if (check.route === "project-reports") activeTab.value = "body";
  else go(check.route);
}
async function jumpToSignoff() {
  activeTab.value = "checks";
  await nextTick();
  const panel = activePanel();
  const signoff = signoffElement.value;
  if (panel && signoff) {
    panel.scrollTo({ top: panel.scrollTop + signoff.getBoundingClientRect().top - panel.getBoundingClientRect().top, behavior: "smooth" });
    signoff.scrollTop = 0;
  }
  if (canDecide.value) document.getElementById("review-comment")?.focus({ preventScroll: true });
}
async function showUnconfirmed() {
  activeTab.value = "checks";
  checkFilter.value = "unconfirmed";
  await nextTick();
  activePanel()?.scrollTo({ top: 0, behavior: "smooth" });
  workbenchElement.value?.querySelector<HTMLElement>(".review-check-list")?.scrollTo({ top: 0 });
}
function activePanel() { return workbenchElement.value?.querySelector<HTMLElement>('[role="tabpanel"][data-state="active"]'); }
function returnToChecks() { activeTab.value = "checks"; }
watch(() => selectedRun.value?.id, () => { checkFilter.value = "attention"; });
watch(activeTab, async () => { await nextTick(); activePanel()?.scrollTo({ top: 0 }); });
watch(() => route.query.reviewRunId, value => {
  if (typeof value === "string" && reportHistory.value.some(run => String(run.id) === value)) reviewId.value = value;
});
onBeforeRouteLeave(() => busy.value ? false : allowDiscard());
onBeforeRouteUpdate((to, from) => {
  const changingRecord = to.params.workspaceId !== from.params.workspaceId || to.params.projectId !== from.params.projectId ||
    to.query.reportId !== from.query.reportId || to.query.reviewRunId !== from.query.reviewRunId;
  return changingRecord ? busy.value ? false : allowDiscard() : true;
});

watch(
  [workspaceId, projectId],
  () => {
    scope++;
    reports.value = [];
    history.value = [];
    policy.value = null;
    reportId.value =
      typeof route.query.reportId === "string" ? route.query.reportId : "";
    reviewId.value = "";
    checking.value = false;
    saving.value = false;
    submitting.value = false;
    comment.value = "";
    confirmations.value = [];
    actionError.value = "";
    decisionError.value = "";
    rulesOpen.value = false;
    policyError.value = "";
    activeTab.value = "checks";
    decideDiscard(false);
    void refresh();
  },
  { immediate: true },
);
watch(
  () => route.query.reportId,
  (id) => {
    if (typeof id === "string") reportId.value = id;
  },
);
onBeforeUnmount(() => {
  scope++;
  decideDiscard(false);
});
</script>

<template>
  <section ref="workbenchElement" class="review-workbench" aria-label="报告审查工作台">
    <PageHeader eyebrow="交付" title="审查中心" subtitle="核对依据，记录结论，完成交付">
      <template #action>
        <Button variant="outline" aria-label="刷新审查数据" :disabled="busy" @click="refreshPage"><RefreshCw data-icon="inline-start" />刷新</Button>
      </template>
    </PageHeader>

    <Alert v-if="loadError" variant="destructive">
      <CircleAlert /><AlertTitle>审查数据读取失败</AlertTitle>
      <AlertDescription>{{ loadError }}<Button variant="outline" size="sm" @click="refreshPage">重新加载</Button></AlertDescription>
    </Alert>
    <div v-else-if="loading && !policy" class="review-loading" role="status"><LoaderCircle class="is-spinning" :size="18" />正在读取报告与审查记录…</div>

    <template v-else-if="policy">
      <div class="review-scope">
        <Field class="review-report-field">
          <FieldLabel for="review-report">本次审查报告</FieldLabel>
          <select id="review-report" :value="reportId" :disabled="busy || !reports.length" :title="selectedReport?.title" @change="selectReport">
            <option v-if="!reports.length" value="">暂无可审查报告</option>
            <option v-for="report in reports" :key="String(report.id)" :value="String(report.id)">{{ report.title }} · v{{ report.versionNo || "未编号" }}</option>
          </select>
        </Field>
        <div class="review-scope-actions">
          <Button variant="outline" size="sm" :disabled="busy" @click="openRules"><Settings2 data-icon="inline-start" />检查规则<span class="rules-count">{{ enabledRules }}/4</span></Button>
          <Button v-if="policy.canManage" aria-label="运行当前版本检查" :disabled="busy || dirty || !selectedReport" @click="runReview">
            <LoaderCircle v-if="checking" data-icon="inline-start" class="is-spinning" /><ClipboardCheck v-else data-icon="inline-start" />{{ checking ? "检查中…" : selectedRun ? "重新检查" : "开始检查" }}
          </Button>
        </div>
      </div>
      <p v-if="!policy.canManage" class="review-access-note"><ShieldCheck :size="14" />你可以查看报告、检查明细与签署记录；运行检查和签署由项目创建者或管理员完成。</p>
      <Alert v-if="actionError" variant="destructive"><CircleAlert /><AlertTitle>操作未完成</AlertTitle><AlertDescription>{{ actionError }}</AlertDescription></Alert>

      <Card v-if="!reports.length" class="review-empty">
        <CardHeader><FileText :size="28" /><CardTitle role="heading" aria-level="2">先准备一份可审查的报告</CardTitle><CardDescription>报告保存后，在这里核对依据、处理问题并签署发布。</CardDescription></CardHeader>
        <CardContent><p class="review-note">审查绑定具体报告版本；已有资料或运行数量不会直接作为通过依据。</p></CardContent>
        <CardFooter><Button @click="go('project-runs')">前往智能分析<ArrowRight data-icon="inline-end" /></Button><Button variant="outline" @click="go('project-reports')">查看报告</Button></CardFooter>
      </Card>

      <template v-else-if="selectedReport">
        <div v-if="selectedRun" class="review-status" :class="{ 'has-blockers': selectedRun.blockedCount > 0 && !selectedRun.stale && !isHistorical }">
          <div class="review-status-copy">
            <span class="review-status-icon"><CircleAlert v-if="selectedRun.stale || selectedRun.blockedCount || selectedRun.status === 'CHANGES_REQUESTED'" :size="20" /><ShieldCheck v-else :size="20" /></span>
            <div><div class="review-status-title"><h2>{{ statusTitle }}</h2><Badge v-if="isHistorical" variant="secondary">历史记录</Badge><Badge v-else-if="selectedRun.stale" variant="secondary">已失效</Badge><Badge v-else variant="secondary">{{ labels[selectedRun.status] || selectedRun.status }}</Badge></div>
              <p>报告 v{{ selectedRun.reportVersion || "未编号" }}<span>检查 #{{ selectedRun.id }}</span><time>{{ formatDateTime(selectedRun.createdAt, "时间未记录") }}</time></p>
            </div>
          </div>
          <Button v-if="isHistorical && latest" variant="outline" size="sm" :disabled="busy" @click="selectRun(latest)">返回最新检查<ArrowRight data-icon="inline-end" /></Button>
          <Button v-else variant="outline" size="sm" @click="jumpToSignoff">{{ selectedRun.decidedAt ? "查看签署" : "核验与签署" }}<ArrowRight data-icon="inline-end" /></Button>
        </div>

        <Tabs v-model="activeTab" class="review-tabs">
          <div class="review-tab-bar">
            <TabsList aria-label="审查内容">
              <TabsTrigger value="checks"><ClipboardCheck />检查结果</TabsTrigger>
              <TabsTrigger value="body"><FileText />报告正文</TabsTrigger>
              <TabsTrigger value="history"><History />审查记录<span class="tab-count">{{ reportHistory.length }}</span></TabsTrigger>
            </TabsList>
            <Button variant="link" size="sm" @click="go('project-reports')">打开报告页<ArrowRight data-icon="inline-end" /></Button>
          </div>

          <TabsContent value="checks" class="review-checks-tab">
            <Card v-if="!selectedRun" class="review-empty">
              <CardHeader><ClipboardCheck :size="28" /><CardTitle role="heading" aria-level="2">这份报告尚未审查</CardTitle><CardDescription>检查已保存的正文、引用和交付任务，再由审查人核对事实。</CardDescription></CardHeader>
              <CardContent><p class="review-note">本次检查不会调用模型。运行后将列出阻断问题与人工核验项。</p></CardContent>
              <CardFooter><Button v-if="policy.canManage" :disabled="busy || dirty" aria-label="开始首次检查" @click="runReview">开始检查<ArrowRight data-icon="inline-end" /></Button></CardFooter>
            </Card>
            <div v-else class="review-columns">
              <div ref="checksElement" class="review-main">
                <div class="review-metrics" aria-label="检查结果概况">
                  <div><span>需先修正</span><strong :class="{ 'text-blocked': selectedRun.blockedCount }">{{ selectedRun.blockedCount }}<small>项</small></strong></div>
                  <div><span>人工核验</span><strong>{{ confirmedCount }}<small>/ {{ requiredChecks.length }} 项已确认</small></strong></div>
                  <div><span>结构检查通过</span><strong>{{ passedChecks.length }}<small>项</small></strong></div>
                </div>
                <div class="review-check-toolbar">
                  <div><h2>逐项检查</h2><p>结构检查通过后，仍需核实事实与引用。</p></div>
                  <Field class="review-filter-field"><FieldLabel for="review-check-filter" class="sr-only">筛选检查项</FieldLabel>
                    <select id="review-check-filter" v-model="checkFilter">
                      <option value="attention">待处理与核验</option><option value="all">全部检查（{{ selectedRun.checks?.length || 0 }}）</option>
                      <option value="BLOCKED">需先修正（{{ selectedRun.blockedCount }}）</option><option value="REVIEW">人工核验（{{ requiredChecks.length }}）</option>
                      <option value="unconfirmed">尚未确认（{{ remainingCount }}）</option><option value="PASSED">检查通过（{{ passedChecks.length }}）</option><option value="SKIPPED">本次跳过（{{ skippedChecks.length }}）</option>
                    </select>
                  </Field>
                </div>
                <div class="review-check-list">
                  <article v-for="check in displayedChecks" :key="check.key" class="review-check" :class="{ 'check-blocked': check.status === 'BLOCKED', 'check-confirmed': confirmations.includes(check.key) && check.status === 'REVIEW' }" :data-check="check.key">
                    <div class="review-check-heading"><h3>{{ check.title }}</h3><Badge :variant="check.status === 'BLOCKED' ? 'destructive' : 'secondary'">{{ checkLabels[check.status] }}</Badge></div>
                    <p>{{ check.detail }}</p>
                    <details v-if="check.excerpts?.length" class="review-excerpt-details">
                      <summary>查看相关片段<span>{{ check.excerpts.length }} 条</span><ChevronDown :size="14" /></summary>
                      <ul class="review-excerpts"><li v-for="(excerpt, index) in check.excerpts" :key="index">{{ excerpt }}</li></ul>
                    </details>
                    <div v-if="check.status === 'REVIEW' || check.status === 'BLOCKED'" class="review-check-footer">
                      <Field v-if="check.status === 'REVIEW'" orientation="horizontal" class="review-confirm-field">
                        <Checkbox :id="'confirm-' + check.key" :model-value="confirmations.includes(check.key)" :disabled="!canDecide" @update:model-value="value => setConfirmation(check.key, value)" />
                        <FieldLabel :for="'confirm-' + check.key">{{ confirmations.includes(check.key) ? "已核验" : "确认已核验" }}<span class="sr-only">：{{ check.title }}</span></FieldLabel>
                      </Field>
                      <Button v-if="check.route" variant="link" size="sm" @click="openCheckSource(check)">{{ check.route === 'project-reports' ? "核对报告正文" : "打开" + (routeLabels[check.route] || "处理页面") }}<ArrowRight data-icon="inline-end" /></Button>
                    </div>
                  </article>
                  <Card v-if="!displayedChecks.length" class="review-check-empty"><CardHeader><CheckCircle2 :size="24" /><CardTitle role="heading" aria-level="3">{{ checkFilter === 'unconfirmed' ? "人工核验项已全部确认" : "此分类没有检查项" }}</CardTitle><CardDescription>可切换分类查看其他结果，或继续填写签署意见。</CardDescription></CardHeader><CardFooter><Button variant="outline" size="sm" @click="checkFilter = 'all'">查看全部检查</Button><Button size="sm" variant="ghost" @click="jumpToSignoff">前往签署</Button></CardFooter></Card>
                </div>
              </div>

              <aside ref="signoffElement" class="review-signoff" aria-label="人工核验与签署">
                <Card>
                  <CardHeader><div class="signoff-heading"><ShieldCheck :size="18" /><CardTitle role="heading" aria-level="2">{{ selectedRun.decidedAt ? "签署记录" : "核验与签署" }}</CardTitle></div><CardDescription>{{ signoffHint }}</CardDescription></CardHeader>
                  <CardContent class="signoff-content">
                    <div v-if="requiredChecks.length" class="confirmation-progress"><div><span>人工核验进度</span><strong>{{ confirmedCount }} / {{ requiredChecks.length }}</strong></div><div role="progressbar" aria-label="人工核验进度" :aria-valuenow="confirmedCount" aria-valuemin="0" :aria-valuemax="requiredChecks.length" class="confirmation-track"><span :style="{ width: confirmedCount / requiredChecks.length * 100 + '%' }" /></div><Button v-if="remainingCount" variant="link" size="sm" @click="showUnconfirmed">查看 {{ remainingCount }} 项未确认内容<ArrowRight data-icon="inline-end" /></Button></div>
                    <div v-if="selectedRun.decidedAt" class="saved-decision">
                      <Badge :variant="selectedRun.status === 'CHANGES_REQUESTED' ? 'destructive' : 'secondary'">{{ labels[selectedRun.status] || selectedRun.status }}</Badge>
                      <dl><div><dt>签署人</dt><dd>{{ selectedRun.decidedByName || (selectedRun.decidedBy ? "用户 " + selectedRun.decidedBy : "未记录") }}</dd></div><div><dt>签署时间</dt><dd>{{ formatDateTime(selectedRun.decidedAt, "时间未记录") }}</dd></div></dl>
                      <h3>审查意见</h3><p>{{ selectedRun.decisionComment || "未记录意见" }}</p>
                    </div>
                    <FieldGroup v-else-if="!isHistorical && !selectedRun.stale && policy.canManage">
                      <Field><FieldLabel for="review-comment">审查意见（必填）</FieldLabel><textarea id="review-comment" v-model="comment" rows="6" maxlength="4000" :disabled="!canDecide" aria-required="true" placeholder="记录核验依据、结论及可接受的限制；退回时请写清需修改的问题。" /><FieldDescription class="comment-count">{{ comment.length }} / 4000 字<span v-if="decisionDirty">尚未签署</span></FieldDescription></Field>
                    </FieldGroup>
                    <p v-else class="review-note">请先处理上方提示，再继续签署。本次检查的明细仍可查看。</p>
                    <Alert v-if="decisionError" variant="destructive"><AlertTitle>签署未完成</AlertTitle><AlertDescription>{{ decisionError }}</AlertDescription></Alert>
                  </CardContent>
                  <CardFooter class="signoff-footer">
                    <template v-if="selectedRun.status === 'APPROVED' && !selectedRun.stale && !isHistorical"><Button @click="go('project-reports')">前往报告发布<ArrowRight data-icon="inline-end" /></Button></template>
                    <template v-else-if="policy.canManage && !selectedRun.decidedAt && !selectedRun.stale && !isHistorical">
                      <Button :disabled="!canApprove" @click="decide('APPROVED')"><LoaderCircle v-if="submitting" data-icon="inline-start" class="is-spinning" /><CheckCircle2 v-else data-icon="inline-start" />签署通过</Button>
                      <Button variant="outline" :disabled="!canDecide || !comment.trim() || comment.length > 4000" @click="decide('CHANGES_REQUESTED')">退回修改</Button>
                    </template>
                    <Button v-if="policy.canManage && !isHistorical && (selectedRun.blockedCount || selectedRun.status === 'CHANGES_REQUESTED')" variant="outline" :disabled="busy" @click="createAction">建立修复行动项<ArrowRight data-icon="inline-end" /></Button>
                    <Button v-if="isHistorical && latest" variant="outline" :disabled="busy" @click="selectRun(latest)">返回最新检查</Button>
                    <Button v-else-if="policy.canManage && (selectedRun.stale || selectedRun.status === 'CHANGES_REQUESTED')" variant="outline" :disabled="busy || dirty" @click="runReview">重新检查当前报告<RefreshCw data-icon="inline-end" /></Button>
                  </CardFooter>
                </Card>
              </aside>
            </div>
          </TabsContent>

          <TabsContent value="body" class="review-body-tab">
            <div class="review-document-toolbar">
              <div><h2>{{ viewingSnapshot ? "审查时的报告正文" : "当前报告正文" }}</h2><p>{{ viewingSnapshot ? "保留本次检查时的正文，可切换查看当前保存的版本。" : "当前保存的正文；签署以所选检查的快照为依据。" }}</p></div>
              <div class="document-actions"><Button v-if="selectedRun?.reportSnapshot && 'content' in selectedRun.reportSnapshot" variant="outline" size="sm" @click="showCurrentBody = !showCurrentBody">{{ viewingSnapshot ? "对照当前正文" : "返回审查快照" }}</Button><Button variant="outline" size="sm" @click="returnToChecks">返回检查结果<ArrowRight data-icon="inline-end" /></Button></div>
            </div>
            <div class="review-document-paper"><ReviewReportBody :content="reportBody" /></div>
          </TabsContent>

          <TabsContent value="history" class="review-history-tab">
            <div class="review-section-heading"><div><h2>审查记录</h2><p>每条记录保存当时的正文、核验结果与签署意见。</p></div><span>{{ reportHistory.length }} 条记录</span></div>
            <div v-if="reportHistory.length" class="review-history">
              <article v-for="run in reportHistory" :key="String(run.id)" :class="{ selected: selectedRun?.id === run.id }">
                <div class="history-status"><span class="history-icon"><History :size="17" /></span><div><div class="history-title"><h3>检查 #{{ run.id }}</h3><Badge v-if="run.id === latest?.id" variant="outline">最新</Badge><Badge :variant="run.status === 'BLOCKED' || run.status === 'CHANGES_REQUESTED' ? 'destructive' : 'secondary'">{{ run.stale ? "已失效" : labels[run.status] || run.status }}</Badge></div><p>报告 v{{ run.reportVersion || "未编号" }} · {{ formatDateTime(run.createdAt, "时间未记录") }}</p><p v-if="run.decidedByName">签署：{{ run.decidedByName }}</p></div></div>
                <p class="history-comment">{{ run.decisionComment || run.detail || "尚未记录签署意见" }}</p>
                <Button variant="outline" size="sm" :disabled="busy" @click="selectedRun?.id === run.id ? activeTab = 'checks' : selectRun(run)">查看检查<ArrowRight data-icon="inline-end" /></Button>
              </article>
            </div>
            <Card v-else class="review-empty"><CardHeader><History :size="26" /><CardTitle role="heading" aria-level="2">暂无审查记录</CardTitle><CardDescription>首次运行检查后，会在这里保留检查和签署历史。</CardDescription></CardHeader></Card>
          </TabsContent>
        </Tabs>
      </template>
      <details v-if="legacyHistory.length && (activeTab === 'history' || !reports.length)" class="review-legacy"><summary>旧版项目数量检查 · {{ legacyHistory.length }} 条<ChevronDown :size="14" /></summary><p class="review-note">旧记录未绑定报告版本，仅供历史参考。请检查当前报告后签署。</p><p v-for="run in legacyHistory" :key="String(run.id)" class="review-note">#{{ run.id }} · {{ formatDateTime(run.createdAt, "时间未记录") }} · {{ run.detail }}</p></details>
    </template>

    <Dialog :open="rulesOpen" @update:open="value => { if (!value) void closeRules(); }">
      <DialogContent class="review-rules-dialog" :show-close-button="false">
        <DialogHeader><div class="rules-dialog-heading"><DialogTitle>检查规则</DialogTitle><Button variant="ghost" size="icon-sm" aria-label="关闭检查规则" :disabled="saving" @click="closeRules"><X /></Button></div><DialogDescription>规则应用于当前项目。保存后，原有检查可能失效，需要重新检查并签署。</DialogDescription></DialogHeader>
        <Alert v-if="policyError" variant="destructive"><AlertTitle>规则未保存</AlertTitle><AlertDescription>{{ policyError }}</AlertDescription></Alert>
        <FieldGroup><FieldSet><FieldLegend class="sr-only">报告核验要求</FieldLegend>
          <Field v-for="rule in ruleDefinitions" :key="rule.key" orientation="horizontal" class="review-rule">
            <Checkbox :id="'rule-' + rule.key" v-model="policyDraft[rule.key]" :disabled="busy || !policy?.canManage" />
            <div><FieldLabel :for="'rule-' + rule.key">{{ rule.label }}</FieldLabel><FieldDescription>{{ rule.detail }}</FieldDescription></div>
          </Field>
        </FieldSet></FieldGroup>
        <p v-if="!policy?.canManage" class="review-note">当前仅可查看规则，项目创建者或管理员可以修改。</p>
        <DialogFooter><Button variant="outline" :disabled="saving" @click="closeRules">{{ dirty ? "取消" : "关闭" }}</Button><Button v-if="policy?.canManage" :disabled="!dirty || busy" @click="savePolicy"><LoaderCircle v-if="saving" data-icon="inline-start" class="is-spinning" />{{ saving ? "保存中…" : "保存规则" }}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
    <Dialog :open="discardOpen" @update:open="value => { if (!value) decideDiscard(false); }"><DialogContent><DialogHeader><DialogTitle>放弃未保存的修改？</DialogTitle><DialogDescription>{{ discardDescription }}</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" @click="decideDiscard(false)">继续处理</Button><Button variant="destructive" @click="decideDiscard(true)">放弃修改</Button></DialogFooter></DialogContent></Dialog>
  </section>
</template>

<style scoped>
.review-workbench {
  --card: var(--surface); --card-foreground: var(--workspace-text); --background: var(--surface);
  --foreground: var(--workspace-text); --border: var(--workspace-border); --input: var(--workspace-border);
  --muted: var(--surface-soft); --muted-foreground: var(--workspace-muted);
  display: flex; flex-direction: column; flex: 1 1 0; min-width: 0; min-height: 0; height: 100%;
  overflow: hidden; gap: 1rem; padding: .125rem .125rem 0;
}
.review-workbench > * { flex-shrink: 0; }
.review-scope { display: flex; align-items: flex-end; gap: 1rem; justify-content: space-between; }
.review-report-field { flex: 1; max-width: 47rem; min-width: 0; gap: .5rem; }
.review-report-field :deep(label) { font-size: .75rem; color: var(--workspace-muted); }
.review-workbench select {
  height: 2.4rem; width: 100%; min-width: 0; padding: .4rem .6rem;
  border: 1px solid var(--workspace-border); border-radius: .5rem; background: var(--surface);
  color: var(--workspace-text); font: inherit; font-size: .8rem; text-overflow: ellipsis; outline: none;
}
.review-workbench select:focus-visible, .review-signoff textarea:focus-visible { border-color: var(--ring); box-shadow: 0 0 0 3px color-mix(in oklab,var(--ring) 25%,transparent); }
.review-scope-actions { display: flex; align-items: center; gap: .5rem; flex-shrink: 0; padding-bottom: .1rem; }
.rules-count { color: var(--workspace-muted); font-size: .68rem; }
.review-access-note { display: flex; align-items: flex-start; gap: .45rem; color: var(--workspace-muted); font-size: .75rem; line-height: 1.8; margin: 0; }
.review-access-note svg { flex-shrink: 0; margin-top: .2rem; }
.review-status { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1.1rem 1.2rem; border: 1px solid var(--workspace-border); background: var(--surface); border-radius: .75rem; min-width: 0; }
.review-status.has-blockers { border-color: color-mix(in oklab,var(--destructive) 35%,var(--workspace-border)); }
.review-status-copy { display: flex; align-items: center; gap: .8rem; min-width: 0; }
.review-status-copy > div { min-width: 0; }
.review-status-icon { color: var(--teal-dark); flex-shrink: 0; }
.has-blockers .review-status-icon { color: var(--destructive); }
.review-status-title { display: flex; flex-wrap: wrap; align-items: center; gap: .65rem; }
.review-status h2 { font-size: .95rem; line-height: 1.6; font-weight: 600; margin: 0; }
.review-status p { display: flex; flex-wrap: wrap; gap: .4rem .8rem; color: var(--workspace-muted); font-size: .72rem; line-height: 1.7; margin: .4rem 0 0; }
.review-status > button { flex-shrink: 0; }
.review-workbench > .review-tabs { flex: 1 1 0; gap: 1rem; min-width: 0; min-height: 0; overflow: hidden; }
.review-tab-bar { display: flex; align-items: center; justify-content: space-between; gap: .5rem; border-bottom: 1px solid var(--workspace-border); padding-bottom: .8rem; flex-shrink: 0; }
.tab-count { color: var(--workspace-muted); font-size: .68rem; }
.review-checks-tab, .review-body-tab, .review-history-tab { min-width: 0; min-height: 0; flex: 1 1 0; overscroll-behavior: contain; }
.review-body-tab, .review-history-tab { overflow-y: auto; scrollbar-gutter: stable; padding-right: .5rem; padding-bottom: 1rem; }
.review-checks-tab { overflow: hidden; }
.review-columns { display: grid; grid-template-columns: minmax(0,1fr) minmax(18rem,21rem); grid-template-rows: minmax(0,1fr); align-items: stretch; gap: 1.25rem; height: 100%; min-height: 0; }
.review-main { display: flex; flex-direction: column; gap: 1rem; min-width: 0; min-height: 0; overflow: hidden; }
.review-main > .review-metrics, .review-main > .review-check-toolbar { flex-shrink: 0; }
.review-metrics { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; padding-bottom: 1rem; border-bottom: 1px solid var(--workspace-border); }
.review-metrics > div { display: flex; flex-direction: column; gap: .4rem; }
.review-metrics > div > span { font-size: .72rem; color: var(--workspace-muted); }
.review-metrics strong { font-size: 1.35rem; line-height: 1.3; font-weight: 650; font-variant-numeric: tabular-nums; }
.review-metrics small { font-size: .72rem; font-weight: 400; color: var(--workspace-muted); margin-left: .4rem; }
.review-metrics .text-blocked { color: var(--destructive); }
.review-check-toolbar { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
.review-check-toolbar h2, .review-document-toolbar h2, .review-section-heading h2 { margin: 0; font-size: .9rem; line-height: 1.7; font-weight: 600; }
.review-check-toolbar p, .review-document-toolbar p, .review-section-heading p { margin: .2rem 0 0; color: var(--workspace-muted); font-size: .72rem; line-height: 1.7; }
.review-filter-field { width: 10.5rem; flex-shrink: 0; }
.review-filter-field select { height: 2.2rem; font-size: .72rem; }
.review-check-list { display: flex; flex-direction: column; gap: .85rem; flex: 1 1 0; min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; padding-right: .5rem; padding-bottom: .5rem; }
.review-check-list > * { flex-shrink: 0; }
.review-check { display: flex; flex-direction: column; gap: .75rem; padding: 1.1rem; border: 1px solid var(--workspace-border); border-radius: .75rem; background: var(--surface); min-width: 0; }
.review-check.check-blocked { border-left: 3px solid var(--destructive); }
.review-check.check-confirmed { border-color: color-mix(in oklab,var(--teal) 45%,var(--workspace-border)); }
.review-check-heading { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
.review-check h3 { font-size: .85rem; font-weight: 600; line-height: 1.6; margin: 0; overflow-wrap: anywhere; }
.review-check p, .review-note { font-size: .8rem; line-height: 1.8; color: var(--workspace-muted); margin: 0; overflow-wrap: anywhere; }
.review-check-heading :deep([data-slot=badge]) { flex-shrink: 0; }
.review-excerpt-details { background: var(--surface-soft); border-radius: .5rem; }
.review-excerpt-details summary { display: flex; align-items: center; gap: .5rem; padding: .6rem .75rem; color: var(--workspace-muted); font-size: .72rem; cursor: pointer; }
.review-excerpt-details summary span { margin-left: auto; }
.review-excerpt-details[open] summary > svg { rotate: 180deg; }
.review-excerpts { margin: 0; padding: 0 1rem .85rem 1.8rem; color: var(--workspace-text); font-size: .78rem; line-height: 1.8; list-style: disc; overflow-wrap: anywhere; }
.review-excerpts li + li { margin-top: .4rem; }
.review-check-footer { display: flex; align-items: center; justify-content: flex-end; gap: .75rem; padding-top: .5rem; border-top: 1px solid var(--workspace-divider); }
.review-confirm-field { flex: 1; width: auto; gap: .5rem; }
.review-confirm-field :deep(label) { font-size: .75rem; cursor: pointer; }
.review-check-footer > button { padding-right: 0; height: auto; font-size: .75rem; }
.review-signoff { min-width: 0; min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; padding-right: .5rem; padding-bottom: .5rem; }
.review-signoff :deep([data-slot=card]) { gap: 1.15rem; }
.review-signoff :deep([data-slot=card-header]), .review-signoff :deep([data-slot=card-content]), .review-signoff :deep([data-slot=card-footer]) { padding-inline: 1.1rem; }
.signoff-heading { display: flex; align-items: center; gap: .5rem; }
.signoff-content { display: flex; flex-direction: column; gap: 1.1rem; }
.confirmation-progress { display: flex; flex-direction: column; gap: .6rem; }
.confirmation-progress > div:first-child { display: flex; align-items: center; justify-content: space-between; color: var(--workspace-muted); font-size: .75rem; }
.confirmation-progress strong { color: var(--workspace-text); font-weight: 600; font-variant-numeric: tabular-nums; }
.confirmation-progress > button { align-self: flex-start; height: auto; padding: 0; font-size: .72rem; }
.confirmation-track { height: .35rem; background: var(--surface-soft); border-radius: 1rem; overflow: hidden; }
.confirmation-track span { display: block; height: 100%; background: var(--teal); transition: width .15s ease; }
.review-signoff textarea { width: 100%; min-width: 0; box-sizing: border-box; padding: .7rem; font: inherit; font-size: .8rem; line-height: 1.8; resize: vertical; border: 1px solid var(--workspace-border); border-radius: .5rem; background: var(--surface); color: var(--workspace-text); outline: none; }
.comment-count { display: flex; flex-wrap: wrap; justify-content: space-between; gap: .5rem; }
.signoff-footer { display: flex; flex-wrap: wrap; gap: .5rem; }
.signoff-footer > button:first-child { flex: 1; }
.signoff-footer > button:nth-child(n+3) { width: 100%; }
.saved-decision { display: flex; flex-direction: column; gap: 1rem; }
.saved-decision > :deep([data-slot=badge]) { align-self: flex-start; }
.saved-decision dl { display: flex; flex-direction: column; gap: .7rem; margin: 0; }
.saved-decision dl > div { display: flex; flex-direction: column; gap: .25rem; }
.saved-decision dt { color: var(--workspace-muted); font-size: .72rem; }
.saved-decision dd { font-size: .8rem; margin: 0; overflow-wrap: anywhere; }
.saved-decision h3 { font-size: .8rem; margin: 0; font-weight: 600; }
.saved-decision p { margin: -.5rem 0 0; white-space: pre-wrap; font-size: .8rem; line-height: 1.85; overflow-wrap: anywhere; }
.review-empty { margin-block: 1rem; }
.review-empty :deep([data-slot=card-header]) { gap: .85rem; }
.review-empty :deep([data-slot=card-footer]) { display: flex; gap: .6rem; flex-wrap: wrap; }
.review-check-empty :deep([data-slot=card-header]) { gap: .65rem; }
.review-check-empty :deep([data-slot=card-footer]) { gap: .5rem; flex-wrap: wrap; }
.review-document-toolbar, .review-section-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.document-actions { display: flex; flex-wrap: wrap; gap: .5rem; flex-shrink: 0; }
.review-document-paper { background: var(--surface); border: 1px solid var(--workspace-border); border-radius: .75rem; padding: clamp(1.25rem,3vw,2.5rem); max-width: 65rem; margin-inline: auto; min-width: 0; }
.review-section-heading > span { color: var(--workspace-muted); font-size: .75rem; white-space: nowrap; }
.review-history { display: flex; flex-direction: column; gap: .75rem; }
.review-history > article { display: grid; grid-template-columns: minmax(13rem,.9fr) minmax(0,1fr) auto; align-items: center; gap: 1.25rem; padding: 1.1rem; background: var(--surface); border: 1px solid var(--workspace-border); border-radius: .65rem; }
.review-history > article.selected { border-color: color-mix(in oklab,var(--teal) 50%,var(--workspace-border)); }
.history-status { display: flex; align-items: flex-start; gap: .75rem; min-width: 0; }
.history-icon { color: var(--workspace-muted); margin-top: .15rem; }
.history-title { display: flex; align-items: center; flex-wrap: wrap; gap: .5rem; }
.history-title h3 { font-size: .85rem; font-weight: 600; margin: 0; }
.history-status p { margin: .4rem 0 0; font-size: .72rem; color: var(--workspace-muted); line-height: 1.7; }
.history-comment { margin: 0; font-size: .8rem; line-height: 1.85; color: var(--workspace-muted); white-space: pre-wrap; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.review-legacy { max-height: 12rem; overflow-y: auto; overscroll-behavior: contain; }
.review-legacy summary { display: flex; align-items: center; gap: .5rem; font-size: .75rem; color: var(--workspace-muted); cursor: pointer; }
.review-legacy p { margin-top: .75rem; }
.review-loading { display: flex; align-items: center; gap: .65rem; padding: 3rem 1rem; color: var(--workspace-muted); font-size: .8rem; }
:global(.review-rules-dialog) { max-height: calc(100dvh - 2rem); overflow-y: auto; }
.rules-dialog-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.review-rule { align-items: flex-start; padding-block: .5rem; }
.review-rule > :deep([role=checkbox]) { margin-top: .15rem; }
.review-rule > div { min-width: 0; display: flex; flex-direction: column; gap: .5rem; }
@media(max-width:80rem) { .review-scope { flex-wrap: wrap; align-items: center; gap: .75rem; } .review-report-field { flex-basis: 100%; max-width: none; } .review-scope-actions { margin-left: auto; } }
@media(max-width:68.75rem) { .review-checks-tab { overflow-y: auto; scrollbar-gutter: stable; padding-right: .5rem; padding-bottom: 1rem; } .review-columns { grid-template-columns: minmax(0,1fr); grid-template-rows: auto; height: auto; align-items: start; } .review-main, .review-signoff { overflow: visible; padding-right: 0; } .review-check-list { overflow: visible; flex: none; padding-right: 0; } .review-history > article { grid-template-columns: minmax(0,1fr) auto; gap: .75rem; } .history-comment { grid-column: 1/-1; grid-row: 2; } .review-document-toolbar { flex-wrap: wrap; } }
@media(max-width:47.5rem) {
  .review-workbench { gap: .85rem; }
  .review-scope-actions { margin-left: 0; width: 100%; justify-content: space-between; }
  .review-status { padding: 1rem; align-items: stretch; flex-direction: column; gap: .75rem; }
  .review-status h2 { font-size: .85rem; }
  .review-status-copy { align-items: flex-start; gap: .6rem; }
  .review-status-icon { margin-top: .15rem; }
  .review-status > button { align-self: flex-end; }
  .review-status p { gap: .25rem .6rem; font-size: .68rem; }
  .review-status-title { gap: .4rem; }
  .review-tab-bar { flex-wrap: wrap; gap: .25rem; }
  .review-tab-bar :deep([role=tablist]) { width: 100%; }
  .review-tab-bar :deep([role=tab]) { gap: .3rem; padding-inline: .5rem; font-size: .75rem; }
  .review-tab-bar > button { margin-left: auto; height: 1.8rem; font-size: .7rem; }
  .review-metrics { gap: .35rem; }
  .review-metrics > div > span { font-size: .68rem; }
  .review-metrics strong { font-size: 1.15rem; }
  .review-metrics small { display: block; margin: .25rem 0 0; font-size: .65rem; }
  .review-check-toolbar { flex-wrap: wrap; }
  .review-check-toolbar > div { width: 100%; }
  .review-filter-field { width: 100%; }
  .review-check { padding: 1rem; }
  .review-check-footer { flex-wrap: wrap; gap: .5rem; }
  .review-check p { font-size: .78rem; }
  .review-check-heading { gap: .5rem; }
  .review-confirm-field { min-width: 8rem; }
  .review-history > article { grid-template-columns: 1fr; }
  .review-history > article > button { justify-self: start; grid-row: 3; }
  .document-actions { width: 100%; }
  .review-document-paper { padding: 1.1rem; }
  .review-section-heading { align-items: flex-start; }
}
</style>
