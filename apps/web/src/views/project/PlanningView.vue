<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCheck2,
  FileText,
  LockKeyhole,
  Save,
  Search,
  ShieldCheck,
  Target,
  Users,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { planningApi } from "@/api/planning";
import { formatDateTime } from "@/lib/utils";

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

type PlanningDraft = {
  objective: string;
  problem: string;
  successMetrics: string;
  constraints: string;
  owner: string;
  deadline: string;
};

const form = reactive<PlanningDraft>({
  objective: "",
  problem: "",
  successMetrics: "",
  constraints: "",
  owner: "",
  deadline: "",
});
const savedAt = ref("");
const dirty = ref(false);
const hydrating = ref(false);
const saving = ref(false);
const planLoadFailed = ref(false);

const projectName = computed(() => selectedProject.value?.name || "当前项目");
const indexedCount = computed(
  () => assets.filter((asset) => asset.status === "indexed").length,
);
const evidenceCoverage = computed(() => {
  if (!assets.length) return "待补齐";
  return `${Math.round((indexedCount.value / assets.length) * 100)}%`;
});
const readinessChecks = computed(() => [
  Boolean(form.objective.trim()),
  Boolean(form.problem.trim()),
  indexedCount.value > 0,
  recentRuns.length > 0,
  reports.length > 0,
]);
const readiness = computed(
  () =>
    `${Math.round(
      (readinessChecks.value.filter(Boolean).length /
        readinessChecks.value.length) *
        100,
    )}%`,
);

const reviewGates = computed(() => [
  {
    key: "scope",
    icon: Target,
    title: "目标与范围",
    detail: form.objective.trim()
      ? "已定义项目目标"
      : "需要补充目标、边界和交付物",
    status: form.objective.trim() ? "ready" : "pending",
  },
  {
    key: "evidence",
    icon: Database,
    title: "证据可追溯",
    detail: assets.length
      ? `${indexedCount.value}/${assets.length} 份资料已完成索引`
      : "尚未接入项目资料",
    status: indexedCount.value > 0 ? "ready" : "pending",
  },
  {
    key: "market",
    icon: Search,
    title: "市场与竞品对比",
    detail: recentRuns.length
      ? "已有调研运行，可进入对比审查"
      : "尚未发起外部资料搜集",
    status: recentRuns.length ? "ready" : "pending",
  },
  {
    key: "feasibility",
    icon: FileCheck2,
    title: "可行性结论",
    detail: reports.length
      ? `${reports.length} 份报告可作为决策输入`
      : "需要生成一份带引用的研究报告",
    status: reports.length ? "ready" : "pending",
  },
  {
    key: "signoff",
    icon: Users,
    title: "人工签署",
    detail: actionItems.length
      ? `${actionItems.length} 个后续行动已登记`
      : "发布前必须由负责人确认",
    status: "pending",
  },
]);

const comparisonDimensions = computed(() => [
  {
    title: "目标用户与场景",
    description: "谁会使用、在什么场景下使用，是否有明确痛点",
    status: form.objective.trim() ? "已定义范围" : "待填写",
    tone: form.objective.trim() ? "ready" : "pending",
  },
  {
    title: "替代方案与竞品",
    description: "市场同类项目、内部流程与人工方案的差异",
    status: recentRuns.length ? "可开始核验" : "待搜集资料",
    tone: recentRuns.length ? "ready" : "pending",
  },
  {
    title: "成本、周期与资源",
    description: "预算、人员、工具、依赖和关键里程碑",
    status: form.constraints.trim() ? "已记录约束" : "待补充约束",
    tone: form.constraints.trim() ? "ready" : "pending",
  },
  {
    title: "风险与反证",
    description: "哪些条件会让方案失效，是否存在相互冲突的来源",
    status: evaluationCases.length ? "已有评估用例" : "待建立反证清单",
    tone: evaluationCases.length ? "ready" : "pending",
  },
]);

const planSections = computed(() => [
  {
    title: "执行摘要",
    detail: "目标、推荐结论与决策请求",
    done: Boolean(form.objective.trim()),
  },
  {
    title: "背景与问题",
    detail: "事实、用户痛点与范围边界",
    done: Boolean(form.problem.trim()),
  },
  {
    title: "方案与市场对比",
    detail: "内部方案、竞品和替代路径",
    done: recentRuns.length > 0,
  },
  {
    title: "可行性与风险",
    detail: "技术、业务、成本和合规审查",
    done: reports.length > 0,
  },
  {
    title: "里程碑与行动项",
    detail: "负责人、截止时间和验收标准",
    done: actionItems.length > 0,
  },
  {
    title: "证据附件",
    detail: "引用、来源、版本和审查记录",
    done: indexedCount.value > 0,
  },
]);

async function loadDraft() {
  hydrating.value = true;
  try {
    const remote = await planningApi.detail(workspaceId.value, projectId.value);
    Object.assign(form, {
      objective: remote.objective || "",
      problem: remote.problem || "",
      successMetrics: remote.successMetrics || "",
      constraints: remote.constraints || "",
      owner: remote.owner || "",
      deadline: remote.deadline || "",
    });
    savedAt.value = remote.updatedAt || "";
    planLoadFailed.value = false;
  } catch (error) {
    Object.assign(form, {
      objective: "",
      problem: "",
      successMetrics: "",
      constraints: "",
      owner: "",
      deadline: "",
    });
    savedAt.value = "";
    planLoadFailed.value = true;
    notify(
      error instanceof Error
        ? `规划数据加载失败：${error.message}`
        : "规划数据加载失败，未使用本地数据",
    );
  }
  dirty.value = false;
  window.setTimeout(() => {
    hydrating.value = false;
  }, 0);
}

async function saveDraft() {
  if (saving.value) return;
  saving.value = true;
  try {
    const remote = await planningApi.save(workspaceId.value, projectId.value, {
      ...form,
      deadline: form.deadline || null,
    });
    savedAt.value = remote.updatedAt || "";
    planLoadFailed.value = false;
    dirty.value = false;
    notify("规划已保存到项目空间");
  } catch (error) {
    notify(
      error instanceof Error
        ? `规划未保存：${error.message}`
        : "规划未保存，数据库暂不可用",
    );
  } finally {
    saving.value = false;
  }
}

function openResearch() {
  notify("已打开 Agent 对话，请先明确要搜集的市场与竞品范围");
  router.push(routeTo("project-agent-chat"));
}

function openReview() {
  router.push(routeTo("project-review"));
}

watch(
  form,
  () => {
    if (!hydrating.value) dirty.value = true;
  },
  { deep: true },
);
onMounted(() => void loadDraft());
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / DECISION PLANNING"
    title="规划中枢"
    :subtitle="`把 ${projectName} 的资料、对比、可行性和行动项组织成一份可审查的计划。`"
  >
    <template #action>
      <button class="button button-secondary" type="button" @click="openReview">
        <ShieldCheck :size="16" />打开审查中心
      </button>
      <button
        class="button button-primary"
        type="button"
        :disabled="!dirty || saving || planLoadFailed"
        @click="saveDraft"
      >
        <Save :size="16" />{{
          saving
            ? "保存中"
            : dirty
              ? "保存规划草稿"
              : savedAt
                ? "已保存"
                : "尚未保存"
        }}
      </button>
    </template>
  </PageHeader>

  <section class="planning-hero panel">
    <div class="planning-hero-copy">
      <div class="planning-kicker">
        <ClipboardList :size="14" />DECISION READY WORKSPACE
      </div>
      <h2>从“想做什么”到“为什么现在可以做”</h2>
      <p>
        规划中枢将项目目标、内部资料、市场对比、可行性判断和人工签署放在同一条证据链上。
        没有来源的结论不会直接进入计划书。
      </p>
      <div class="planning-hero-meta">
        <span><LockKeyhole :size="13" />项目级草稿</span>
        <span><CheckCircle2 :size="13" />引用门禁已启用</span>
        <span v-if="savedAt">最近保存 {{ formatDateTime(savedAt, "—") }}</span>
      </div>
    </div>
    <div class="readiness-meter" aria-label="规划准备度">
      <div class="readiness-ring" :style="{ '--readiness': readiness }">
        <strong>{{ readiness }}</strong
        ><span>规划准备度</span>
      </div>
      <small>{{
        readiness === "100%" ? "已具备提交审查条件" : "补齐证据后再提交审查"
      }}</small>
    </div>
  </section>

  <section class="planning-steps panel" aria-label="规划流程">
    <div class="step-intro">
      <strong>规划链路</strong><span>每一步都留下输入、证据和责任人</span>
    </div>
    <div class="step-list">
      <div
        v-for="(step, index) in [
          '定义目标',
          '搜集证据',
          '市场对比',
          '可行性审查',
          '形成计划书',
        ]"
        :key="step"
        class="step-item"
        :class="{ active: index === 0, complete: readinessChecks[index] }"
      >
        <span class="step-number"
          ><Check v-if="readinessChecks[index]" :size="12" />{{
            readinessChecks[index] ? "" : index + 1
          }}</span
        >
        <span
          ><strong>{{ step }}</strong
          ><small>{{
            index === 0 ? "当前编辑" : index < 3 ? "等待输入" : "审查门禁"
          }}</small></span
        >
        <ArrowRight v-if="index < 4" :size="14" class="step-arrow" />
      </div>
    </div>
  </section>

  <div class="planning-metrics">
    <article class="planning-metric">
      <span class="metric-icon teal"><Target :size="16" /></span>
      <div>
        <strong>{{ form.objective.trim() ? "已定义" : "待补齐" }}</strong
        ><small>目标与范围</small>
      </div>
    </article>
    <article class="planning-metric">
      <span class="metric-icon violet"><Database :size="16" /></span>
      <div>
        <strong>{{ evidenceCoverage }}</strong
        ><small>资料证据覆盖</small>
      </div>
    </article>
    <article class="planning-metric">
      <span class="metric-icon amber"><Search :size="16" /></span>
      <div>
        <strong>{{
          recentRuns.length ? `${recentRuns.length} 次` : "待发起"
        }}</strong
        ><small>市场调研运行</small>
      </div>
    </article>
    <article class="planning-metric">
      <span class="metric-icon blue"><FileCheck2 :size="16" /></span>
      <div>
        <strong>{{ reports.length ? `${reports.length} 份` : "待生成" }}</strong
        ><small>可行性输入</small>
      </div>
    </article>
  </div>

  <div class="planning-layout">
    <section class="panel planning-brief-panel">
      <div class="panel-heading">
        <div>
          <h2>规划输入</h2>
          <p>先写清楚决策问题，再让 Agent 去搜集和验证资料</p>
        </div>
        <span class="draft-state" :class="{ dirty }">{{
          dirty ? "未保存" : savedAt ? "数据库草稿" : "尚未保存"
        }}</span>
      </div>
      <div class="planning-form">
        <label class="field field-wide"
          ><span>项目目标 <b>*</b></span
          ><textarea
            v-model="form.objective"
            rows="3"
            placeholder="例如：评估是否在 Q4 建设面向企业团队的项目规划能力，并形成可执行的首期方案。"
          />
        </label>
        <label class="field field-wide"
          ><span>背景问题与机会</span
          ><textarea
            v-model="form.problem"
            rows="3"
            placeholder="当前业务遇到什么问题？为什么现在需要做？哪些事实需要被验证？"
          />
        </label>
        <div class="form-two-columns">
          <label class="field"
            ><span>成功指标</span
            ><textarea
              v-model="form.successMetrics"
              rows="3"
              placeholder="例如：交付周期、采用率、成本上限、质量门槛"
            />
          </label>
          <label class="field"
            ><span>约束与假设</span
            ><textarea
              v-model="form.constraints"
              rows="3"
              placeholder="预算、人员、依赖、合规边界和必须成立的前提"
            />
          </label>
        </div>
        <div class="form-two-columns">
          <label class="field"
            ><span>项目负责人</span
            ><input
              v-model="form.owner"
              type="text"
              placeholder="填写负责人或责任团队"
          /></label>
          <label class="field"
            ><span>期望决策日期</span
            ><input v-model="form.deadline" type="date"
          /></label>
        </div>
      </div>
      <div class="planning-form-footer">
        <span
          ><LockKeyhole
            :size="13"
          />仅保存到项目空间，服务不可用时不会伪造已保存状态</span
        ><button
          class="button button-primary button-sm"
          type="button"
          :disabled="!dirty || saving || planLoadFailed"
          @click="saveDraft"
        >
          <Save :size="14" />保存
        </button>
      </div>
    </section>

    <section class="panel gate-panel">
      <div class="panel-heading">
        <div>
          <h2>审查门禁</h2>
          <p>发布计划书前必须逐项通过</p>
        </div>
        <button class="text-button" type="button" @click="openReview">
          查看规则 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="gate-summary">
        <strong
          >{{ reviewGates.filter((gate) => gate.status === "ready").length }}/{{
            reviewGates.length
          }}</strong
        ><span>项已满足进入审查的前置条件</span>
      </div>
      <div class="gate-list">
        <div v-for="gate in reviewGates" :key="gate.key" class="gate-row">
          <span class="gate-icon" :class="gate.status"
            ><component :is="gate.icon" :size="15"
          /></span>
          <span class="gate-copy"
            ><strong>{{ gate.title }}</strong
            ><small>{{ gate.detail }}</small></span
          >
          <CheckCircle2
            v-if="gate.status === 'ready'"
            :size="15"
            class="gate-ready"
          />
          <ArrowRight v-else :size="14" class="gate-arrow" />
        </div>
      </div>
      <button
        class="button button-secondary full-button"
        type="button"
        @click="openReview"
      >
        <ShieldCheck :size="15" />进入结构化审查
      </button>
    </section>
  </div>

  <div class="planning-lower-grid">
    <section class="panel comparison-panel">
      <div class="panel-heading">
        <div>
          <h2>方案与市场对比框架</h2>
          <p>先定义比较维度，再要求 Agent 为每个判断补充来源</p>
        </div>
        <button
          class="button button-secondary button-sm"
          type="button"
          @click="openResearch"
        >
          <Search :size="14" />发起对比研究
        </button>
      </div>
      <div class="comparison-list">
        <div
          v-for="item in comparisonDimensions"
          :key="item.title"
          class="comparison-row"
        >
          <span class="comparison-icon" :class="item.tone"
            ><GitCompare :size="15"
          /></span>
          <div>
            <strong>{{ item.title }}</strong
            ><small>{{ item.description }}</small>
          </div>
          <span class="comparison-status" :class="item.tone">{{
            item.status
          }}</span>
          <ArrowRight :size="14" class="comparison-arrow" />
        </div>
      </div>
      <div class="comparison-note">
        <ShieldCheck :size="14" /><span
          >对比结论必须区分“事实、推断、建议”，并保留来源版本与检索时间。</span
        >
      </div>
    </section>

    <section class="panel structure-panel">
      <div class="panel-heading">
        <div>
          <h2>标准计划书结构</h2>
          <p>完成后可生成 Markdown / PDF 版本</p>
        </div>
        <FileText :size="17" class="structure-heading-icon" />
      </div>
      <div class="structure-list">
        <div
          v-for="(section, index) in planSections"
          :key="section.title"
          class="structure-row"
        >
          <span class="structure-index">{{
            String(index + 1).padStart(2, "0")
          }}</span
          ><span
            ><strong>{{ section.title }}</strong
            ><small>{{ section.detail }}</small></span
          ><CheckCircle2
            v-if="section.done"
            :size="15"
            class="structure-done"
          /><span v-else class="structure-pending">待补</span>
        </div>
      </div>
      <button
        class="text-button structure-link"
        type="button"
        @click="router.push(routeTo('project-reports'))"
      >
        查看报告模板 <ArrowRight :size="14" />
      </button>
    </section>
  </div>
</template>

<style scoped>
.planning-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  min-height: 12rem;
  margin-bottom: 0.75rem;
  padding: 1.5rem 1.75rem;
  background: linear-gradient(
    115deg,
    color-mix(in oklab, var(--teal) 9%, var(--surface)),
    var(--surface)
  );
  border-color: color-mix(in oklab, var(--teal) 20%, var(--workspace-border));
}
.planning-hero-copy {
  min-width: 0;
  max-width: 48rem;
}
.planning-kicker {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 750;
  letter-spacing: 0.12em;
}
.planning-hero h2 {
  margin: 0.625rem 0 0;
  color: var(--workspace-text);
  font-size: 1.45rem;
  letter-spacing: -0.035em;
}
.planning-hero p {
  max-width: 42rem;
  margin: 0.625rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.8125rem;
  line-height: 1.7;
}
.planning-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.875rem;
  margin-top: 1rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.planning-hero-meta span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
}
.planning-hero-meta svg {
  color: var(--teal-dark);
}
.readiness-meter {
  display: grid;
  flex: 0 0 9.5rem;
  justify-items: center;
  gap: 0.5rem;
}
.readiness-ring {
  display: grid;
  width: 8rem;
  height: 8rem;
  place-content: center;
  justify-items: center;
  border-radius: 50%;
  background: conic-gradient(
    var(--teal) var(--readiness),
    color-mix(in oklab, var(--teal) 11%, var(--surface)) 0
  );
  position: relative;
}
.readiness-ring::after {
  position: absolute;
  inset: 0.625rem;
  border-radius: 50%;
  background: var(--surface);
  content: "";
}
.readiness-ring strong,
.readiness-ring span {
  position: relative;
  z-index: 1;
}
.readiness-ring strong {
  color: var(--workspace-text);
  font-size: 1.4rem;
  letter-spacing: -0.05em;
}
.readiness-ring span {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.readiness-meter > small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  text-align: center;
}
.planning-steps {
  display: flex;
  align-items: center;
  gap: 2rem;
  margin-bottom: 0.75rem;
  padding: 0.875rem 1.25rem;
}
.step-intro {
  display: grid;
  flex: 0 0 8.5rem;
  gap: 0.25rem;
}
.step-intro strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.step-intro span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.5;
}
.step-list {
  display: grid;
  min-width: 0;
  flex: 1;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}
.step-item {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 0.4375rem;
  padding-right: 1.25rem;
}
.step-number {
  display: grid;
  width: 1.5rem;
  height: 1.5rem;
  flex: 0 0 auto;
  place-items: center;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 50%;
  background: var(--surface-raised);
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.step-item.active .step-number,
.step-item.complete .step-number {
  border-color: var(--teal);
  background: color-mix(in oklab, var(--teal) 13%, var(--surface));
  color: var(--teal-dark);
}
.step-item > span:last-of-type {
  min-width: 0;
}
.step-item strong,
.step-item small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step-item strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.step-item small {
  margin-top: 0.1875rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.step-arrow {
  position: absolute;
  top: 0.375rem;
  right: 0.375rem;
  color: var(--workspace-border);
}
.planning-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.planning-metric {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  min-height: 4.25rem;
  padding: 0.75rem 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface);
}
.planning-metric > div {
  display: grid;
  gap: 0.25rem;
  min-width: 0;
}
.planning-metric strong {
  color: var(--workspace-text);
  font-size: 1.05rem;
  letter-spacing: -0.04em;
}
.planning-metric small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.metric-icon {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5625rem;
}
.metric-icon.teal {
  color: var(--teal-dark);
  background: #e3f7f3;
}
.metric-icon.violet {
  color: #6e62d6;
  background: #eeebff;
}
.metric-icon.amber {
  color: #b97914;
  background: #fff2da;
}
.metric-icon.blue {
  color: #4b86c8;
  background: #e8f2fd;
}
.planning-layout,
.planning-lower-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(20rem, 0.75fr);
  gap: 0.75rem;
}
.planning-layout {
  margin-bottom: 0.75rem;
}
.planning-brief-panel,
.gate-panel,
.comparison-panel,
.structure-panel {
  min-width: 0;
  overflow: hidden;
}
.draft-state {
  padding: 0.25rem 0.4375rem;
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.draft-state.dirty {
  background: #fff2da;
  color: #ad751c;
}
.planning-form {
  display: grid;
  gap: 0.75rem;
  padding: 0.125rem 1.25rem 1rem;
}
.form-two-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.field {
  display: grid;
  gap: 0.375rem;
  min-width: 0;
}
.field span {
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
}
.field span b {
  color: var(--red);
}
.field input,
.field textarea {
  width: 100%;
  box-sizing: border-box;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  padding: 0.625rem 0.6875rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.75rem;
  line-height: 1.55;
  outline: none;
  resize: vertical;
}
.field input {
  height: 2.25rem;
}
.field input::placeholder,
.field textarea::placeholder {
  color: var(--workspace-subtle);
}
.field input:focus,
.field textarea:focus {
  border-color: color-mix(in oklab, var(--teal) 58%, var(--workspace-border));
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 10%, transparent);
}
.planning-form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.planning-form-footer > span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
}
.planning-form-footer svg {
  color: var(--teal-dark);
}
.gate-summary {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.125rem 1.25rem 0.75rem;
}
.gate-summary strong {
  color: var(--workspace-text);
  font-size: 1.25rem;
  letter-spacing: -0.05em;
}
.gate-summary span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.gate-list {
  display: grid;
  padding: 0 1.25rem;
}
.gate-row {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  min-width: 0;
  padding: 0.6875rem 0;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.gate-icon {
  display: grid;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5rem;
}
.gate-icon.ready {
  background: #e3f7f3;
  color: var(--teal-dark);
}
.gate-icon.pending {
  background: #fff4df;
  color: #b37b20;
}
.gate-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.1875rem;
}
.gate-copy strong,
.gate-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gate-copy strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.gate-copy small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.gate-ready {
  color: var(--teal);
}
.gate-arrow {
  color: var(--workspace-subtle);
}
.gate-panel .full-button {
  width: calc(100% - 2.5rem);
  margin: 1rem 1.25rem 1.25rem;
}
.comparison-panel .panel-heading,
.structure-panel .panel-heading {
  align-items: center;
}
.comparison-list {
  display: grid;
  padding: 0 1.25rem;
}
.comparison-row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  min-width: 0;
  padding: 0.75rem 0;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.comparison-icon {
  display: grid;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5rem;
}
.comparison-icon.ready {
  color: var(--teal-dark);
  background: #e3f7f3;
}
.comparison-icon.pending {
  color: #b37b20;
  background: #fff4df;
}
.comparison-row > div {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.1875rem;
}
.comparison-row strong,
.comparison-row small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.comparison-row strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.comparison-row small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.comparison-status {
  padding: 0.25rem 0.4375rem;
  border-radius: 999px;
  font-size: 0.75rem;
  white-space: nowrap;
}
.comparison-status.ready {
  color: var(--teal-dark);
  background: #e3f7f3;
}
.comparison-status.pending {
  color: #a97620;
  background: #fff4df;
}
.comparison-arrow {
  color: var(--workspace-subtle);
}
.comparison-note {
  display: flex;
  align-items: flex-start;
  gap: 0.4375rem;
  margin: 0.5rem 1.25rem 1.125rem;
  padding: 0.625rem 0.6875rem;
  border-radius: 0.4375rem;
  background: color-mix(in oklab, var(--teal) 7%, var(--surface));
  color: var(--teal-dark);
  font-size: 0.75rem;
  line-height: 1.55;
}
.comparison-note svg {
  flex: 0 0 auto;
  margin-top: 0.0625rem;
}
.structure-heading-icon {
  color: var(--teal-dark);
}
.structure-list {
  display: grid;
  padding: 0 1.25rem;
}
.structure-row {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  padding: 0.6rem 0;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.structure-index {
  width: 1.25rem;
  flex: 0 0 auto;
  color: var(--workspace-subtle);
  font:
    700 0.75rem ui-monospace,
    monospace;
}
.structure-row > span:nth-child(2) {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.1875rem;
}
.structure-row strong,
.structure-row small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.structure-row strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.structure-row small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.structure-done {
  color: var(--teal);
}
.structure-pending {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.structure-link {
  margin: 0.5rem 1.25rem 1.125rem;
}
.button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}
@media (max-width: 68.75rem) {
  .planning-steps {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.875rem;
  }
  .step-intro {
    flex-basis: auto;
  }
  .planning-layout,
  .planning-lower-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 47.5rem) {
  .planning-hero {
    align-items: flex-start;
    flex-direction: column;
    gap: 1.25rem;
    padding: 1.25rem;
  }
  .readiness-meter {
    align-self: center;
  }
  .step-list {
    width: 100%;
    overflow-x: auto;
    grid-template-columns: repeat(5, minmax(8rem, 1fr));
    padding-bottom: 0.25rem;
  }
  .planning-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .form-two-columns {
    grid-template-columns: 1fr;
  }
  .planning-brief-panel .panel-heading,
  .comparison-panel .panel-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
@media (max-width: 30rem) {
  .planning-metrics {
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }
  .planning-metric {
    padding-inline: 0.625rem;
  }
  .planning-metric strong {
    font-size: 0.9rem;
  }
  .comparison-status {
    display: none;
  }
}
</style>
