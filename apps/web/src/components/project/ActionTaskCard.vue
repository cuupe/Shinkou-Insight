<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowRight,
  CalendarDays,
  FileText,
  ShieldCheck,
  UserRound,
} from "@lucide/vue";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  actionCommand,
  actionDue,
  actionStatusLabel,
  isActionVerified,
  type ActionRow,
} from "@/utils/actionWorkflow";

const props = withDefaults(
  defineProps<{
    item: ActionRow;
    view?: "board" | "list";
    saving?: boolean;
    showSource?: boolean;
  }>(),
  { view: "board", saving: false, showSource: true },
);
const emit = defineEmits<{
  open: [ActionRow];
  advance: [ActionRow];
  source: [ActionRow, boolean?];
}>();
const next = computed(() =>
  isActionVerified(props.item) ? null : actionCommand(props.item),
);
const due = computed(() => actionDue(props.item));
const verified = computed(() => isActionVerified(props.item));
const code = computed(() =>
  props.item.sourceKey?.startsWith("item:")
    ? props.item.sourceKey.slice(5).toUpperCase()
    : "",
);
</script>

<template>
  <Card
    class="action-card"
    :class="{ 'action-card-done': verified }"
    :data-view="view"
    :data-status="item.status"
  >
    <CardHeader class="task-card-heading">
      <div class="task-tags">
        <span v-if="code" class="task-code">{{ code }}</span
        ><Badge v-if="item.status === 'rejected'" variant="destructive"
          >退回修改</Badge
        ><Badge
          v-else-if="item.status === 'done' && !verified"
          variant="outline"
          >待补验收</Badge
        ><Badge variant="outline">{{ item.priority }}优先级</Badge
        ><span
          v-if="item.blocksRelease !== false"
          class="task-release"
          title="发布前必须验收关闭"
          ><ShieldCheck :size="12" />发布前置</span
        >
      </div>
      <CardTitle
        ><h3>
          <button type="button" :title="item.title" @click="emit('open', item)">
            {{ item.title }}
          </button>
        </h3></CardTitle
      >
    </CardHeader>
    <CardContent class="task-card-content">
      <span v-if="view === 'list'" class="task-status">{{
        actionStatusLabel(item)
      }}</span>
      <span class="task-owner" :title="'负责人：' + item.owner"
        ><UserRound :size="13" /><span>{{ item.owner }}</span></span
      >
      <span
        class="task-due"
        :class="{ 'is-overdue': due.overdue, 'is-today': due.today }"
        :title="due.full"
        ><CalendarDays :size="13" /><time
          v-if="item.dueAt"
          :datetime="item.dueAt"
          >{{ due.label }}</time
        ><span v-else>{{ due.label }}</span
        ><small v-if="due.overdue">逾期</small></span
      >
      <p
        v-if="item.status === 'rejected' && item.acceptanceComment"
        class="task-return-note"
      >
        退回原因：{{ item.acceptanceComment }}
      </p>
      <p v-if="showSource && item.sourceReportId" class="action-source">
        <button
          type="button"
          :title="item.sourceReportTitle || '关联报告'"
          :aria-label="
            '打开来源报告：' + (item.sourceReportTitle || '关联报告')
          "
          @click="emit('source', item)"
        >
          <FileText :size="12" /><span>{{
            item.sourceReportTitle || "关联报告"
          }}</span>
        </button>
      </p>
    </CardContent>
    <CardFooter class="task-card-footer"
      ><Button
        class="card-detail-button"
        variant="ghost"
        size="sm"
        @click="emit('open', item)"
        >查看详情</Button
      ><Button
        v-if="next"
        class="card-action-button"
        :variant="next.command === 'accept' ? 'default' : 'outline'"
        size="sm"
        :disabled="saving"
        @click="emit('advance', item)"
        >{{ next.label }}<ArrowRight data-icon="inline-end" /></Button
    ></CardFooter>
  </Card>
</template>

<style scoped>
.action-card {
  min-width: 0;
  flex-shrink: 0;
}
.action-card:focus-within {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}
.task-tags {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-bottom: 0.35rem;
}
.task-code {
  font-size: 0.7rem;
  color: var(--workspace-subtle);
  font-weight: 600;
  letter-spacing: 0.04em;
}
.task-release {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-left: auto;
  font-size: 0.67rem;
  color: var(--workspace-subtle);
}
h3 {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.65;
  font-weight: 600;
}
h3 button {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  overflow-wrap: anywhere;
}
h3 button:hover {
  text-decoration: underline;
  text-underline-offset: 0.2em;
}
h3 button:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 3px;
  border-radius: 0.2rem;
}
.task-card-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}
.task-owner,
.task-due {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  min-width: 0;
}
.task-owner > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-owner svg,
.task-due svg {
  flex-shrink: 0;
}
.task-due {
  justify-content: flex-end;
  white-space: nowrap;
}
.task-due small {
  font-size: 0.65rem;
}
.task-due.is-overdue {
  color: var(--destructive);
}
.task-due.is-today {
  color: var(--teal-dark);
}
.task-status {
  font-size: 0.75rem;
  color: var(--workspace-muted);
  white-space: nowrap;
}
.task-return-note {
  grid-column: 1/-1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.7;
  color: var(--destructive);
  overflow-wrap: anywhere;
}
.action-source {
  grid-column: 1/-1;
  margin: 0;
  min-width: 0;
}
.action-source button {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  max-width: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--workspace-subtle);
  font-size: 0.7rem;
  text-align: left;
  cursor: pointer;
}
.action-source span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.action-source svg {
  flex-shrink: 0;
}
.action-source button:hover {
  color: var(--teal-dark);
}
.task-card-footer {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.65rem 0.75rem;
}
.action-card[data-view="list"] {
  display: grid;
  grid-template-columns: minmax(13rem, 1fr) minmax(20rem, 0.9fr) auto;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: 0;
  box-shadow: none;
  border-bottom: 1px solid var(--workspace-border);
  overflow: visible;
}
[data-view="list"] .task-card-heading,
[data-view="list"] .task-card-content,
[data-view="list"] .task-card-footer {
  padding: 0;
}
[data-view="list"] .task-card-content {
  grid-template-columns: 5.5rem minmax(5rem, 1fr) 7.5rem;
  gap: 0.6rem 1rem;
}
[data-view="list"] .task-card-footer {
  background: transparent;
  border: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}
[data-view="list"] .task-return-note,
[data-view="list"] .action-source {
  grid-column: 1/-1;
}
@media (max-width: 80rem) {
  .action-card[data-view="list"] {
    grid-template-columns: minmax(12rem, 1fr) minmax(15rem, 1fr);
  }
  [data-view="list"] .task-card-footer {
    grid-column: 1/-1;
  }
}
@media (max-width: 47.5rem) {
  .action-card[data-view="list"] {
    display: flex;
    align-items: stretch;
    gap: 0.85rem;
    padding: 1rem;
    border: 1px solid var(--workspace-border);
    border-radius: 0.75rem;
  }
  [data-view="list"] .task-card-content {
    grid-template-columns: 1fr auto;
  }
  [data-view="list"] .task-status {
    grid-column: 1/-1;
  }
  [data-view="list"] .task-card-footer {
    justify-content: space-between;
  }
  .task-release {
    font-size: 0.65rem;
  }
}
</style>
