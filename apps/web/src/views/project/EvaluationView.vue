<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  Database,
  LoaderCircle,
  MessageCircle,
  Play,
  Plus,
  RefreshCw,
  Search,
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/composables/useWorkspace";
import { evaluationApi } from "@/api/evaluation";
import { getApiErrorMessage } from "@/api/core";
import type { EvaluationResult, EvaluationRun } from "@/api/types";
import { formatDateTime } from "@/lib/utils";

const { assets, notify, workspaceId, projectId, router, routeTo } =
  useWorkspace();
const route = useRoute();
const evaluationCases = ref<ReturnType<typeof mapEvaluationCase>[]>([]);
const selectedCaseId = ref("");
const filter = ref("all");
const search = ref("");
const loading = ref(false);
const loadError = ref("");
const saving = ref(false);
const saveError = ref("");
const reviewing = ref(false);
const dialogOpen = ref(false);
const editingId = ref<string | null>(null);
const running = ref(false);
const runningCaseId = ref("");
const stopRequested = ref(false);
const runErrors = reactive<Record<string, string>>({});
const batch = ref<{
  total: number;
  completed: number;
  passed: number;
  failed: number;
  errors: number;
  stopped: boolean;
} | null>(null);
let scopeVersion = 0;
let loadVersion = 0;
const form = reactive({
  query: "",
  expectedAnswer: "",
  expectedAsset: "",
  expectedChunkIds: "",
  requiredFacts: "",
  forbiddenFacts: "",
});
const indexedAssets = computed(() =>
  assets.filter((asset) => asset.status === "indexed"),
);
const selectedCase = computed(() =>
  evaluationCases.value.find((item) => item.id === selectedCaseId.value),
);
const runnableCases = computed(() => evaluationCases.value.filter(canRun));
const evaluatedCases = computed(() =>
  evaluationCases.value.filter((item) => item.evaluationResult),
);
const failedCases = computed(() =>
  evaluatedCases.value.filter(
    (item) => item.evaluationResult?.status === "FAILED",
  ),
);
const averageRecall = computed(() => {
  const values = evaluatedCases.value
    .map((item) => item.evaluationResult?.recall)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    );
  return values.length
    ? `${(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)}%`
    : "尚未运行";
});
const filters = [
  { value: "all", label: "全部" },
  { value: "ready", label: "待运行" },
  { value: "failed", label: "未通过" },
  { value: "unannotated", label: "待标注" },
];
const filteredCases = computed(() =>
  evaluationCases.value.filter((item) => {
    const matchesFilter =
      filter.value === "all" ||
      (filter.value === "ready" && canRun(item) && !item.evaluationResult) ||
      (filter.value === "failed" &&
        item.evaluationResult?.status === "FAILED") ||
      (filter.value === "unannotated" && !canRun(item));
    return (
      matchesFilter &&
      `${item.query} ${item.expectedAsset}`
        .toLowerCase()
        .includes(search.value.trim().toLowerCase())
    );
  }),
);
const remainingUnannotated = computed(
  () => evaluationCases.value.length - runnableCases.value.length,
);

function parseList(value: unknown): string[] {
  if (typeof value === "string") {
    try {
      return parseList(JSON.parse(value));
    } catch {
      return [];
    }
  }
  return Array.isArray(value)
    ? value.filter(
        (entry): entry is string => typeof entry === "string" && !!entry.trim(),
      )
    : [];
}
function parseResult(
  value: EvaluationRun["evaluationResult"],
): EvaluationResult | null {
  if (typeof value === "string") {
    try {
      return parseResult(JSON.parse(value));
    } catch {
      return null;
    }
  }
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
}
function mapEvaluationCase(item: EvaluationRun) {
  return {
    id: String(item.id),
    projectId: item.projectId,
    query: String(item.query || ""),
    expectedAnswer: String(item.expectedAnswer || ""),
    expectedAsset: String(item.expectedAsset || ""),
    expectedChunkIds: parseList(item.expectedChunkIds),
    requiredFacts: parseList(item.requiredFacts),
    forbiddenFacts: parseList(item.forbiddenFacts),
    evaluationResult: parseResult(item.evaluationResult),
    evaluatedAt: item.evaluatedAt,
    status: String(item.status || "REVIEW").toLowerCase(),
  };
}
function canRun(item: ReturnType<typeof mapEvaluationCase> | undefined) {
  return (
    !!item &&
    !!(
      item.expectedAsset.trim() ||
      item.expectedChunkIds.length ||
      item.requiredFacts.length
    )
  );
}
function caseLabel(item: ReturnType<typeof mapEvaluationCase>) {
  if (!canRun(item)) return "待标注";
  if (runErrors[item.id]) return "运行出错";
  if (!item.evaluationResult) return "待运行";
  return item.evaluationResult.status === "PASSED" ? "检索通过" : "检索未通过";
}
function splitLines(value: string) {
  return [
    ...new Set(
      value
        .split(/\r?\n/)
        .map((entry) => entry.trim())
        .filter(Boolean),
    ),
  ];
}
function openCreate(assetName = "") {
  editingId.value = null;
  saveError.value = "";
  Object.assign(form, {
    query: assetName ? `《${assetName}》主要说明了什么？` : "",
    expectedAnswer: "",
    expectedAsset: assetName,
    expectedChunkIds: "",
    requiredFacts: "",
    forbiddenFacts: "",
  });
  dialogOpen.value = true;
}
function openEdit() {
  const item = selectedCase.value;
  if (!item) return;
  editingId.value = item.id;
  saveError.value = "";
  Object.assign(form, {
    ...item,
    expectedChunkIds: item.expectedChunkIds.join("\n"),
    requiredFacts: item.requiredFacts.join("\n"),
    forbiddenFacts: item.forbiddenFacts.join("\n"),
  });
  dialogOpen.value = true;
}
async function saveCase() {
  if (!form.query.trim() || saving.value || running.value) return;
  const version = scopeVersion;
  const id = editingId.value;
  const payload = {
    projectId: projectId.value,
    query: form.query.trim(),
    expectedAnswer: form.expectedAnswer.trim(),
    expectedAsset: form.expectedAsset.trim(),
    expectedChunkIds: splitLines(form.expectedChunkIds),
    requiredFacts: splitLines(form.requiredFacts),
    forbiddenFacts: splitLines(form.forbiddenFacts),
  };
  saving.value = true;
  saveError.value = "";
  try {
    const response = id
      ? await evaluationApi.update(workspaceId.value, id, payload)
      : await evaluationApi.create(workspaceId.value, payload);
    if (version !== scopeVersion) return;
    const saved = mapEvaluationCase(response);
    const index = evaluationCases.value.findIndex(
      (item) => item.id === saved.id,
    );
    if (index >= 0) evaluationCases.value.splice(index, 1, saved);
    else evaluationCases.value.unshift(saved);
    delete runErrors[saved.id];
    selectedCaseId.value = saved.id;
    filter.value = "all";
    search.value = "";
    dialogOpen.value = false;
    notify(
      id ? "用例标注已更新，请重新运行评估" : "用例已保存，可开始检索评估",
    );
  } catch (error) {
    if (version === scopeVersion)
      saveError.value = getApiErrorMessage(error, "保存用例失败，请重试");
  } finally {
    if (version === scopeVersion) saving.value = false;
  }
}
async function loadCases() {
  const version = ++loadVersion;
  const scope = scopeVersion;
  const currentProject = projectId.value;
  loading.value = true;
  loadError.value = "";
  try {
    const remote = await evaluationApi.list(workspaceId.value);
    if (version !== loadVersion || scope !== scopeVersion) return;
    evaluationCases.value = remote
      .filter((item) => Number(item.projectId) === currentProject)
      .map(mapEvaluationCase);
    if (!evaluationCases.value.some((item) => item.id === selectedCaseId.value))
      selectedCaseId.value = evaluationCases.value[0]?.id || "";
  } catch (error) {
    if (version === loadVersion && scope === scopeVersion)
      loadError.value = getApiErrorMessage(error, "读取用例失败，请重试");
  } finally {
    if (version === loadVersion && scope === scopeVersion)
      loading.value = false;
  }
}
async function runCases(items: ReturnType<typeof mapEvaluationCase>[]) {
  const targets = items.filter(canRun);
  if (
    running.value ||
    saving.value ||
    reviewing.value ||
    loading.value ||
    !targets.length
  )
    return;
  const version = scopeVersion;
  const currentWorkspace = workspaceId.value;
  running.value = true;
  stopRequested.value = false;
  batch.value = {
    total: targets.length,
    completed: 0,
    passed: 0,
    failed: 0,
    errors: 0,
    stopped: false,
  };
  try {
    for (const item of targets) {
      if (version !== scopeVersion || stopRequested.value) break;
      runningCaseId.value = item.id;
      delete runErrors[item.id];
      try {
        const response = await evaluationApi.run(currentWorkspace, item.id);
        if (version !== scopeVersion) return;
        Object.assign(item, mapEvaluationCase(response));
        if (item.evaluationResult?.status === "PASSED") batch.value!.passed++;
        else batch.value!.failed++;
      } catch (error) {
        if (version !== scopeVersion) return;
        runErrors[item.id] = getApiErrorMessage(
          error,
          "检索评估请求失败，请重试",
        );
        batch.value!.errors++;
      }
      batch.value!.completed++;
    }
    if (version !== scopeVersion) return;
    batch.value!.stopped =
      stopRequested.value && batch.value!.completed < targets.length;
    notify(
      batch.value!.stopped
        ? "已停止后续评估，当前结果已保留"
        : "检索评估结束，结果已保存",
    );
  } finally {
    if (version === scopeVersion) {
      running.value = false;
      runningCaseId.value = "";
    }
  }
}
function openTool(name: string) {
  const item = selectedCase.value;
  if (!item) return;
  void router.push({
    ...routeTo(name),
    query: {
      [name === "project-agent-chat" ? "prompt" : "query"]: item.query,
      evaluationCaseId: item.id,
    },
  });
}
async function markReviewed(status: "PASSED" | "FAILED" | "REVIEW") {
  const item = selectedCase.value;
  if (!item || reviewing.value || running.value) return;
  const version = scopeVersion;
  reviewing.value = true;
  try {
    const response = await evaluationApi.update(workspaceId.value, item.id, {
      status,
    });
    if (version === scopeVersion) {
      item.status = String(response.status).toLowerCase();
      notify("人工核验状态已保存");
    }
  } catch (error) {
    if (version === scopeVersion)
      notify(getApiErrorMessage(error, "更新核验状态失败"));
  } finally {
    if (version === scopeVersion) reviewing.value = false;
  }
}
function createAction() {
  const item = selectedCase.value;
  if (!item) return;
  const result = item.evaluationResult;
  const details = [
    `评估问题：${item.query}`,
    item.expectedAnswer && `验收标准：${item.expectedAnswer}`,
    item.expectedAsset && `目标资料：${item.expectedAsset}`,
    result?.missingChunkIds?.length &&
      `未命中片段：${result.missingChunkIds.join("、")}`,
    result?.expectedAssetFound === false && `未命中资料：${item.expectedAsset}`,
    result?.missingRequiredFacts?.length &&
      `缺失事实：${result.missingRequiredFacts.join("、")}`,
    result?.matchedForbiddenFacts?.length &&
      `命中禁止事实：${result.matchedForbiddenFacts.join("、")}`,
    `检索评估：Recall@5 ${result?.recall ?? "—"}%`,
  ]
    .filter(Boolean)
    .join("\n\n");
  void router.push({
    ...routeTo("project-action-items"),
    query: {
      actionTitle: `修复检索评估：${item.query.slice(0, 72)}`,
      actionDescription: details,
    },
  });
}
watch(
  [workspaceId, projectId],
  () => {
    scopeVersion++;
    evaluationCases.value = [];
    selectedCaseId.value =
      typeof route.query.caseId === "string" ? route.query.caseId : "";
    for (const key of Object.keys(runErrors)) delete runErrors[key];
    running.value = false;
    saving.value = false;
    reviewing.value = false;
    dialogOpen.value = false;
    batch.value = null;
    filter.value = "all";
    search.value = "";
    void loadCases();
  },
  { immediate: true },
);
watch(
  () => route.query.caseId,
  (id) => {
    if (typeof id === "string") selectedCaseId.value = id;
  },
);
onBeforeUnmount(() => {
  scopeVersion++;
});
</script>

<template>
  <PageHeader
    eyebrow="质量工具"
    title="检索评估"
    subtitle="把常问的问题保存为用例，检查知识库能否稳定找到正确资料。"
  >
    <template #action
      ><Button
        type="button"
        :disabled="loading || running || saving"
        @click="openCreate()"
        ><Plus data-icon="inline-start" />新建用例</Button
      ></template
    >
  </PageHeader>

  <section class="evaluation-workbench" aria-label="知识库检索评估">
    <section class="evaluation-intro">
      <div>
        <Badge variant="secondary">按需使用 · 质量工具</Badge>
        <h2>先找到对的资料，再验证回答</h2>
        <p>
          自动检查前 5
          条检索结果中的资料和事实命中情况。更新知识库后重新运行，即可发现检索退化。
        </p>
      </div>
      <ol class="evaluation-steps">
        <li><span>1</span>选择资料、定义问题</li>
        <li><span>2</span>运行检索评估</li>
        <li><span>3</span>定位缺失、跟进修复</li>
      </ol>
    </section>

    <Alert v-if="loadError" variant="destructive"
      ><CircleAlert /><AlertTitle>用例读取失败</AlertTitle
      ><AlertDescription
        >{{ loadError }}
        <Button type="button" variant="outline" size="sm" @click="loadCases"
          >重新加载</Button
        ></AlertDescription
      ></Alert
    >
    <div v-if="loading" class="evaluation-loading" role="status">
      <LoaderCircle class="is-spinning" :size="18" />正在加载项目用例…
    </div>

    <template v-else-if="!loadError">
      <dl class="evaluation-summary" aria-label="当前评估集概况">
        <div>
          <dt>可运行用例</dt>
          <dd>
            {{ runnableCases.length
            }}<small>/ {{ evaluationCases.length }}</small>
          </dd>
        </div>
        <div>
          <dt>已运行用例</dt>
          <dd>{{ evaluatedCases.length }}</dd>
        </div>
        <div>
          <dt>平均 Recall@5</dt>
          <dd>{{ averageRecall }}</dd>
        </div>
        <div>
          <dt>检索未通过</dt>
          <dd>{{ failedCases.length }}</dd>
        </div>
      </dl>

      <Card v-if="!evaluationCases.length" class="evaluation-start">
        <CardHeader
          ><CardTitle role="heading" aria-level="2"
            >建立第一条有效用例</CardTitle
          ><CardDescription
            >选一份已索引资料，用真实业务问题和预期命中内容建立可重复运行的检查。</CardDescription
          ></CardHeader
        >
        <CardContent>
          <template v-if="indexedAssets.length"
            ><p>
              当前有
              {{ indexedAssets.length }} 份已索引资料，可从下面的资料开始：
            </p>
            <div class="asset-starters">
              <Button
                v-for="asset in indexedAssets.slice(0, 4)"
                :key="asset.id"
                type="button"
                variant="outline"
                @click="openCreate(asset.name)"
                ><Database data-icon="inline-start" /><span>{{
                  asset.name
                }}</span
                ><Plus data-icon="inline-end"
              /></Button>
            </div>
            <p class="evaluation-note">
              资料定位问题仅用于建立基础检查；请改成团队实际会问的问题，并补充应命中的原文事实。
            </p></template
          >
          <template v-else
            ><p>
              当前项目还没有已索引资料。先到知识库添加并完成索引，再建立自动检索用例。
            </p>
            <Button
              type="button"
              variant="outline"
              @click="router.push(routeTo('project-assets'))"
              ><Database data-icon="inline-start" />前往知识库</Button
            ></template
          >
        </CardContent>
        <CardFooter
          ><Button type="button" variant="outline" @click="openCreate()"
            ><Plus data-icon="inline-start" />手动建立用例</Button
          ></CardFooter
        >
      </Card>

      <section v-else class="evaluation-cases" aria-label="评估用例与结果">
        <div class="evaluation-toolbar">
          <div>
            <h2>评估用例</h2>
            <p>自动评估仅检查检索，完整回答可带入 Agent 人工核验。</p>
          </div>
          <div class="evaluation-buttons">
            <Button
              type="button"
              variant="outline"
              size="sm"
              :disabled="running || saving || reviewing"
              @click="loadCases"
              ><RefreshCw data-icon="inline-start" />刷新</Button
            ><Button
              type="button"
              :disabled="
                running || saving || reviewing || !runnableCases.length
              "
              @click="runCases(runnableCases)"
              ><Play data-icon="inline-start" />运行全部
              {{ runnableCases.length }} 条</Button
            >
          </div>
        </div>
        <p v-if="remainingUnannotated" class="evaluation-note">
          {{ remainingUnannotated }}
          条用例尚未指定资料、片段或必需事实，批量运行时会跳过。选择用例后补充标注即可。
        </p>
        <Alert
          v-if="batch"
          :variant="batch.errors ? 'destructive' : 'default'"
          aria-live="polite"
          ><LoaderCircle v-if="running" class="is-spinning" /><CheckCircle2
            v-else
          /><AlertTitle
            >{{
              running
                ? "检索评估进行中"
                : batch.stopped
                  ? "已停止后续评估"
                  : "本次评估完成"
            }}
            · {{ batch.completed }}/{{ batch.total }}</AlertTitle
          ><AlertDescription
            >通过 {{ batch.passed }} · 未通过 {{ batch.failed }} · 请求出错
            {{ batch.errors
            }}<Button
              v-if="running && batch.total > 1"
              type="button"
              variant="outline"
              size="sm"
              :disabled="stopRequested"
              @click="stopRequested = true"
              >{{ stopRequested ? "本条完成后停止" : "停止后续用例" }}</Button
            ></AlertDescription
          ></Alert
        >

        <div class="evaluation-columns">
          <div class="evaluation-case-list">
            <Input
              v-model="search"
              aria-label="搜索评估用例"
              placeholder="搜索问题或目标资料"
            />
            <div class="evaluation-filters" aria-label="用例筛选">
              <Button
                v-for="option in filters"
                :key="option.value"
                type="button"
                size="sm"
                :variant="filter === option.value ? 'secondary' : 'ghost'"
                :aria-pressed="filter === option.value"
                @click="filter = option.value"
                >{{ option.label }}</Button
              >
            </div>
            <button
              v-for="item in filteredCases"
              :key="item.id"
              type="button"
              class="evaluation-case-row"
              :class="{ selected: item.id === selectedCaseId }"
              :aria-pressed="item.id === selectedCaseId"
              @click="selectedCaseId = item.id"
            >
              <strong>{{ item.query }}</strong
              ><small>{{
                item.expectedAsset ||
                (item.requiredFacts.length
                  ? `${item.requiredFacts.length} 项必需事实`
                  : "尚未指定检索目标")
              }}</small
              ><span
                ><Badge
                  :variant="
                    runErrors[item.id] ||
                    item.evaluationResult?.status === 'FAILED'
                      ? 'destructive'
                      : 'secondary'
                  "
                  >{{
                    runningCaseId === item.id ? "运行中" : caseLabel(item)
                  }}</Badge
                ><span v-if="item.evaluationResult"
                  >{{ item.evaluationResult.recall ?? "—" }}%</span
                ></span
              >
            </button>
            <p v-if="!filteredCases.length" class="evaluation-note">
              没有符合筛选条件的用例。<Button
                type="button"
                variant="link"
                size="sm"
                @click="
                  filter = 'all';
                  search = '';
                "
                >清除筛选</Button
              >
            </p>
          </div>

          <Card v-if="selectedCase" class="evaluation-detail">
            <CardHeader
              ><CardDescription>用例 #{{ selectedCase.id }}</CardDescription
              ><CardTitle role="heading" aria-level="2">{{
                selectedCase.query
              }}</CardTitle>
              <div class="evaluation-buttons">
                <Button
                  type="button"
                  :disabled="
                    running || saving || reviewing || !canRun(selectedCase)
                  "
                  @click="runCases([selectedCase])"
                  ><LoaderCircle
                    v-if="runningCaseId === selectedCase.id"
                    data-icon="inline-start"
                    class="is-spinning"
                  /><Play v-else data-icon="inline-start" />{{
                    runningCaseId === selectedCase.id ? "评估中…" : "运行此用例"
                  }}</Button
                ><Button
                  type="button"
                  variant="outline"
                  :disabled="running || saving || reviewing"
                  @click="openEdit"
                  >编辑标注</Button
                >
              </div></CardHeader
            >
            <CardContent class="evaluation-detail-content">
              <Alert v-if="runErrors[selectedCase.id]" variant="destructive"
                ><CircleAlert /><AlertTitle>本次请求未完成</AlertTitle
                ><AlertDescription
                  >{{ runErrors[selectedCase.id] }}
                  <p>
                    已有结果不会被本次请求错误替换，可以重新运行。
                  </p></AlertDescription
                ></Alert
              >
              <Alert v-if="!canRun(selectedCase)"
                ><ClipboardCheck /><AlertTitle>先补充检索目标</AlertTitle
                ><AlertDescription
                  >点击“编辑标注”，选择目标资料，或填写目标片段、必需事实中的任意一项。只有问题和验收标准时，无法自动计算检索命中。</AlertDescription
                ></Alert
              >
              <dl class="evaluation-targets">
                <div>
                  <dt>目标资料</dt>
                  <dd>{{ selectedCase.expectedAsset || "未指定" }}</dd>
                </div>
                <div v-if="selectedCase.expectedChunkIds.length">
                  <dt>目标片段</dt>
                  <dd>{{ selectedCase.expectedChunkIds.join("、") }}</dd>
                </div>
                <div v-if="selectedCase.requiredFacts.length">
                  <dt>必需事实</dt>
                  <dd>
                    <ul>
                      <li
                        v-for="fact in selectedCase.requiredFacts"
                        :key="fact"
                      >
                        {{ fact }}
                      </li>
                    </ul>
                  </dd>
                </div>
                <div v-if="selectedCase.forbiddenFacts.length">
                  <dt>禁止事实</dt>
                  <dd>
                    <ul>
                      <li
                        v-for="fact in selectedCase.forbiddenFacts"
                        :key="fact"
                      >
                        {{ fact }}
                      </li>
                    </ul>
                  </dd>
                </div>
              </dl>
              <section
                v-if="selectedCase.evaluationResult"
                class="evaluation-result"
                aria-label="最近一次检索评估结果"
              >
                <div class="evaluation-result-heading">
                  <h3>最近一次检索结果</h3>
                  <Badge
                    :variant="
                      selectedCase.evaluationResult.status === 'PASSED'
                        ? 'secondary'
                        : 'destructive'
                    "
                    >{{
                      selectedCase.evaluationResult.status === "PASSED"
                        ? "通过"
                        : "未通过"
                    }}</Badge
                  >
                </div>
                <p class="evaluation-result-score">
                  {{ selectedCase.evaluationResult.recall ?? "—" }}%<span
                    >Recall@{{ selectedCase.evaluationResult.topK || 5 }} · 命中
                    {{ selectedCase.evaluationResult.matchedCount ?? 0 }}/{{
                      selectedCase.evaluationResult.targetCount ?? 0
                    }}
                    项目标</span
                  >
                </p>
                <p class="evaluation-note">
                  {{ formatDateTime(selectedCase.evaluatedAt, "时间未记录") }} ·
                  返回
                  {{ selectedCase.evaluationResult.retrievedCount ?? 0 }}
                  条检索结果
                </p>
                <ul class="evaluation-result-issues">
                  <li
                    v-if="
                      selectedCase.evaluationResult.expectedAssetFound ===
                        false && selectedCase.expectedAsset
                    "
                  >
                    未命中目标资料：{{ selectedCase.expectedAsset }}
                  </li>
                  <li
                    v-for="id in selectedCase.evaluationResult
                      .missingChunkIds || []"
                    :key="id"
                  >
                    未命中片段：{{ id }}
                  </li>
                  <li
                    v-for="fact in selectedCase.evaluationResult
                      .missingRequiredFacts || []"
                    :key="fact"
                  >
                    缺失事实：{{ fact }}
                  </li>
                  <li
                    v-for="fact in selectedCase.evaluationResult
                      .matchedForbiddenFacts || []"
                    :key="fact"
                  >
                    命中禁止事实：{{ fact }}
                  </li>
                </ul>
                <details
                  v-if="
                    selectedCase.evaluationResult.retrievedAssets?.length ||
                    selectedCase.evaluationResult.retrievedChunkIds?.length
                  "
                >
                  <summary>实际检索到了什么</summary>
                  <p
                    v-if="selectedCase.evaluationResult.retrievedAssets?.length"
                  >
                    资料：{{
                      selectedCase.evaluationResult.retrievedAssets.join("、")
                    }}
                  </p>
                  <p
                    v-if="
                      selectedCase.evaluationResult.retrievedChunkIds?.length
                    "
                  >
                    片段：{{
                      selectedCase.evaluationResult.retrievedChunkIds.join("、")
                    }}
                  </p>
                </details>
              </section>
              <p v-else-if="canRun(selectedCase)" class="evaluation-note">
                此用例尚未运行。点击“运行此用例”查看真实命中情况。
              </p>
              <div class="evaluation-buttons">
                <Button
                  type="button"
                  variant="outline"
                  @click="openTool('project-playground')"
                  ><Search data-icon="inline-start" />打开检索调试</Button
                ><Button
                  v-if="selectedCase.evaluationResult?.status === 'FAILED'"
                  type="button"
                  variant="outline"
                  @click="createAction"
                  ><ArrowRight data-icon="inline-start" />转为修复行动项</Button
                >
              </div>
              <details class="evaluation-manual">
                <summary>人工核验完整回答（可选）</summary>
                <p>
                  {{
                    selectedCase.expectedAnswer ||
                    "尚未填写验收标准。可在编辑标注中补充应包含的结论和引用要求。"
                  }}
                </p>
                <p class="evaluation-note">
                  自动检索通过不等于回答正确。带入 Agent
                  查看回答后，在这里记录人工结论。用例状态由自动评估或人工确认更新，人工确认不会重新计算
                  Recall@5。
                </p>
                <p>
                  用例记录状态：{{
                    { passed: "通过", failed: "未通过", review: "待复核" }[
                      selectedCase.status as "passed" | "failed" | "review"
                    ] || selectedCase.status
                  }}
                </p>
                <div class="evaluation-buttons">
                  <Button
                    type="button"
                    variant="outline"
                    @click="openTool('project-agent-chat')"
                    ><MessageCircle data-icon="inline-start" />带入 Agent
                    验证</Button
                  ><Button
                    type="button"
                    variant="outline"
                    :disabled="running || reviewing"
                    @click="markReviewed('PASSED')"
                    >标记通过</Button
                  ><Button
                    type="button"
                    variant="outline"
                    :disabled="running || reviewing"
                    @click="markReviewed('FAILED')"
                    >标记未通过</Button
                  ><Button
                    type="button"
                    variant="ghost"
                    :disabled="running || reviewing"
                    @click="markReviewed('REVIEW')"
                    >待复核</Button
                  >
                </div>
              </details>
            </CardContent>
            <CardFooter
              ><p class="evaluation-note">
                评估范围：前 5
                条混合检索结果，关闭重排序。引用准确率、答案质量和结构化输出需另行核验。
              </p></CardFooter
            >
          </Card>
        </div>
      </section>
    </template>
  </section>

  <Dialog v-model:open="dialogOpen">
    <DialogContent class="evaluation-case-dialog">
      <DialogHeader
        ><DialogTitle>{{
          editingId ? "编辑评估用例" : "新建评估用例"
        }}</DialogTitle
        ><DialogDescription
          >填写真实业务问题，并选择预期应命中的资料。保存后运行，查看实际结果。</DialogDescription
        ></DialogHeader
      >
      <form
        id="evaluation-case-form"
        class="evaluation-case-form"
        @submit.prevent="saveCase"
      >
        <FieldGroup>
          <Field
            ><FieldLabel for="evaluation-query">测试问题</FieldLabel
            ><textarea
              id="evaluation-query"
              v-model="form.query"
              rows="2"
              required
              placeholder="例如：国内出差的住宿报销上限是多少？"
            />
          </Field>
          <Field
            ><FieldLabel for="evaluation-asset">目标资料</FieldLabel
            ><Input
              id="evaluation-asset"
              v-model="form.expectedAsset"
              list="evaluation-assets"
              placeholder="选择项目资料，或输入与知识库一致的资料名"
            /><datalist id="evaluation-assets">
              <option
                v-for="asset in indexedAssets"
                :key="asset.id"
                :value="asset.name"
              /></datalist
            ><FieldDescription
              >只填写目标资料即可运行基础命中检查；补充必需事实后检查会更具体。</FieldDescription
            ></Field
          >
          <Field
            ><FieldLabel for="evaluation-required"
              >必需事实（可选，每行一项）</FieldLabel
            ><textarea
              id="evaluation-required"
              v-model="form.requiredFacts"
              rows="2"
              placeholder="从资料中复制应检出的原文，例如：每晚不超过 800 元"
            /><FieldDescription
              >逐项匹配检索片段中的文字，建议使用原文短句。</FieldDescription
            ></Field
          >
          <details class="evaluation-advanced">
            <summary>更多标注与人工验收标准</summary>
            <FieldGroup
              ><Field
                ><FieldLabel for="evaluation-chunks"
                  >目标片段 ID（每行一项）</FieldLabel
                ><textarea
                  id="evaluation-chunks"
                  v-model="form.expectedChunkIds"
                  rows="2"
                  placeholder="可从检索调试或知识库片段详情中获取"
                /></Field
              ><Field
                ><FieldLabel for="evaluation-forbidden"
                  >禁止事实（每行一项）</FieldLabel
                ><textarea
                  id="evaluation-forbidden"
                  v-model="form.forbiddenFacts"
                  rows="2"
                  placeholder="检索结果不应包含的过期或错误原文"
                /></Field
              ><Field
                ><FieldLabel for="evaluation-expected"
                  >完整回答的人工验收标准</FieldLabel
                ><textarea
                  id="evaluation-expected"
                  v-model="form.expectedAnswer"
                  rows="2"
                  placeholder="例如：给出住宿上限，说明适用条件并引用制度原文。"
                /></Field
            ></FieldGroup>
          </details>
        </FieldGroup>
        <Alert v-if="saveError" variant="destructive"
          ><CircleAlert /><AlertTitle>保存失败</AlertTitle
          ><AlertDescription>{{ saveError }}</AlertDescription></Alert
        >
      </form>
      <DialogFooter
        ><Button
          type="button"
          variant="outline"
          :disabled="saving"
          @click="dialogOpen = false"
          >取消</Button
        ><Button
          type="submit"
          form="evaluation-case-form"
          :disabled="!form.query.trim() || saving || running"
          ><LoaderCircle
            v-if="saving"
            data-icon="inline-start"
            class="is-spinning"
          />{{ saving ? "保存中…" : "保存用例" }}</Button
        ></DialogFooter
      >
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.evaluation-workbench {
  --card: var(--surface);
  --card-foreground: var(--workspace-text);
  --muted-foreground: var(--workspace-muted);
  display: grid;
  grid-auto-rows: max-content;
  flex: 1 1 auto;
  align-content: start;
  gap: 1.25rem;
  padding-bottom: 1rem;
}
.evaluation-intro {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  padding: 0.25rem 0;
}
.evaluation-intro h2 {
  margin: 0.625rem 0 0.375rem;
  color: var(--workspace-text);
  font-size: 1.25rem;
  font-weight: 650;
}
.evaluation-intro p,
.evaluation-toolbar p,
.evaluation-note {
  margin: 0.375rem 0;
  color: var(--workspace-muted);
  font-size: 0.8125rem;
  line-height: 1.7;
}
.evaluation-steps {
  display: grid;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--workspace-muted);
  font-size: 0.8125rem;
}
.evaluation-steps li {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}
.evaluation-steps li > span {
  display: grid;
  width: 1.375rem;
  height: 1.375rem;
  place-items: center;
  border: 1px solid var(--workspace-border);
  border-radius: 50%;
  color: var(--teal-dark);
  font-size: 0.75rem;
}
.evaluation-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  margin: 0;
  border: 1px solid var(--workspace-border);
  border-radius: 0.75rem;
  overflow: hidden;
  background: var(--workspace-border);
}
.evaluation-summary > div {
  padding: 1rem 1.25rem;
  background: var(--surface);
}
.evaluation-summary dt {
  color: var(--workspace-muted);
  font-size: 0.8125rem;
}
.evaluation-summary dd {
  margin: 0.5rem 0 0;
  color: var(--workspace-text);
  font-size: 1.375rem;
  font-weight: 650;
}
.evaluation-summary small {
  margin-left: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.8125rem;
  font-weight: 400;
}
.asset-starters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.625rem;
  margin: 1rem 0;
}
.asset-starters button {
  max-width: 100%;
}
.asset-starters button > span {
  max-width: 24rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evaluation-toolbar,
.evaluation-result-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}
.evaluation-toolbar h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 1rem;
  font-weight: 650;
}
.evaluation-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.evaluation-cases {
  display: grid;
  gap: 0.875rem;
}
.evaluation-columns {
  display: grid;
  grid-template-columns: minmax(15rem, 0.8fr) minmax(0, 1.6fr);
  gap: 1rem;
  align-items: start;
}
.evaluation-case-list {
  display: grid;
  gap: 0.5rem;
  min-width: 0;
}
.evaluation-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.125rem;
}
.evaluation-case-row {
  display: grid;
  gap: 0.5rem;
  padding: 1rem;
  border: 1px solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface);
  color: var(--workspace-text);
  text-align: left;
  cursor: pointer;
  font-family: inherit;
}
.evaluation-case-row:hover,
.evaluation-case-row.selected {
  border-color: var(--teal-dark);
  background: color-mix(in oklab, var(--teal) 6%, var(--surface));
}
.evaluation-case-row strong {
  font-size: 0.875rem;
  line-height: 1.6;
  font-weight: 550;
  overflow-wrap: anywhere;
}
.evaluation-case-row small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  overflow-wrap: anywhere;
}
.evaluation-case-row > span {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8125rem;
}
.evaluation-detail {
  min-width: 0;
}
.evaluation-detail-content {
  display: grid;
  gap: 1rem;
}
.evaluation-targets {
  display: grid;
  gap: 0.75rem;
  margin: 0;
}
.evaluation-targets > div {
  display: grid;
  gap: 0.25rem;
}
.evaluation-targets dt {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.evaluation-targets dd {
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.875rem;
  overflow-wrap: anywhere;
}
.evaluation-targets ul {
  margin: 0;
  padding-left: 1.25rem;
}
.evaluation-result {
  padding: 1rem;
  border: 1px solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface);
}
.evaluation-result h3 {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
}
.evaluation-result-score {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.75rem;
  margin: 0.75rem 0 0.25rem;
  color: var(--workspace-text);
  font-size: 1.625rem;
  font-weight: 650;
}
.evaluation-result-score > span {
  color: var(--workspace-muted);
  font-size: 0.8125rem;
  font-weight: 400;
}
.evaluation-result-issues {
  margin: 0.75rem 0;
  padding-left: 1.25rem;
  color: var(--red);
  line-height: 1.8;
  font-size: 0.8125rem;
  overflow-wrap: anywhere;
}
.evaluation-result-issues:empty {
  display: none;
}
.evaluation-result details {
  margin-top: 0.75rem;
}
.evaluation-result details p {
  font-size: 0.8125rem;
  overflow-wrap: anywhere;
}
.evaluation-manual,
.evaluation-advanced {
  border-top: 1px solid var(--workspace-border);
  padding-top: 0.875rem;
}
summary {
  cursor: pointer;
  font-size: 0.8125rem;
  color: var(--workspace-text);
}
.evaluation-manual p {
  line-height: 1.7;
  font-size: 0.8125rem;
}
.evaluation-advanced[open] > div {
  margin-top: 1rem;
}
.evaluation-loading {
  display: flex;
  gap: 0.625rem;
  align-items: center;
  padding: 2rem 0;
  color: var(--workspace-muted);
}
.evaluation-case-dialog {
  max-height: 90dvh;
  overflow-y: auto;
}
.evaluation-case-form {
  display: grid;
  gap: 1rem;
}
.evaluation-case-form textarea {
  box-sizing: border-box;
  width: 100%;
  resize: vertical;
  min-height: 4rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface);
  color: var(--workspace-text);
  font: inherit;
  line-height: 1.6;
}
.is-spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 68rem) {
  .evaluation-columns {
    grid-template-columns: minmax(13rem, 0.8fr) minmax(0, 1.2fr);
  }
}
@media (max-width: 55rem) {
  .evaluation-columns {
    grid-template-columns: minmax(0, 1fr);
  }
  .evaluation-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 30rem) {
  .evaluation-summary > div {
    padding: 0.875rem;
  }
  .evaluation-toolbar {
    align-items: flex-start;
  }
}
</style>
