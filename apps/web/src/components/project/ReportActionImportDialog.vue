<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router";
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "@lucide/vue";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { actionItemsApi } from "@/api/action-items";
import { getApiErrorCode, getApiErrorMessage } from "@/api/core";
import { workspaceApi } from "@/api/workspace";
import type {
  ReportActionDraft,
  ReportActionCandidate,
  WorkspaceMember,
} from "@/api/types";

const props = defineProps<{
  open: boolean;
  workspaceId: number | string;
  projectId: number;
  reportId?: number | string;
}>();
const emit = defineEmits<{
  "update:open": [boolean];
  imported: [number | string];
  manual: [number | string, string];
}>();
type Candidate = ReportActionCandidate & {
  selected: boolean;
  ownerId: string;
  blocksRelease: boolean;
  exists: boolean;
};
const draft = ref<ReportActionDraft | null>(null),
  rows = ref<Candidate[]>([]),
  members = ref<WorkspaceMember[]>([]);
const loading = ref(false),
  saving = ref(false),
  error = ref(""),
  memberError = ref(""),
  sourceStale = ref(false);
const activeKey = ref(""),
  bulkOwner = ref(""),
  baseline = ref(""),
  discardOpen = ref(false);
const editorElement = ref<HTMLElement | null>(null),
  contentElement = ref<HTMLElement | null>(null);
let scope = 0,
  discardResolver: ((allow: boolean) => void) | null = null;
const selected = computed(() =>
  rows.value.filter((row) => row.selected && !row.exists),
);
const activeIndex = computed(() =>
  rows.value.findIndex((row) => row.sourceKey === activeKey.value),
);
const activeRow = computed(() => rows.value[activeIndex.value]);
const available = computed(() => rows.value.filter((row) => !row.exists));
const allSelected = computed(
  () =>
    available.value.length > 0 &&
    selected.value.length === available.value.length,
);
const invalidRows = computed(() =>
  selected.value.filter(
    (row) =>
      !row.title.trim() ||
      row.title.length > 255 ||
      !row.acceptanceCriteria.trim() ||
      row.acceptanceCriteria.length > 4000,
  ),
);
const valid = computed(
  () => selected.value.length > 0 && !invalidRows.value.length,
);
const unassigned = computed(
  () => selected.value.filter((row) => !row.ownerId).length,
);
const editable = computed(
  () =>
    !!draft.value?.canManage &&
    !!activeRow.value &&
    !activeRow.value.exists &&
    activeRow.value.selected &&
    !saving.value &&
    !sourceStale.value,
);
function snapshot() {
  return JSON.stringify(
    rows.value.map((row) => ({
      key: row.sourceKey,
      title: row.title,
      criteria: row.acceptanceCriteria,
      owner: row.ownerId,
      due: row.dueAt,
      selected: row.selected,
      blocks: row.blocksRelease,
    })),
  );
}
const dirty = computed(() => !!draft.value && snapshot() !== baseline.value);
function allowDiscard() {
  if (!dirty.value) return Promise.resolve(true);
  if (discardResolver) return Promise.resolve(false);
  discardOpen.value = true;
  return new Promise<boolean>((resolve) => {
    discardResolver = resolve;
  });
}
function decideDiscard(allow: boolean) {
  discardOpen.value = false;
  const resolve = discardResolver;
  discardResolver = null;
  resolve?.(allow);
}
async function requestClose() {
  if (!saving.value && (await allowDiscard())) emit("update:open", false);
}
async function viewExisting() {
  if (saving.value || !(await allowDiscard()) || !draft.value) return;
  emit("update:open", false);
  emit("imported", draft.value.reportId);
}
async function reload() {
  if (!saving.value && (await allowDiscard())) await load();
}
async function load() {
  const current = ++scope;
  if (!props.reportId) return;
  loading.value = true;
  error.value = "";
  memberError.value = "";
  sourceStale.value = false;
  draft.value = null;
  rows.value = [];
  members.value = [];
  bulkOwner.value = "";
  try {
    const [source, people] = await Promise.allSettled([
      actionItemsApi.reportDraft(
        props.workspaceId,
        props.projectId,
        props.reportId,
      ),
      workspaceApi.members(props.workspaceId),
    ]);
    if (current !== scope) return;
    if (source.status !== "fulfilled") throw source.reason;
    draft.value = source.value;
    if (people.status === "fulfilled")
      members.value = people.value.filter(
        (person) => !person.status || person.status === "ACTIVE",
      );
    else memberError.value = "成员列表暂时不可用，可以稍后分派。";
    const existing = new Set(
      source.value.existing.map((item) => item.sourceKey),
    );
    rows.value = source.value.items.map((item) => ({
      ...item,
      selected: !existing.has(item.sourceKey),
      exists: existing.has(item.sourceKey),
      ownerId: "",
      blocksRelease: true,
    }));
    activeKey.value =
      rows.value.find((row) => !row.exists)?.sourceKey ||
      rows.value[0]?.sourceKey ||
      "";
    baseline.value = snapshot();
  } catch (exc) {
    if (current === scope)
      error.value = getApiErrorMessage(exc, "无法读取报告行动清单");
  } finally {
    if (current === scope) loading.value = false;
  }
}
function toggleAll(checked: boolean) {
  rows.value.forEach((row) => {
    if (!row.exists) row.selected = checked;
  });
}
function assignOwner() {
  if (!bulkOwner.value || !draft.value?.canManage || sourceStale.value) return;
  selected.value.forEach((row) => {
    row.ownerId = bulkOwner.value === "unassigned" ? "" : bulkOwner.value;
  });
}
function selectAdjacent(offset: number) {
  const row = rows.value[activeIndex.value + offset];
  if (row) activeKey.value = row.sourceKey;
}
function showFirstInvalid() {
  if (invalidRows.value[0]) activeKey.value = invalidRows.value[0].sourceKey;
}
watch(activeKey, async () => {
  await nextTick();
  if (editorElement.value) editorElement.value.scrollTop = 0;
  if (contentElement.value) contentElement.value.scrollTop = 0;
});
watch(
  () => [props.open, props.workspaceId, props.projectId, props.reportId],
  () => {
    if (props.open) void load();
    else {
      scope++;
      decideDiscard(false);
    }
  },
);
const navigationAllowed = () =>
  !props.open ? true : saving.value ? false : allowDiscard();
onBeforeRouteLeave(navigationAllowed);
onBeforeRouteUpdate((to, from) =>
  to.params.projectId !== from.params.projectId ||
  to.params.workspaceId !== from.params.workspaceId
    ? navigationAllowed()
    : true,
);
onBeforeUnmount(() => {
  scope++;
  decideDiscard(false);
});
async function save() {
  if (
    !valid.value ||
    !draft.value?.canManage ||
    saving.value ||
    sourceStale.value ||
    !props.reportId
  )
    return;
  const current = scope,
    reportId = props.reportId;
  saving.value = true;
  error.value = "";
  try {
    await actionItemsApi.importReport(
      props.workspaceId,
      props.projectId,
      reportId,
      {
        sourceHash: draft.value.sourceHash,
        items: selected.value.map((row) => ({
          sourceKey: row.sourceKey,
          title: row.title,
          description: row.description,
          acceptanceCriteria: row.acceptanceCriteria,
          ownerId: row.ownerId || null,
          dueAt: row.dueAt || null,
          priority: row.priority,
          blocksRelease: row.blocksRelease,
        })),
      },
    );
    if (current === scope) {
      emit("update:open", false);
      emit("imported", reportId);
    }
  } catch (exc) {
    if (current === scope) {
      error.value = getApiErrorMessage(exc, "行动项导入失败");
      sourceStale.value = getApiErrorCode(exc) === "ACTION_SOURCE_CHANGED";
    }
  } finally {
    if (current === scope) saving.value = false;
  }
}
</script>

<template>
  <Dialog
    :open="open"
    @update:open="
      (value) => {
        if (!value) void requestClose();
      }
    "
  >
    <DialogContent class="task-import-dialog" :show-close-button="false">
      <DialogHeader class="import-header"
        ><DialogTitle>从报告建立行动项</DialogTitle
        ><DialogDescription
          >先勾选任务，再分派负责人并逐项确认；导入顺序与报告保持一致。</DialogDescription
        >
        <p v-if="draft" class="import-report-title">
          {{ draft.reportTitle
          }}<span v-if="draft.reportVersion">
            · v{{ draft.reportVersion }}</span
          >
        </p></DialogHeader
      >
      <div v-if="loading" class="import-loading" role="status">
        <RefreshCw class="is-spinning" :size="18" />正在读取报告任务…
      </div>
      <div
        v-if="error || memberError || (draft && !draft.canManage)"
        class="import-messages"
      >
        <Alert v-if="error" variant="destructive"
          ><AlertTitle>{{
            sourceStale ? "来源报告已更新" : "读取或导入未完成"
          }}</AlertTitle
          ><AlertDescription
            >{{ error
            }}<Button
              variant="link"
              :disabled="loading || saving"
              @click="reload"
              >重新读取报告</Button
            ></AlertDescription
          ></Alert
        ><Alert v-if="memberError"
          ><AlertDescription>{{ memberError }}</AlertDescription></Alert
        ><Alert v-if="draft && !draft.canManage"
          ><AlertDescription
            >你可以查看任务来源，导入和分派由项目创建者或管理员完成。</AlertDescription
          ></Alert
        >
      </div>

      <template v-if="draft && rows.length">
        <div class="import-toolbar">
          <Field orientation="horizontal"
            ><Checkbox
              id="import-select-all"
              :model-value="
                allSelected ? true : selected.length ? 'indeterminate' : false
              "
              :disabled="
                !draft.canManage || saving || !available.length || sourceStale
              "
              @update:model-value="(value) => toggleAll(value === true)"
            /><FieldLabel for="import-select-all"
              >全选待建立任务</FieldLabel
            ></Field
          >
          <span class="import-selection-count"
            >已选 {{ selected.length }} / {{ available.length }} 项 · 已建立
            {{ draft.existing.length }} 项</span
          >
          <div v-if="draft.canManage && available.length" class="bulk-assign">
            <label for="import-bulk-owner" class="sr-only">批量负责人</label
            ><select
              id="import-bulk-owner"
              v-model="bulkOwner"
              class="import-select"
              :disabled="saving || sourceStale"
            >
              <option value="" disabled>批量分派负责人</option>
              <option value="unassigned">稍后分派</option>
              <option
                v-for="person in members"
                :key="person.userId || person.id"
                :value="String(person.userId || person.id)"
              >
                {{ person.userName || person.userId }}
              </option></select
            ><Button
              variant="outline"
              size="sm"
              :disabled="
                !bulkOwner || !selected.length || saving || sourceStale
              "
              @click="assignOwner"
              >应用到所选</Button
            >
          </div>
        </div>

        <div ref="contentElement" class="import-content">
          <nav class="import-sidebar" aria-label="报告任务清单">
            <div
              v-for="(row, index) in rows"
              :key="row.sourceKey"
              class="import-task-row"
              :class="{ 'is-active': activeKey === row.sourceKey }"
            >
              <Checkbox
                :id="'import-select-' + index"
                v-model="row.selected"
                :disabled="
                  row.exists || !draft.canManage || saving || sourceStale
                "
              /><label :for="'import-select-' + index" class="sr-only"
                >选择 {{ row.title }}</label
              ><button
                type="button"
                :aria-current="activeKey === row.sourceKey ? 'true' : undefined"
                @click="activeKey = row.sourceKey"
              >
                <span>{{ index + 1 }}. {{ row.title }}</span
                ><small>{{
                  row.exists
                    ? "已建立"
                    : row.ownerId
                      ? members.find(
                          (person) =>
                            String(person.userId || person.id) === row.ownerId,
                        )?.userName || "已分派"
                      : "尚未分派"
                }}</small></button
              ><CheckCircle2 v-if="row.exists" :size="14" />
            </div>
          </nav>

          <div ref="editorElement" class="import-editor">
            <Field class="mobile-task-picker"
              ><FieldLabel for="import-active-task">当前任务</FieldLabel
              ><select
                id="import-active-task"
                v-model="activeKey"
                class="import-select"
              >
                <option
                  v-for="(row, index) in rows"
                  :key="row.sourceKey"
                  :value="row.sourceKey"
                >
                  {{ index + 1 }}. {{ row.title
                  }}{{ row.exists ? "（已建立）" : "" }}
                </option>
              </select></Field
            >
            <template v-if="activeRow">
              <div class="import-item-heading">
                <h3>任务 {{ activeIndex + 1 }} / {{ rows.length }}</h3>
                <div>
                  <Button
                    variant="outline"
                    size="icon-sm"
                    aria-label="上一项任务"
                    :disabled="activeIndex === 0"
                    @click="selectAdjacent(-1)"
                    ><ChevronLeft /></Button
                  ><Button
                    variant="outline"
                    size="icon-sm"
                    aria-label="下一项任务"
                    :disabled="activeIndex === rows.length - 1"
                    @click="selectAdjacent(1)"
                    ><ChevronRight
                  /></Button>
                </div>
              </div>
              <Field orientation="horizontal"
                ><Checkbox
                  :id="'import-current-' + activeIndex"
                  v-model="activeRow.selected"
                  :disabled="
                    activeRow.exists ||
                    !draft.canManage ||
                    saving ||
                    sourceStale
                  "
                /><FieldLabel :for="'import-current-' + activeIndex">{{
                  activeRow.exists ? "此任务已建立" : "导入这项任务"
                }}</FieldLabel></Field
              >
              <Alert v-if="activeRow.exists"
                ><AlertDescription
                  >此任务已建立，不会重复创建。当前任务要求与进展可在行动项页面查看。<Button
                    variant="link"
                    @click="viewExisting"
                    >查看已建立任务<ArrowRight
                      data-icon="inline-end" /></Button></AlertDescription
              ></Alert>
              <FieldGroup v-else>
                <Field
                  :data-invalid="activeRow.selected && !activeRow.title.trim()"
                  ><FieldLabel :for="'import-title-' + activeIndex"
                    >任务名称</FieldLabel
                  ><Input
                    :id="'import-title-' + activeIndex"
                    v-model="activeRow.title"
                    :disabled="!editable"
                    maxlength="255"
                    :aria-invalid="
                      activeRow.selected && !activeRow.title.trim()
                    "
                /></Field>
                <Field
                  :data-invalid="
                    activeRow.selected && !activeRow.acceptanceCriteria.trim()
                  "
                  ><FieldLabel :for="'import-criteria-' + activeIndex"
                    >验收标准</FieldLabel
                  ><textarea
                    :id="'import-criteria-' + activeIndex"
                    v-model="activeRow.acceptanceCriteria"
                    class="import-textarea"
                    :disabled="!editable"
                    rows="5"
                    maxlength="4000"
                    :aria-invalid="
                      activeRow.selected && !activeRow.acceptanceCriteria.trim()
                    "
                  /><FieldDescription
                    v-if="
                      activeRow.selected && !activeRow.acceptanceCriteria.trim()
                    "
                    >请补充验收标准后再建立。</FieldDescription
                  ></Field
                >
                <FieldGroup class="import-form-grid"
                  ><Field
                    ><FieldLabel :for="'import-owner-' + activeIndex"
                      >实际负责人</FieldLabel
                    ><select
                      :id="'import-owner-' + activeIndex"
                      v-model="activeRow.ownerId"
                      class="import-select"
                      :disabled="!editable"
                    >
                      <option value="">稍后分派</option>
                      <option
                        v-for="person in members"
                        :key="person.userId || person.id"
                        :value="String(person.userId || person.id)"
                      >
                        {{ person.userName || person.userId }}
                      </option></select
                    ><FieldDescription v-if="activeRow.ownerLabel"
                      >原文角色：{{ activeRow.ownerLabel }}</FieldDescription
                    ></Field
                  ><Field
                    ><FieldLabel :for="'import-due-' + activeIndex"
                      >截止日期</FieldLabel
                    ><Input
                      :id="'import-due-' + activeIndex"
                      v-model="activeRow.dueAt"
                      type="date"
                      :disabled="!editable" /></Field
                ></FieldGroup>
                <Field orientation="horizontal"
                  ><Checkbox
                    :id="'import-block-' + activeIndex"
                    v-model="activeRow.blocksRelease"
                    :disabled="!editable"
                  /><FieldLabel :for="'import-block-' + activeIndex"
                    >发布前必须验收关闭</FieldLabel
                  ></Field
                >
              </FieldGroup>
            </template>
          </div>
        </div>
      </template>
      <div v-else-if="draft && !rows.length" class="import-empty">
        <h3>报告中没有识别到行动清单</h3>
        <p>可手工建立关联任务，来源报告会保留。</p>
        <Button
          v-if="draft.canManage"
          variant="outline"
          @click="
            emit('manual', draft.reportId, draft.reportTitle);
            emit('update:open', false);
          "
          >手工建立关联任务</Button
        >
      </div>

      <div class="import-footer">
        <div class="import-footer-note">
          <span v-if="draft && !draft.canManage">当前仅预览报告任务</span
          ><span v-else-if="selected.length"
            >将建立 {{ selected.length }} 项任务<span v-if="unassigned"
              >，其中 {{ unassigned }} 项稍后分派</span
            ></span
          ><span v-else>{{
            available.length
              ? "勾选需要建立的任务"
              : "清单中的任务均已建立，无需重复导入"
          }}</span
          ><Button
            v-if="invalidRows.length"
            variant="link"
            size="sm"
            @click="showFirstInvalid"
            >{{ invalidRows.length }} 项要求待完善，点击检查</Button
          >
        </div>
        <div>
          <Button variant="outline" :disabled="saving" @click="requestClose"
            >取消</Button
          ><Button
            v-if="draft?.existing.length && !available.length"
            variant="outline"
            @click="viewExisting"
            >查看已建立任务</Button
          ><Button
            v-if="available.length && draft?.canManage"
            :disabled="!valid || saving || sourceStale"
            @click="save"
            ><RefreshCw
              v-if="saving"
              data-icon="inline-start"
              class="is-spinning"
            />{{
              saving ? "正在建立…" : "按顺序建立 " + selected.length + " 项"
            }}</Button
          >
        </div>
      </div>
    </DialogContent>
  </Dialog>
  <Dialog
    :open="discardOpen"
    @update:open="
      (value) => {
        if (!value) decideDiscard(false);
      }
    "
    ><DialogContent
      ><DialogHeader
        ><DialogTitle>放弃导入设置？</DialogTitle
        ><DialogDescription
          >已调整的负责人、任务内容和勾选状态尚未导入。</DialogDescription
        ></DialogHeader
      ><DialogFooter
        ><Button variant="outline" @click="decideDiscard(false)"
          >继续确认</Button
        ><Button variant="destructive" @click="decideDiscard(true)"
          >放弃修改</Button
        ></DialogFooter
      ></DialogContent
    ></Dialog
  >
</template>

<style scoped>
:global(.task-import-dialog) {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: calc(100vw - 2rem);
  max-width: 62rem !important;
  height: min(46rem, calc(100dvh - 2rem));
  max-height: calc(100dvh - 2rem);
  padding: 0;
  overflow: hidden;
}
.import-header {
  padding: 1.25rem 1.5rem;
  flex: 0 0 auto;
}
.import-report-title {
  font-size: 0.75rem;
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted-foreground);
  margin: 0.5rem 0 0;
}
.import-toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.8rem 1.5rem;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  flex: 0 0 auto;
}
.import-toolbar :deep([data-slot="field"]) {
  width: auto;
}
.import-selection-count {
  font-size: 0.72rem;
  color: var(--muted-foreground);
}
.bulk-assign {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-left: auto;
  max-width: 100%;
}
.bulk-assign select {
  max-width: 12rem;
}
.import-content {
  display: grid;
  grid-template-columns: minmax(14rem, 19rem) minmax(0, 1fr);
  min-height: 0;
  flex: 1 1 0;
  overflow: hidden;
}
.import-sidebar {
  overflow-y: auto;
  border-right: 1px solid var(--border);
  padding: 0.6rem;
  min-width: 0;
}
.import-task-row {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  border-radius: 0.5rem;
  padding: 0.7rem 0.6rem;
}
.import-task-row :deep([role="checkbox"]) {
  flex-shrink: 0;
  margin-top: 0.15rem;
}
.import-task-row.is-active {
  background: var(--muted);
}
.import-task-row button {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  border: 0;
  background: transparent;
  color: var(--foreground);
  padding: 0;
  text-align: left;
  cursor: pointer;
  min-width: 0;
  flex: 1;
}
.import-task-row button > span {
  font-size: 0.8rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.import-task-row small {
  font-size: 0.68rem;
  color: var(--muted-foreground);
}
.import-editor {
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  min-width: 0;
}
.import-editor > * {
  flex-shrink: 0;
}
.import-item-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.import-item-heading h3 {
  font-size: 0.8rem;
  margin: 0;
  color: var(--muted-foreground);
  font-weight: 500;
}
.import-item-heading > div {
  display: flex;
  gap: 0.35rem;
}
.import-select,
.import-textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--input);
  border-radius: 0.5rem;
  background: var(--background);
  color: var(--foreground);
  font: inherit;
  font-size: 0.8rem;
  outline: none;
}
.import-select {
  height: 2.25rem;
  padding: 0.3rem 0.65rem;
  text-overflow: ellipsis;
}
.import-textarea {
  resize: vertical;
  line-height: 1.8;
  padding: 0.65rem;
}
.import-select:focus-visible,
.import-textarea:focus-visible {
  border-color: var(--ring);
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--ring) 25%, transparent);
}
.import-select:disabled,
.import-textarea:disabled {
  opacity: 0.55;
}
.import-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
}
.import-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.7rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border);
  flex: 0 0 auto;
}
.import-footer > div:last-child {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-left: auto;
}
.import-footer-note {
  font-size: 0.75rem;
  color: var(--muted-foreground);
  line-height: 1.6;
}
.import-footer-note small {
  display: block;
  color: var(--destructive);
}
.import-messages {
  flex: 0 0 auto;
  padding: 0 1.5rem 0.75rem;
}
.import-loading,
.import-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  flex: 1 1 0;
  min-height: 8rem;
  padding: 1.5rem;
  color: var(--muted-foreground);
  font-size: 0.8rem;
}
.import-empty {
  flex-direction: column;
  text-align: center;
}
.import-empty h3,
.import-empty p {
  margin: 0;
}
.mobile-task-picker {
  display: none;
}
@media (max-width: 47.5rem) {
  :global(.task-import-dialog) {
    width: 100vw;
    max-width: 100vw !important;
    height: 100dvh;
    max-height: 100dvh;
    border-radius: 0;
  }
  .import-header {
    padding: 1rem;
  }
  .import-toolbar {
    padding: 0.65rem 1rem;
    gap: 0.5rem;
  }
  .bulk-assign {
    width: 100%;
    margin: 0;
  }
  .bulk-assign select {
    flex: 1;
    max-width: none;
  }
  .import-content {
    display: block;
    overflow-y: auto;
  }
  .import-sidebar {
    display: none;
  }
  .import-editor {
    overflow: visible;
    padding: 1rem;
  }
  .mobile-task-picker {
    display: flex;
  }
  .import-form-grid {
    grid-template-columns: 1fr;
  }
  .import-footer {
    padding: 0.8rem 1rem;
  }
  .import-footer-note {
    font-size: 0.7rem;
    width: 100%;
  }
  .import-footer > div:last-child {
    width: 100%;
    justify-content: flex-end;
  }
  .import-messages {
    padding: 0 1rem 0.5rem;
  }
}
</style>
