<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Database,
  FileCheck2,
  FileText,
  LockKeyhole,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Users,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { reviewApi } from "@/api/review";
import type { ProjectReviewRun } from "@/api/types";

const {
  selectedProject,
  workspaceId,
  projectId,
  router,
  routeTo,
  assets,
  recentRuns,
  reports,
  actionItems,
  evaluationCases,
  notify,
} = useWorkspace();

type ReviewRule = {
  key: string;
  title: string;
  detail: string;
  severity: "阻断" | "升级" | "提示";
  enabled: boolean;
};

const rules = reactive<ReviewRule[]>([
  { key: "citation", title: "结论必须可引用", detail: "每个事实性判断都要能定位到资料、页面或外部来源。", severity: "阻断", enabled: true },
  { key: "numbers", title: "数字和时间必须核验", detail: "金额、比例、日期、规模等数字缺少来源时不得发布。", severity: "阻断", enabled: true },
  { key: "conflict", title: "冲突来源自动升级", detail: "来源之间存在矛盾时，标记差异并交由负责人确认。", severity: "升级", enabled: true },
  { key: "external", title: "外部材料必须标注", detail: "竞品、市场和网页资料要记录抓取时间与来源类型。", severity: "提示", enabled: true },
]);
const reviewRun = ref<ProjectReviewRun | null>(null);
const reviewLoading = ref(false);
const savingRules = ref(false);
const governanceLoaded = ref(false);
const indexedCount = computed(
  () => assets.filter((asset) => asset.status === "indexed").length,
);
const enabledRuleCount = computed(() => rules.filter((rule) => rule.enabled).length);
const projectName = computed(() => selectedProject.value?.name || "当前项目");

const checks = computed(() => [
  {
    key: "source",
    title: "资料来源覆盖",
    detail: assets.length ? `${indexedCount.value}/${assets.length} 份项目资料已完成索引` : "没有资料可供核验",
    status: indexedCount.value > 0 ? "review" : "blocked",
    icon: Database,
  },
  {
    key: "market",
    title: "市场与竞品来源",
    detail: recentRuns.length ? "已有调研运行，等待逐条检查外部来源" : "尚未发起市场或竞品资料搜集",
    status: recentRuns.length ? "review" : "blocked",
    icon: Search,
  },
  {
    key: "report",
    title: "报告事实性断言",
    detail: reports.length ? `${reports.length} 份报告待做引用覆盖检查` : "尚未生成可审查报告",
    status: reports.length ? "review" : "blocked",
    icon: FileText,
  },
  {
    key: "evaluation",
    title: "反证与回归用例",
    detail: evaluationCases.length ? `${evaluationCases.length} 个评估用例可用于回归` : "尚未建立反证用例",
    status: evaluationCases.length ? "review" : "blocked",
    icon: FileCheck2,
  },
  {
    key: "signoff",
    title: "人工责任确认",
    detail: actionItems.length ? `${actionItems.length} 个行动项已登记，仍需负责人签署` : "未登记负责人和后续行动",
    status: "pending",
    icon: Users,
  },
]);

const statusCopy: Record<string, string> = {
  blocked: "阻断",
  review: "待核验",
  pending: "待签署",
};

const auditSummary = computed(() => {
  if (!reviewRun.value) return "尚未运行结构化检查";
  if (reviewRun.value.blockedCount) return reviewRun.value.detail;
  return `结构化检查完成，仍有 ${reviewRun.value.reviewCount} 个项目需要人工确认`;
});

const currentReviewStatus = computed(() => {
  if (!reviewRun.value) return "尚未检查";
  return reviewRun.value.blockedCount > 0 ? "不可发布" : "待人工确认";
});

async function loadGovernance() {
  reviewLoading.value = true;
  try {
    const [policy, latest] = await Promise.all([
      reviewApi.policy(workspaceId.value, projectId.value),
      reviewApi.latest(workspaceId.value, projectId.value),
    ]);
    rules.find((rule) => rule.key === "citation")!.enabled = policy.requireCitations;
    rules.find((rule) => rule.key === "numbers")!.enabled = policy.verifyNumbers;
    rules.find((rule) => rule.key === "conflict")!.enabled = policy.escalateConflicts;
    rules.find((rule) => rule.key === "external")!.enabled = policy.labelExternal;
    reviewRun.value = latest;
    governanceLoaded.value = true;
  } catch (error) {
    governanceLoaded.value = false;
    notify(error instanceof Error ? `审查数据加载失败：${error.message}` : "审查数据加载失败，未使用本地数据");
  } finally {
    reviewLoading.value = false;
  }
}

async function saveRules() {
  if (savingRules.value || !governanceLoaded.value) return;
  savingRules.value = true;
  try {
    await reviewApi.savePolicy(workspaceId.value, projectId.value, {
      requireCitations: rules.find((rule) => rule.key === "citation")!.enabled,
      verifyNumbers: rules.find((rule) => rule.key === "numbers")!.enabled,
      escalateConflicts: rules.find((rule) => rule.key === "conflict")!.enabled,
      labelExternal: rules.find((rule) => rule.key === "external")!.enabled,
    });
    notify("审查规则已保存到项目空间");
  } catch (error) {
    notify(error instanceof Error ? `审查规则未保存：${error.message}` : "审查规则未保存，数据库暂不可用");
  } finally {
    savingRules.value = false;
  }
}

async function runReview() {
  if (reviewLoading.value || !governanceLoaded.value) return;
  reviewLoading.value = true;
  try {
    reviewRun.value = await reviewApi.run(workspaceId.value, projectId.value);
    notify("结构化审查已完成，结果已写入数据库");
  } catch (error) {
    notify(error instanceof Error ? `审查未完成：${error.message}` : "审查未完成，未生成本地结果");
  } finally {
    reviewLoading.value = false;
  }
}

function openPlanning() {
  router.push(routeTo("project-planning"));
}

onMounted(loadGovernance);
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / GOVERNANCE"
    title="审查中心"
    :subtitle="`为 ${projectName} 建立可追溯、可反驳、可签署的结论发布门禁。`"
  >
    <template #action>
      <button class="button button-secondary" type="button" @click="openPlanning"><ChevronRight :size="15" />返回规划中枢</button>
      <button class="button button-primary" type="button" :disabled="reviewLoading" @click="runReview"><RefreshCw :size="15" />{{ reviewLoading ? "检查中" : "运行结构化检查" }}</button>
    </template>
  </PageHeader>

  <section class="review-hero panel">
    <div class="review-hero-icon"><ShieldAlert :size="24" /></div>
    <div class="review-hero-copy"><strong>没有证据，就没有结论</strong><p>审查中心把“事实、推断、建议”分开处理。引用缺失、数字无法核验或来源互相冲突时，计划书保持在草稿状态。</p><div class="review-hero-tags"><span><Ban :size="12" />发布阻断开启</span><span><LockKeyhole :size="12" />{{ governanceLoaded ? `${enabledRuleCount} 项规则生效` : "规则状态不可用" }}</span><span v-if="reviewRun"><Check :size="12" />本次检查已运行</span></div></div>
    <div class="review-hero-status"><span>当前状态</span><strong>{{ currentReviewStatus }}</strong><small>{{ auditSummary }}</small></div>
  </section>

  <div class="review-metrics">
    <article class="review-metric"><span class="review-metric-icon red"><Ban :size="16" /></span><div><strong>{{ reviewRun ? reviewRun.blockedCount : '—' }}</strong><small>最近一次阻断项</small></div></article>
    <article class="review-metric"><span class="review-metric-icon amber"><CircleAlert :size="16" /></span><div><strong>{{ reviewRun ? reviewRun.reviewCount : '—' }}</strong><small>最近一次待核验项</small></div></article>
    <article class="review-metric"><span class="review-metric-icon teal"><Database :size="16" /></span><div><strong>{{ indexedCount }}/{{ assets.length || '—' }}</strong><small>资料已索引</small></div></article>
    <article class="review-metric"><span class="review-metric-icon blue"><ShieldCheck :size="16" /></span><div><strong>{{ evaluationCases.length || '—' }}</strong><small>反证用例</small></div></article>
  </div>

  <div class="review-layout">
    <section class="panel checks-panel">
      <div class="panel-heading"><div><h2>结论发布检查</h2><p>先由系统发现缺口，再由负责人核验具体断言</p></div><span class="review-policy-badge"><ShieldCheck :size="13" />安全模式</span></div>
      <div class="check-list">
        <div v-for="item in checks" :key="item.key" class="check-row">
          <span class="check-icon" :class="item.status"><component :is="item.icon" :size="16" /></span>
          <div class="check-copy"><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></div>
          <span class="check-status" :class="item.status">{{ statusCopy[item.status] }}</span>
          <ChevronRight :size="14" class="check-arrow" />
        </div>
      </div>
      <div class="checks-footer"><span><LockKeyhole :size="13" />规则检查只报告缺口，不替代人工判断</span><button class="button button-secondary button-sm" type="button" :disabled="reviewLoading" @click="runReview"><RefreshCw :size="13" />重新检查</button></div>
    </section>

    <section class="panel rules-panel">
      <div class="panel-heading"><div><h2>反虚构策略</h2><p>项目级规则，可在发布前强制执行</p></div><ShieldCheck :size="17" class="rules-heading-icon" /></div>
      <div class="rule-list">
        <label v-for="rule in rules" :key="rule.key" class="rule-row"><input v-model="rule.enabled" :disabled="!governanceLoaded || reviewLoading" type="checkbox" :aria-label="rule.title" /><span class="rule-toggle" /><span class="rule-copy"><strong>{{ rule.title }}</strong><small>{{ rule.detail }}</small></span><span class="rule-severity" :class="rule.severity === '阻断' ? 'danger' : rule.severity === '升级' ? 'warning' : 'info'">{{ rule.severity }}</span></label>
      </div>
      <div class="rule-note"><ShieldAlert :size="14" /><span>关闭阻断规则会降低本项目可信等级，并记录在审查日志中。</span></div>
      <button class="button button-secondary full-button" type="button" :disabled="savingRules || reviewLoading" @click="saveRules"><Check :size="14" />{{ savingRules ? "保存中" : "保存审查策略" }}</button>
    </section>
  </div>

  <div class="review-lower-grid">
    <section class="panel flow-panel">
      <div class="panel-heading"><div><h2>审查流程</h2><p>按证据链顺序推进，任何阶段都可以回到资料层修正</p></div></div>
      <div class="review-flow">
        <div class="flow-item done"><span>01</span><div><strong>输入登记</strong><small>目标、范围、负责人</small></div><CheckCircle2 :size="15" /></div>
        <div class="flow-line" />
        <div class="flow-item"><span>02</span><div><strong>证据核验</strong><small>来源、版本、引用位置</small></div><Database :size="15" /></div>
        <div class="flow-line" />
        <div class="flow-item"><span>03</span><div><strong>反证检查</strong><small>冲突、假设、失败条件</small></div><CircleAlert :size="15" /></div>
        <div class="flow-line" />
        <div class="flow-item"><span>04</span><div><strong>人工签署</strong><small>责任人确认后才可发布</small></div><Users :size="15" /></div>
      </div>
    </section>

    <section class="panel audit-panel">
      <div class="panel-heading"><div><h2>审查记录</h2><p>为每次发布保留规则版本和处理结果</p></div><FileText :size="17" class="rules-heading-icon" /></div>
      <div v-if="reviewRun" class="audit-result"><span class="audit-result-icon"><ShieldAlert :size="17" /></span><div><strong>结构化检查结果已生成</strong><small>{{ auditSummary }}</small><em>{{ reviewRun.createdAt || "数据库时间不可用" }}</em></div></div>
      <div v-else class="audit-empty"><FileText :size="18" /><strong>暂无本次审查记录</strong><span>运行结构化检查后，系统会在这里记录检查时间与阻断原因。</span></div>
      <div class="audit-actions"><button class="text-button" type="button" @click="router.push(routeTo('project-evaluation'))">打开评估用例 <ArrowRight :size="14" /></button><button class="text-button" type="button" @click="router.push(routeTo('project-reports'))">查看报告版本 <ArrowRight :size="14" /></button></div>
    </section>
  </div>
</template>

<style scoped>
.review-hero { display: flex; align-items: center; gap: 0.875rem; min-height: 7.25rem; margin-bottom: 0.75rem; padding: 1.125rem 1.25rem; border-color: color-mix(in oklab, var(--red) 20%, var(--workspace-border)); background: linear-gradient(112deg, color-mix(in oklab, var(--red) 7%, var(--surface)), var(--surface)); }
.review-hero-icon { display: grid; width: 3rem; height: 3rem; flex: 0 0 auto; place-items: center; border-radius: 0.75rem; background: #fff0ef; color: #c46161; }
.review-hero-copy { min-width: 0; flex: 1; }
.review-hero-copy > strong { color: var(--workspace-text); font-size: 1rem; letter-spacing: -0.025em; }
.review-hero-copy p { margin: 0.375rem 0 0; color: var(--workspace-muted); font-size: 0.625rem; line-height: 1.6; }
.review-hero-tags { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.625rem; color: var(--workspace-muted); font-size: 0.5rem; }
.review-hero-tags span { display: inline-flex; align-items: center; gap: 0.25rem; }
.review-hero-tags svg { color: #c46161; }
.review-hero-status { display: grid; flex: 0 0 10rem; gap: 0.25rem; padding-left: 1.125rem; border-left: 0.0625rem solid var(--workspace-border); }
.review-hero-status span, .review-hero-status small { color: var(--workspace-muted); font-size: 0.5rem; }
.review-hero-status strong { color: #bd5555; font-size: 0.875rem; }
.review-hero-status small { line-height: 1.45; }
.review-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; margin-bottom: 0.75rem; }
.review-metric { display: flex; align-items: center; gap: 0.625rem; min-height: 4.125rem; padding: 0.75rem 0.875rem; border: 0.0625rem solid var(--workspace-border); border-radius: 0.625rem; background: var(--surface); }
.review-metric > div { display: grid; gap: 0.25rem; }
.review-metric strong { color: var(--workspace-text); font-size: 1.05rem; letter-spacing: -0.04em; }
.review-metric small { color: var(--workspace-muted); font-size: 0.5625rem; }
.review-metric-icon { display: grid; width: 2rem; height: 2rem; flex: 0 0 auto; place-items: center; border-radius: 0.5625rem; }
.review-metric-icon.red { background: #fff0ef; color: #bf5e5e; }
.review-metric-icon.amber { background: #fff4df; color: #b37b20; }
.review-metric-icon.teal { background: #e3f7f3; color: var(--teal-dark); }
.review-metric-icon.blue { background: #e8f2fd; color: #4b86c8; }
.review-layout, .review-lower-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(20rem, 0.8fr); gap: 0.75rem; }
.review-layout { margin-bottom: 0.75rem; }
.checks-panel, .rules-panel, .flow-panel, .audit-panel { min-width: 0; overflow: hidden; }
.review-policy-badge { display: inline-flex; align-items: center; gap: 0.3125rem; padding: 0.25rem 0.4375rem; border-radius: 999px; background: #e3f7f3; color: var(--teal-dark); font-size: 0.5rem; white-space: nowrap; }
.check-list { display: grid; padding: 0 1.25rem; }
.check-row { display: flex; align-items: center; gap: 0.625rem; min-width: 0; padding: 0.8125rem 0; border-top: 0.0625rem solid var(--workspace-divider); }
.check-icon { display: grid; width: 2rem; height: 2rem; flex: 0 0 auto; place-items: center; border-radius: 0.5625rem; }
.check-icon.blocked { color: #bd5959; background: #fff0ef; }
.check-icon.review { color: #a87520; background: #fff4df; }
.check-icon.pending { color: #6d7c81; background: var(--surface-soft); }
.check-copy { display: grid; min-width: 0; flex: 1; gap: 0.25rem; }
.check-copy strong, .check-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.check-copy strong { color: var(--workspace-text); font-size: 0.625rem; }
.check-copy small { color: var(--workspace-muted); font-size: 0.5rem; }
.check-status { padding: 0.25rem 0.4375rem; border-radius: 999px; font-size: 0.5rem; white-space: nowrap; }
.check-status.blocked { color: #bd5959; background: #fff0ef; }
.check-status.review { color: #a87520; background: #fff4df; }
.check-status.pending { color: #6d7c81; background: var(--surface-soft); }
.check-arrow { color: var(--workspace-subtle); }
.checks-footer { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin: 0.25rem 1.25rem 1rem; padding-top: 0.75rem; border-top: 0.0625rem solid var(--workspace-divider); color: var(--workspace-muted); font-size: 0.5rem; }
.checks-footer > span { display: inline-flex; align-items: center; gap: 0.3125rem; }
.rules-heading-icon { color: var(--teal-dark); }
.rule-list { display: grid; padding: 0 1.25rem; }
.rule-row { display: flex; align-items: flex-start; gap: 0.5625rem; min-width: 0; padding: 0.6875rem 0; border-top: 0.0625rem solid var(--workspace-divider); cursor: pointer; }
.rule-row input { position: absolute; opacity: 0; pointer-events: none; }
.rule-toggle { position: relative; display: block; width: 1.75rem; height: 1rem; flex: 0 0 auto; border-radius: 999px; background: var(--workspace-border); transition: background 0.18s ease; }
.rule-toggle::after { position: absolute; top: 0.125rem; left: 0.125rem; width: 0.75rem; height: 0.75rem; border-radius: 50%; background: white; box-shadow: 0 0.0625rem 0.1875rem rgb(0 0 0 / 12%); content: ""; transition: transform 0.18s ease; }
.rule-row input:checked + .rule-toggle { background: var(--teal); }
.rule-row input:checked + .rule-toggle::after { transform: translateX(0.75rem); }
.rule-copy { display: grid; min-width: 0; flex: 1; gap: 0.1875rem; }
.rule-copy strong, .rule-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rule-copy strong { color: var(--workspace-text); font-size: 0.5625rem; }
.rule-copy small { color: var(--workspace-muted); font-size: 0.5rem; line-height: 1.45; }
.rule-severity { flex: 0 0 auto; padding: 0.25rem 0.375rem; border-radius: 0.25rem; font-size: 0.5rem; }
.rule-severity.danger { color: #bd5959; background: #fff0ef; }
.rule-severity.warning { color: #a87520; background: #fff4df; }
.rule-severity.info { color: var(--teal-dark); background: #e3f7f3; }
.rule-note { display: flex; align-items: flex-start; gap: 0.4375rem; margin: 0.5rem 1.25rem 0; padding: 0.625rem 0.6875rem; border-radius: 0.4375rem; background: #fff8ed; color: #a87520; font-size: 0.5rem; line-height: 1.55; }
.rule-note svg { flex: 0 0 auto; }
.rules-panel .full-button { width: calc(100% - 2.5rem); margin: 1rem 1.25rem 1.25rem; }
.review-flow { display: flex; align-items: center; padding: 0.75rem 1.25rem 1.25rem; }
.flow-item { display: flex; align-items: center; gap: 0.4375rem; min-width: 0; }
.flow-item > span { display: grid; width: 1.75rem; height: 1.75rem; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--surface-soft); color: var(--workspace-muted); font: 700 0.5rem ui-monospace, monospace; }
.flow-item.done > span { background: #e3f7f3; color: var(--teal-dark); }
.flow-item > div { display: grid; min-width: 0; gap: 0.1875rem; }
.flow-item strong, .flow-item small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.flow-item strong { color: var(--workspace-text); font-size: 0.5625rem; }
.flow-item small { color: var(--workspace-muted); font-size: 0.5rem; }
.flow-item > svg { flex: 0 0 auto; color: var(--workspace-subtle); }
.flow-item.done > svg { color: var(--teal); }
.flow-line { height: 0.0625rem; min-width: 1rem; flex: 1; margin: 0 0.375rem; background: var(--workspace-border); }
.audit-result { display: flex; align-items: flex-start; gap: 0.625rem; margin: 0.25rem 1.25rem 0.75rem; padding: 0.75rem; border: 0.0625rem solid #f0d7d7; border-radius: 0.5rem; background: #fff8f8; }
.audit-result-icon { display: grid; width: 1.875rem; height: 1.875rem; flex: 0 0 auto; place-items: center; border-radius: 0.5rem; background: #fff0ef; color: #bd5959; }
.audit-result > div { display: grid; gap: 0.25rem; min-width: 0; }
.audit-result strong { color: var(--workspace-text); font-size: 0.5625rem; }
.audit-result small, .audit-result em { color: var(--workspace-muted); font-size: 0.5rem; font-style: normal; line-height: 1.45; }
.audit-empty { display: grid; justify-items: center; gap: 0.375rem; min-height: 6.75rem; margin: 0.25rem 1.25rem 0.75rem; padding: 0.875rem; border: 0.0625rem dashed var(--workspace-border); border-radius: 0.5rem; color: var(--workspace-muted); text-align: center; }
.audit-empty strong { color: var(--workspace-text); font-size: 0.5625rem; }
.audit-empty span { max-width: 18rem; font-size: 0.5rem; line-height: 1.55; }
.audit-actions { display: flex; gap: 1rem; margin: 0 1.25rem 1.125rem; padding-top: 0.75rem; border-top: 0.0625rem solid var(--workspace-divider); }
@media (max-width: 68.75rem) { .review-layout, .review-lower-grid { grid-template-columns: 1fr; } }
@media (max-width: 47.5rem) { .review-hero { align-items: flex-start; flex-wrap: wrap; } .review-hero-status { flex-basis: 100%; padding-top: 0.75rem; padding-left: 0; border-top: 0.0625rem solid var(--workspace-border); border-left: 0; } .review-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .review-flow { overflow-x: auto; align-items: flex-start; } .flow-item { min-width: 8.25rem; } .flow-line { flex: 0 0 1rem; margin-top: 0.875rem; } }
@media (max-width: 30rem) { .review-metrics { gap: 0.5rem; } .review-metric { padding-inline: 0.625rem; } .check-status, .rule-severity { display: none; } .checks-footer { align-items: flex-start; flex-direction: column; } }
</style>
