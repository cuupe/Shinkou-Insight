<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  FileText,
  Pencil,
  RefreshCw,
  ShieldCheck,
  UserRound,
  X,
} from "@lucide/vue";
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
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  actionCommand,
  actionMetadataEditable,
  actionStatusLabel,
} from "@/utils/actionWorkflow";
import { formatDateTime } from "@/lib/utils";
import type { ActionWorkflow } from "@/composables/useActionWorkflow";

const props = defineProps<{ workflow: ActionWorkflow }>();
const {
  itemDialogOpen,
  editingItemId,
  dialogMode,
  dialogTitle,
  dialogError,
  metadataEditable,
  actionForm,
  selectedItem,
  completionDraft,
  acceptanceDraft,
  saving,
  owners,
  sourceReports,
  discardOpen,
  decideDiscard,
  requestTaskClose,
  backToDetail,
  editSelectedItem,
  saveActionItem,
  advanceItem,
  finishWorkflow,
  goSource,
} = props.workflow;
const next = computed(() =>
  selectedItem.value ? actionCommand(selectedItem.value) : null,
);
const canEdit = computed(
  () => !!selectedItem.value && actionMetadataEditable(selectedItem.value),
);
const sourceTitle = computed(
  () =>
    selectedItem.value?.sourceReportTitle ||
    sourceReports.value.find(
      (report) => String(report.id) === actionForm.sourceReportId,
    )?.title ||
    "关联报告",
);
const bodyElement = ref<HTMLElement | null>(null);
async function resetBodyScroll() {
  await nextTick();
  if (bodyElement.value) bodyElement.value.scrollTop = 0;
}
watch([dialogMode, editingItemId, itemDialogOpen], () => {
  void resetBodyScroll();
});
watch(dialogError, (message) => {
  if (message) void resetBodyScroll();
});
</script>

<template>
  <Dialog
    :open="itemDialogOpen"
    @update:open="
      (value) => {
        if (!value) void requestTaskClose();
      }
    "
  >
    <DialogContent class="action-task-panel" :show-close-button="false">
      <DialogHeader class="task-panel-header">
        <div class="panel-topline">
          <div class="panel-badges">
            <Badge v-if="selectedItem" variant="secondary">{{
              actionStatusLabel(selectedItem)
            }}</Badge
            ><span>{{
              selectedItem?.blocksRelease === false
                ? "发布后跟进"
                : "发布前置任务"
            }}</span>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="关闭任务面板"
            :disabled="saving"
            @click="requestTaskClose"
            ><X
          /></Button>
        </div>
        <Button
          v-if="editingItemId && dialogMode !== 'detail'"
          class="panel-back"
          variant="ghost"
          size="sm"
          :disabled="saving"
          @click="backToDetail"
          ><ArrowLeft data-icon="inline-start" />返回任务详情</Button
        >
        <DialogTitle>{{ dialogTitle }}</DialogTitle
        ><DialogDescription>{{
          dialogMode === "detail"
            ? "任务要求、执行证据和验收记录集中在此查看。"
            : dialogMode === "edit"
              ? "填写任务要求与负责人，保存后继续执行。"
              : dialogMode === "submit"
                ? "说明执行结果并提供证据，提交后等待管理者验收。"
                : "对照验收标准核对提交的证据，再记录结论。"
        }}</DialogDescription>
        <p
          v-if="selectedItem && dialogMode !== 'detail'"
          class="panel-task-context"
        >
          {{ selectedItem.title }}
        </p>
      </DialogHeader>

      <div ref="bodyElement" class="task-panel-body">
        <Alert v-if="dialogError" variant="destructive"
          ><AlertTitle>操作未完成</AlertTitle
          ><AlertDescription>{{ dialogError }}</AlertDescription></Alert
        >

        <template v-if="dialogMode === 'detail' && selectedItem">
          <dl class="task-facts">
            <div>
              <dt><UserRound :size="14" />负责人</dt>
              <dd>{{ selectedItem.owner }}</dd>
            </div>
            <div>
              <dt><CalendarDays :size="14" />截止日期</dt>
              <dd>{{ selectedItem.dueAt || "未设置" }}</dd>
            </div>
            <div>
              <dt>优先级</dt>
              <dd>{{ selectedItem.priority }}</dd>
            </div>
            <div>
              <dt><ShieldCheck :size="14" />交付要求</dt>
              <dd>
                {{
                  selectedItem.blocksRelease === false
                    ? "发布后继续跟进"
                    : "发布前必须验收"
                }}
              </dd>
            </div>
          </dl>
          <section v-if="selectedItem.description" class="task-section">
            <h3>任务背景</h3>
            <p>{{ selectedItem.description }}</p>
          </section>
          <section class="task-section">
            <h3>验收标准</h3>
            <p>
              {{
                selectedItem.acceptanceCriteria ||
                "尚未补充验收标准，请由项目管理者编辑完善。"
              }}
            </p>
          </section>
          <section class="task-section">
            <h3>完成证据与执行记录</h3>
            <p v-if="selectedItem.completionEvidence">
              {{ selectedItem.completionEvidence }}
            </p>
            <p v-else class="muted">
              尚未提交。负责人执行完成后，在此提交可核对的记录。
            </p>
            <small v-if="selectedItem.submittedAt"
              >提交于 {{ formatDateTime(selectedItem.submittedAt) }}</small
            >
          </section>
          <section v-if="selectedItem.acceptanceComment" class="task-section">
            <h3>{{ selectedItem.acceptedAt ? "验收记录" : "退回意见" }}</h3>
            <p>{{ selectedItem.acceptanceComment }}</p>
            <small v-if="selectedItem.acceptedAt"
              >{{ selectedItem.acceptedByName || "项目管理者" }} ·
              {{ formatDateTime(selectedItem.acceptedAt) }}</small
            >
          </section>
          <Alert
            v-if="selectedItem.status === 'done' && !selectedItem.acceptedAt"
            ><AlertTitle>历史任务待补验收</AlertTitle
            ><AlertDescription
              >这条记录只有完成状态，没有验收凭据。请补齐标准并重新打开任务，提交证据后再验收。</AlertDescription
            ></Alert
          >
        </template>

        <form
          v-else-if="dialogMode === 'edit'"
          id="action-edit-form"
          @submit.prevent="saveActionItem"
        >
          <FieldGroup
            ><FieldSet
              ><FieldLegend>任务要求</FieldLegend>
              <Field
                ><FieldLabel for="action-title"
                  >任务名称 <span class="required-note">必填</span></FieldLabel
                ><Input
                  id="action-title"
                  v-model="actionForm.title"
                  maxlength="255"
                  aria-required="true"
                  :disabled="saving"
                  placeholder="写清需要完成的事情"
              /></Field>
              <Field
                ><FieldLabel for="action-description">任务背景</FieldLabel
                ><textarea
                  id="action-description"
                  v-model="actionForm.description"
                  class="task-textarea"
                  rows="3"
                  maxlength="1000"
                  :disabled="saving"
                  placeholder="背景、范围与需要注意的事项"
                />
              </Field>
              <Field
                ><FieldLabel for="action-criteria"
                  >验收标准 <span class="required-note">必填</span></FieldLabel
                ><textarea
                  id="action-criteria"
                  v-model="actionForm.acceptanceCriteria"
                  class="task-textarea"
                  rows="4"
                  maxlength="4000"
                  aria-required="true"
                  :disabled="saving"
                  placeholder="明确交付物、通过条件及所需证据"
                /><FieldDescription
                  >负责人和验收人将共同使用这份标准。</FieldDescription
                ></Field
              > </FieldSet
            ><FieldSet
              ><FieldLegend>分派与时间</FieldLegend
              ><FieldGroup class="task-form-grid">
                <Field
                  ><FieldLabel for="action-owner">实际负责人</FieldLabel
                  ><select
                    id="action-owner"
                    v-model="actionForm.ownerId"
                    class="task-select"
                    :disabled="saving"
                  >
                    <option value="">稍后分派</option>
                    <option
                      v-for="person in owners"
                      :key="person.userId || person.id"
                      :value="String(person.userId || person.id)"
                    >
                      {{ person.userName || person.userId }}
                    </option></select
                  ><FieldDescription
                    >分派后才能开始执行。</FieldDescription
                  ></Field
                >
                <Field
                  ><FieldLabel for="action-due">截止日期</FieldLabel
                  ><Input
                    id="action-due"
                    v-model="actionForm.due"
                    type="date"
                    :disabled="saving"
                /></Field>
                <Field
                  ><FieldLabel for="action-priority">优先级</FieldLabel
                  ><select
                    id="action-priority"
                    v-model="actionForm.priority"
                    class="task-select"
                    :disabled="saving"
                  >
                    <option value="高">高</option>
                    <option value="中">中</option>
                    <option value="低">低</option>
                  </select></Field
                >
                <Field v-if="!editingItemId && !actionForm.sourceReviewRunId"
                  ><FieldLabel for="action-report">来源报告</FieldLabel
                  ><select
                    id="action-report"
                    v-model="actionForm.sourceReportId"
                    class="task-select"
                    :disabled="saving"
                  >
                    <option value="">独立任务</option>
                    <option
                      v-for="report in sourceReports"
                      :key="report.id"
                      :value="String(report.id)"
                    >
                      {{ report.title }}
                    </option>
                  </select></Field
                >
              </FieldGroup>
              <p
                v-if="actionForm.sourceReviewRunId && !editingItemId"
                class="prefilled-source"
              >
                来源：{{ sourceTitle }} · 审查 #{{
                  actionForm.sourceReviewRunId
                }}
              </p>
              <Field orientation="horizontal"
                ><Checkbox
                  id="action-block-release"
                  v-model="actionForm.blocksRelease"
                  :disabled="saving"
                />
                <div>
                  <FieldLabel for="action-block-release"
                    >发布前必须验收关闭</FieldLabel
                  ><FieldDescription
                    >未验收的前置任务会阻止报告发布。</FieldDescription
                  >
                </div></Field
              ></FieldSet
            ></FieldGroup
          >
        </form>

        <template v-else-if="selectedItem">
          <div class="review-compare">
            <section class="task-section compare-standard">
              <h3>验收标准</h3>
              <p>{{ selectedItem.acceptanceCriteria || "尚未填写" }}</p>
            </section>
            <section
              v-if="dialogMode === 'accept'"
              class="task-section compare-evidence"
            >
              <h3>已提交的完成证据</h3>
              <p>{{ selectedItem.completionEvidence || "没有完成证据" }}</p>
              <small v-if="selectedItem.submittedAt"
                >提交于 {{ formatDateTime(selectedItem.submittedAt) }}</small
              >
            </section>
          </div>
          <Alert
            v-if="selectedItem.acceptanceComment && !selectedItem.acceptedAt"
            ><AlertTitle>上次退回意见</AlertTitle
            ><AlertDescription>{{
              selectedItem.acceptanceComment
            }}</AlertDescription></Alert
          >
          <form
            v-if="dialogMode === 'submit'"
            id="action-submit-form"
            @submit.prevent="finishWorkflow()"
          >
            <FieldGroup
              ><Field
                ><FieldLabel for="action-evidence"
                  >完成证据与执行记录
                  <span class="required-note">必填</span></FieldLabel
                ><textarea
                  id="action-evidence"
                  v-model="completionDraft"
                  class="task-textarea"
                  rows="9"
                  maxlength="8000"
                  aria-required="true"
                  :disabled="saving"
                  placeholder="执行了什么、结果如何、证据在哪里？可粘贴文档链接、测试记录或结果说明。"
                /><FieldDescription
                  >请逐项说明如何满足验收标准。{{ completionDraft.length }} /
                  8000</FieldDescription
                ></Field
              ></FieldGroup
            >
          </form>
          <FieldGroup v-else
            ><Field
              ><FieldLabel for="action-acceptance"
                >验收或退回意见
                <span class="required-note">必填</span></FieldLabel
              ><textarea
                id="action-acceptance"
                v-model="acceptanceDraft"
                class="task-textarea"
                rows="5"
                maxlength="4000"
                aria-required="true"
                :disabled="saving"
                placeholder="通过：记录已核对的证据。退回：指出需要补齐的问题。"
              /><FieldDescription
                >意见会保留到任务记录中。</FieldDescription
              ></Field
            ></FieldGroup
          >
        </template>

        <section
          v-if="selectedItem?.sourceReportId"
          class="task-section task-origin"
        >
          <h3>任务来源</h3>
          <Button
            variant="link"
            :disabled="saving"
            @click="goSource(selectedItem)"
            ><FileText data-icon="inline-start" />{{ sourceTitle
            }}<ArrowRight data-icon="inline-end" /></Button
          ><Button
            v-if="selectedItem.sourceReviewRunId"
            variant="link"
            :disabled="saving"
            @click="goSource(selectedItem, true)"
            >审查记录 #{{ selectedItem.sourceReviewRunId
            }}<ArrowRight data-icon="inline-end" /></Button
          ><small v-if="selectedItem.sourceReportVersion"
            >建项时报告版本：v{{ selectedItem.sourceReportVersion }}</small
          >
          <details v-if="selectedItem.sourceExcerpt">
            <summary>查看建项时的原文<ChevronDown :size="14" /></summary>
            <p>{{ selectedItem.sourceExcerpt }}</p>
          </details>
        </section>
      </div>

      <div class="task-panel-footer">
        <template v-if="dialogMode === 'detail' && selectedItem"
          ><Button
            variant="outline"
            :disabled="saving"
            @click="requestTaskClose"
            >关闭</Button
          >
          <div class="panel-primary-actions">
            <Button
              v-if="canEdit"
              variant="outline"
              :disabled="saving"
              @click="editSelectedItem"
              ><Pencil data-icon="inline-start" />编辑任务</Button
            ><Button
              v-if="next"
              :disabled="saving"
              @click="advanceItem(selectedItem)"
              ><RefreshCw
                v-if="saving"
                data-icon="inline-start"
                class="is-spinning" />{{ next.label
              }}<ArrowRight v-if="!saving" data-icon="inline-end"
            /></Button></div
        ></template>
        <template v-else-if="dialogMode === 'edit'"
          ><Button
            variant="outline"
            :disabled="saving"
            @click="editingItemId ? backToDetail() : requestTaskClose()"
            >取消</Button
          ><span
            v-if="
              !actionForm.title.trim() || !actionForm.acceptanceCriteria.trim()
            "
            class="footer-hint"
            >请补齐名称和验收标准</span
          ><Button
            type="submit"
            form="action-edit-form"
            :disabled="
              saving ||
              !metadataEditable ||
              !actionForm.title.trim() ||
              !actionForm.acceptanceCriteria.trim()
            "
            ><RefreshCw
              v-if="saving"
              data-icon="inline-start"
              class="is-spinning"
            />{{
              saving ? "保存中…" : editingItemId ? "保存修改" : "创建行动项"
            }}</Button
          ></template
        >
        <template v-else-if="dialogMode === 'submit'"
          ><Button variant="outline" :disabled="saving" @click="backToDetail"
            >返回详情</Button
          ><Button
            type="submit"
            form="action-submit-form"
            :disabled="saving || !completionDraft.trim()"
            ><ClipboardCheck data-icon="inline-start" />{{
              saving ? "提交中…" : "提交验收"
            }}</Button
          ></template
        >
        <template v-else
          ><Button variant="ghost" :disabled="saving" @click="backToDetail"
            >返回详情</Button
          >
          <div class="panel-primary-actions">
            <Button
              variant="outline"
              :disabled="saving || !acceptanceDraft.trim()"
              @click="finishWorkflow('RETURN')"
              >退回修改</Button
            ><Button
              :disabled="saving || !acceptanceDraft.trim()"
              @click="finishWorkflow('ACCEPT')"
              ><CheckCircle2 data-icon="inline-start" />验收通过并关闭</Button
            >
          </div></template
        >
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
        ><DialogTitle>放弃未保存的修改？</DialogTitle
        ><DialogDescription
          >当前输入尚未保存。继续编辑可保留输入，放弃后将返回原有记录。</DialogDescription
        ></DialogHeader
      ><DialogFooter
        ><Button variant="outline" @click="decideDiscard(false)"
          >继续编辑</Button
        ><Button variant="destructive" @click="decideDiscard(true)"
          >放弃修改</Button
        ></DialogFooter
      ></DialogContent
    ></Dialog
  >
</template>

<style scoped>
:global(.action-task-panel) {
  top: 0;
  right: 0;
  bottom: 0;
  left: auto;
  translate: 0 0;
  transform: none;
  width: min(46rem, 100vw);
  max-width: min(46rem, 100vw) !important;
  height: 100dvh;
  max-height: 100dvh;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  border-radius: 0;
  overflow: hidden;
}
.task-panel-header {
  flex: 0 0 auto;
  padding: 1.2rem 1.5rem;
  border-bottom: 1px solid var(--border);
  gap: 0.5rem;
  min-width: 0;
}
.panel-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.panel-badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.65rem;
  color: var(--muted-foreground);
  font-size: 0.72rem;
}
.task-panel-header :deep([data-slot="dialog-title"]) {
  font-size: 1.1rem;
  line-height: 1.65;
  overflow-wrap: anywhere;
  padding-right: 0.5rem;
}
.panel-back {
  align-self: flex-start;
  padding-left: 0;
}
.panel-task-context {
  font-size: 0.8rem;
  line-height: 1.65;
  color: var(--muted-foreground);
  margin: 0.35rem 0 0;
  overflow-wrap: anywhere;
}
.task-panel-body {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  overscroll-behavior: contain;
}
.task-panel-body > * {
  flex-shrink: 0;
}
.task-facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin: 0;
  padding: 1rem;
  background: var(--muted);
  border-radius: 0.65rem;
}
.task-facts dt {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--muted-foreground);
  font-size: 0.72rem;
}
.task-facts dd {
  margin: 0.4rem 0 0;
  font-size: 0.85rem;
  overflow-wrap: anywhere;
}
.task-section h3 {
  font-size: 0.85rem;
  font-weight: 650;
  margin: 0 0 0.65rem;
}
.task-section p {
  font-size: 0.85rem;
  line-height: 1.85;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 0;
}
.task-section small,
.muted {
  color: var(--muted-foreground);
}
.task-section small {
  display: block;
  margin-top: 0.6rem;
  font-size: 0.72rem;
}
.task-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.task-panel-body :deep(fieldset) {
  min-width: 0;
}
.required-note {
  color: var(--muted-foreground);
  font-size: 0.68rem;
  font-weight: 400;
  margin-left: 0.25rem;
}
.prefilled-source {
  color: var(--muted-foreground);
  font-size: 0.75rem;
  line-height: 1.7;
  margin: 0;
  overflow-wrap: anywhere;
}
.task-select,
.task-textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--input);
  border-radius: 0.5rem;
  background: var(--background);
  color: var(--foreground);
  font: inherit;
  font-size: 0.85rem;
  outline: none;
}
.task-select {
  height: 2.5rem;
  padding: 0.4rem 0.65rem;
  text-overflow: ellipsis;
}
.task-textarea {
  resize: vertical;
  line-height: 1.8;
  padding: 0.65rem 0.8rem;
}
.task-select:focus-visible,
.task-textarea:focus-visible {
  border-color: var(--ring);
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--ring) 25%, transparent);
}
.review-compare {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 1rem;
}
.review-compare .task-section {
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
}
.task-origin {
  border-top: 1px solid var(--border);
  padding-top: 1.25rem;
}
.task-origin :deep(button) {
  padding-left: 0;
  max-width: 100%;
  height: auto;
  text-align: left;
  white-space: normal;
  justify-content: flex-start;
  line-height: 1.8;
}
.task-origin details {
  margin-top: 1rem;
}
.task-origin summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--muted-foreground);
  font-size: 0.75rem;
  cursor: pointer;
}
.task-origin details p {
  font-size: 0.75rem;
  margin-top: 0.75rem;
}
.task-panel-footer {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border);
  background: var(--popover);
}
.panel-primary-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}
.footer-hint {
  color: var(--muted-foreground);
  font-size: 0.7rem;
  margin-right: auto;
}
@media (max-width: 47.5rem) {
  .task-panel-header {
    padding: 1rem;
  }
  .task-panel-header :deep([data-slot="dialog-title"]) {
    font-size: 1rem;
  }
  .task-panel-body {
    padding: 1rem;
    gap: 1.25rem;
  }
  .task-panel-footer {
    padding: 0.85rem 1rem;
  }
  .task-form-grid {
    grid-template-columns: 1fr;
  }
  .review-compare {
    grid-template-columns: 1fr;
  }
  .footer-hint {
    display: none;
  }
  .panel-primary-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .task-facts {
    gap: 0.85rem;
  }
  .task-panel-footer :deep(button) {
    font-size: 0.75rem;
  }
}
</style>
