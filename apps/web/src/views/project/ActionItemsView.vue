<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  AlertCircle,
  ArrowRight,
  CalendarDays,
  Check,
  CheckCircle2,
  CircleDot,
  Clock3,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  UserRound,
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
import { useWorkspace } from "@/composables/useWorkspace";
import { actionItemsApi } from "@/api/action-items";
import { workspaceApi } from "@/api/workspace";
import type { WorkspaceMember } from "@/api/types";

const { actionItems, notify, workspaceId, projectId } = useWorkspace();
const items = reactive(actionItems);
const searchQuery = ref("");
const filterStatus = ref("全部");
const filterPriority = ref("全部");
const itemDialogOpen = ref(false);
const editingItemId = ref<string | null>(null);
const owners = ref<WorkspaceMember[]>([]);

onMounted(async () => {
  try {
    const members = await workspaceApi.members(workspaceId.value);
    owners.value = members.filter((member) => member.userName);
  } catch {
    owners.value = [];
  }
});
const priorityOptions = ["全部", "高", "中", "低"];
const filterLabelMap: Record<string, string> = {
  全部: "全部状态",
  todo: "待处理",
  "in-progress": "进行中",
  done: "已完成",
};
const statusColumns = [
  {
    value: "todo",
    label: "待处理",
    detail: "已确认，等待推进",
    tone: "slate",
    icon: CircleDot,
  },
  {
    value: "in-progress",
    label: "进行中",
    detail: "团队正在处理",
    tone: "amber",
    icon: Clock3,
  },
  {
    value: "done",
    label: "已完成",
    detail: "已经完成并归档",
    tone: "teal",
    icon: CheckCircle2,
  },
] as const;

const actionForm = reactive({
  title: "",
  owner: "",
  due: "",
  priority: "中",
  status: "todo",
});
const actionItemStatusFilters = ["全部", "todo", "in-progress", "done"];

const filteredActionItems = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return items.filter((item) => {
    const matchesStatus =
      filterStatus.value === "全部" || item.status === filterStatus.value;
    const matchesPriority =
      filterPriority.value === "全部" || item.priority === filterPriority.value;
    const matchesQuery =
      !query ||
      [item.title, item.owner, item.due]
        .join(" ")
        .toLowerCase()
        .includes(query);
    return matchesStatus && matchesPriority && matchesQuery;
  });
});

const pendingCount = computed(
  () => items.filter((item) => item.status !== "done").length,
);
const inProgressCount = computed(
  () => items.filter((item) => item.status === "in-progress").length,
);
const highPriorityCount = computed(
  () =>
    items.filter((item) => item.priority === "高" && item.status !== "done")
      .length,
);
const completedCount = computed(
  () => items.filter((item) => item.status === "done").length,
);
const dialogTitle = computed(() =>
  editingItemId.value ? "编辑行动项" : "新建行动项",
);

function itemsForStatus(status: string) {
  return filteredActionItems.value.filter((item) => item.status === status);
}

function resetForm() {
  Object.assign(actionForm, {
    title: "",
    owner: owners.value[0]?.userName || "",
    due: "",
    priority: "中",
    status: "todo",
  });
}

function openCreateDialog() {
  editingItemId.value = null;
  resetForm();
  itemDialogOpen.value = true;
}

function openEditDialog(item: (typeof items)[number]) {
  editingItemId.value = item.id;
  Object.assign(actionForm, {
    title: item.title,
    owner: item.owner,
    due: item.due,
    priority: item.priority,
    status: item.status,
  });
  itemDialogOpen.value = true;
}

async function saveActionItem() {
  if (!actionForm.title.trim()) return;
  if (editingItemId.value) {
    const item = items.find(
      (candidate) => candidate.id === editingItemId.value,
    );
    if (!item) return;
    try {
      await actionItemsApi.update(
        workspaceId.value,
        projectId.value,
        editingItemId.value,
        {
          title: actionForm.title.trim(),
          ownerId: owners.value.find((owner) => owner.userName === actionForm.owner)?.userId,
          dueAt: actionForm.due || null,
          status: actionForm.status,
          priority: actionForm.priority,
        },
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : "行动项保存失败");
      return;
    }
    Object.assign(item, { ...actionForm, title: actionForm.title.trim() });
    notify("行动项已更新");
  } else {
    try {
      const created = await actionItemsApi.create(
        workspaceId.value,
        projectId.value,
        {
          title: actionForm.title.trim(),
          ownerId: owners.value.find((owner) => owner.userName === actionForm.owner)?.userId,
          dueAt: actionForm.due || null,
          status: actionForm.status,
          priority: actionForm.priority,
        },
      );
      items.unshift({
        id: String(created.id),
        ...actionForm,
        title: created.title || actionForm.title.trim(),
      });
    } catch (error) {
      notify(error instanceof Error ? error.message : "行动项创建失败");
      return;
    }
    notify("行动项已创建");
  }
  itemDialogOpen.value = false;
}

async function advanceItem(item: (typeof items)[number]) {
  const nextStatus: Record<string, string> = {
    todo: "in-progress",
    "in-progress": "done",
    done: "todo",
  };
  const next = nextStatus[item.status] || "todo";
  try {
    await actionItemsApi.update(workspaceId.value, projectId.value, item.id, {
      status: next,
    });
  } catch (error) {
    notify(error instanceof Error ? error.message : "行动项状态保存失败");
    return;
  }
  item.status = next;
  notify(
    item.status === "done"
      ? "行动项已完成"
      : item.status === "in-progress"
        ? "行动项已开始处理"
        : "行动项已重新打开",
  );
}

function advanceLabel(status: string) {
  return status === "todo"
    ? "开始处理"
    : status === "in-progress"
      ? "标记完成"
      : "重新打开";
}

function priorityClass(priority: string) {
  return `priority-${priority === "高" ? "high" : priority === "中" ? "medium" : "low"}`;
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / FOLLOW-UP"
    title="行动项"
    subtitle="跟踪调研结论落地前仍需完成的工作"
  >
    <template #action
      ><button
        class="button button-primary"
        type="button"
        @click="openCreateDialog"
      >
        <Plus :size="16" />新建行动项
      </button></template
    >
  </PageHeader>

  <div class="action-summary">
    <div class="action-summary-card">
      <span class="summary-icon teal-bg"><CheckCircle2 :size="16" /></span>
      <div>
        <strong>{{ pendingCount }}</strong
        ><span>待完成</span>
      </div>
      <small>需要继续推进</small>
    </div>
    <div class="action-summary-card">
      <span class="summary-icon violet-bg"><Clock3 :size="16" /></span>
      <div>
        <strong>{{ inProgressCount }}</strong
        ><span>进行中</span>
      </div>
      <small>正在处理</small>
    </div>
    <div class="action-summary-card">
      <span class="summary-icon amber-bg"><AlertCircle :size="16" /></span>
      <div>
        <strong>{{ highPriorityCount }}</strong
        ><span>高优先级</span>
      </div>
      <small>需要优先确认</small>
    </div>
    <div class="action-summary-card">
      <span class="summary-icon blue-bg"><Check :size="16" /></span>
      <div>
        <strong>{{ completedCount }}</strong
        ><span>已完成</span>
      </div>
      <small>已归档事项</small>
    </div>
  </div>

  <div class="action-toolbar">
    <label class="search-control"
      ><Search :size="15" /><input
        v-model="searchQuery"
        type="search"
        placeholder="搜索行动项、负责人或截止日期"
        aria-label="搜索行动项"
    /></label>
    <div class="toolbar-filters">
      <SlidersHorizontal :size="14" /><span>筛选</span>
      <select v-model="filterStatus" aria-label="筛选行动项状态">
        <option
          v-for="filter in actionItemStatusFilters"
          :key="filter"
          :value="filter"
        >
          {{ filterLabelMap[filter] }}
        </option>
      </select>
      <select v-model="filterPriority" aria-label="筛选行动项优先级">
        <option
          v-for="priority in priorityOptions"
          :key="priority"
          :value="priority"
        >
          {{ priority === "全部" ? "全部优先级" : `${priority}优先级` }}
        </option>
      </select>
    </div>
  </div>

  <section class="action-board">
    <article
      v-for="column in statusColumns"
      :key="column.value"
      class="action-column"
    >
      <header class="action-column-header">
        <div>
          <h2>
            <span class="column-dot" :class="`dot-${column.tone}`" />{{
              column.label
            }}
            <b>{{ itemsForStatus(column.value).length }}</b>
          </h2>
          <p>{{ column.detail }}</p>
        </div>
        <component
          :is="column.icon"
          :size="16"
          :class="`column-icon ${column.tone}-text`"
        />
      </header>
      <div class="action-card-list">
        <article
          v-for="item in itemsForStatus(column.value)"
          :key="item.id"
          class="action-card"
          :class="{ 'action-card-done': item.status === 'done' }"
        >
          <div class="action-card-top">
            <span class="priority-badge" :class="priorityClass(item.priority)"
              >{{ item.priority }}优先级</span
            ><button
              class="card-edit"
              type="button"
              :aria-label="`编辑${item.title}`"
              @click="openEditDialog(item)"
            >
              <Pencil :size="13" />
            </button>
          </div>
          <h3>{{ item.title }}</h3>
          <div class="action-card-meta">
            <span><UserRound :size="13" />{{ item.owner }}</span
            ><span :class="{ 'due-highlight': item.due === '今天' }"
              ><CalendarDays :size="13" />{{ item.due }}</span
            >
          </div>
          <div class="action-card-footer">
            <button
              class="card-detail-button"
              type="button"
              @click="openEditDialog(item)"
            >
              查看详情</button
            ><button
              class="card-action-button"
              type="button"
              @click="advanceItem(item)"
            >
              {{ advanceLabel(item.status) }}<ArrowRight :size="13" />
            </button>
          </div>
        </article>
        <div v-if="!itemsForStatus(column.value).length" class="empty-column">
          <component :is="column.icon" :size="18" /><span>{{
            filteredActionItems.length ? "暂无匹配项" : "没有行动项"
          }}</span>
        </div>
      </div>
      <button class="add-card-button" type="button" @click="openCreateDialog">
        <Plus :size="14" />添加行动项
      </button>
    </article>
  </section>

  <Dialog v-model:open="itemDialogOpen">
    <DialogContent class="action-editor-dialog">
      <DialogHeader
        ><DialogTitle>{{ dialogTitle }}</DialogTitle
        ><DialogDescription
          >明确负责人和截止时间，让调研结论更容易落地。</DialogDescription
        ></DialogHeader
      >
      <div class="editor-form">
        <label
          >行动项名称<input
            v-model="actionForm.title"
            type="text"
            placeholder="例如：确认跨地域复制的 RPO 目标"
        /></label>
        <div class="form-grid">
          <label
            >负责人<select v-model="actionForm.owner">
              <option v-for="owner in owners" :key="owner.userId || owner.id" :value="owner.userName">
                {{ owner.userName }}
              </option>
            </select></label
          ><label
            >截止时间<input
              v-model="actionForm.due"
              type="date"
          /></label>
        </div>
        <div class="form-grid">
          <label
            >优先级<select v-model="actionForm.priority">
              <option value="高">高优先级</option>
              <option value="中">中优先级</option>
              <option value="低">低优先级</option>
            </select></label
          ><label
            >状态<select v-model="actionForm.status">
              <option value="todo">待处理</option>
              <option value="in-progress">进行中</option>
              <option value="done">已完成</option>
            </select></label
          >
        </div>
      </div>
      <DialogFooter
        ><button
          class="button button-secondary"
          type="button"
          @click="itemDialogOpen = false"
        >
          取消</button
        ><button
          class="button button-primary"
          type="button"
          @click="saveActionItem"
        >
          保存行动项
        </button></DialogFooter
      >
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.blue-bg {
  color: #4b86c8;
  background: #e8f2fd;
}
.action-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.125rem;
}
.action-summary-card {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 0.625rem;
  align-items: center;
  padding: 0.875rem 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.6875rem;
  background: var(--surface);
}
.summary-icon {
  display: grid;
  grid-row: span 2;
  place-items: center;
  width: 1.9375rem;
  height: 1.9375rem;
  border-radius: 0.5rem;
}
.action-summary-card > div {
  display: flex;
  align-items: baseline;
  gap: 0.375rem;
}
.action-summary-card strong {
  color: var(--workspace-text);
  font-size: 1.125rem;
  letter-spacing: -0.04em;
}
.action-summary-card span:not(.summary-icon) {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.action-summary-card small {
  grid-column: 2;
  margin-top: 0.125rem;
  color: var(--workspace-subtle);
  font-size: 0.5rem;
}
.action-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.875rem;
}
.search-control {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  min-width: 14rem;
  flex: 1;
  max-width: 26rem;
  padding: 0 0.625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  color: var(--workspace-muted);
  background: var(--surface);
}
.search-control:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 16%, transparent);
}
.search-control input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  padding: 0.5625rem 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.625rem;
}
.search-control input::placeholder {
  color: var(--workspace-subtle);
}
.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
  color: var(--workspace-muted);
  font-size: 0.625rem;
}
.toolbar-filters select,
.editor-form select {
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  outline: 0;
  padding: 0.5rem 1.75rem 0.5rem 0.625rem;
  background: var(--surface);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.625rem;
}
.toolbar-filters select:focus,
.editor-form select:focus {
  border-color: var(--teal);
}
.action-board {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.875rem;
  align-items: start;
}
.action-column {
  min-width: 0;
  padding: 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;
  background: color-mix(in oklab, var(--surface-soft) 80%, var(--surface));
}
.action-column-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 3rem;
  padding: 0.125rem 0.125rem 0.75rem;
}
.action-column-header h2 {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.action-column-header h2 b {
  display: inline-grid;
  place-items: center;
  min-width: 1.25rem;
  height: 1.125rem;
  border-radius: 0.3125rem;
  background: var(--surface);
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.action-column-header p {
  margin: 0.3125rem 0 0 0.8125rem;
  color: var(--workspace-subtle);
  font-size: 0.5625rem;
}
.column-dot {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 999px;
  background: var(--workspace-muted);
}
.dot-amber {
  background: var(--amber);
}
.dot-teal {
  background: var(--teal);
}
.dot-slate {
  background: #8d9aa0;
}
.amber-text {
  color: var(--amber) !important;
}
.teal-text {
  color: var(--teal-dark) !important;
}
.slate-text {
  color: var(--workspace-muted) !important;
}
.action-card-list {
  display: grid;
  gap: 0.625rem;
}
.action-card {
  padding: 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface);
  box-shadow: 0 0.25rem 0.75rem rgba(21, 53, 52, 0.035);
  transition:
    transform 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}
.action-card:hover {
  transform: translateY(-0.125rem);
  border-color: color-mix(in oklab, var(--teal) 38%, var(--workspace-border));
  box-shadow: 0 0.625rem 1.25rem rgba(21, 53, 52, 0.07);
}
.action-card-done {
  opacity: 0.72;
}
.action-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.priority-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.5rem;
}
.priority-high {
  color: #bd5f5f;
  background: #fff0ef;
}
.priority-medium {
  color: #af7a26;
  background: #fff4df;
}
.priority-low {
  color: #71898c;
  background: #f0f4f4;
}
.card-edit {
  display: grid;
  place-items: center;
  width: 1.625rem;
  height: 1.625rem;
  border: 0;
  border-radius: 0.375rem;
  background: transparent;
  color: var(--workspace-subtle);
  cursor: pointer;
}
.card-edit:hover {
  color: var(--teal-dark);
  background: var(--surface-soft);
}
.action-card h3 {
  margin: 0.875rem 0;
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
  line-height: 1.5;
}
.action-card-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.action-card-meta span {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}
.due-highlight {
  color: var(--amber);
}
.action-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-top: 0.875rem;
  padding-top: 0.6875rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}
.card-detail-button,
.card-action-button {
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 0.5625rem;
  cursor: pointer;
}
.card-detail-button {
  padding: 0.25rem 0;
  color: var(--workspace-muted);
}
.card-detail-button:hover {
  color: var(--workspace-text);
}
.card-action-button {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.3125rem 0.4375rem;
  border-radius: 0.3125rem;
  color: var(--teal-dark);
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
}
.card-action-button:hover {
  background: color-mix(in oklab, var(--teal) 17%, var(--surface));
}
.empty-column {
  display: grid;
  place-items: center;
  gap: 0.375rem;
  min-height: 7.5rem;
  color: var(--workspace-subtle);
  font-size: 0.5625rem;
}
.add-card-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.3125rem;
  width: 100%;
  margin-top: 0.625rem;
  padding: 0.5rem;
  border: 0.0625rem dashed var(--workspace-border);
  border-radius: 0.4375rem;
  background: transparent;
  color: var(--workspace-muted);
  font: inherit;
  font-size: 0.5625rem;
  cursor: pointer;
}
.add-card-button:hover {
  border-color: var(--teal);
  color: var(--teal-dark);
  background: color-mix(in oklab, var(--teal) 5%, var(--surface));
}
.action-editor-dialog {
  max-width: 38rem !important;
}
.editor-form {
  display: grid;
  gap: 0.875rem;
}
.editor-form label {
  display: grid;
  gap: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.625rem;
}
.editor-form input,
.editor-form select {
  width: 100%;
  box-sizing: border-box;
}
.editor-form input {
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  outline: 0;
  padding: 0.625rem 0.6875rem;
  background: var(--surface-soft);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.6875rem;
}
.editor-form input:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 16%, transparent);
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
@media (max-width: 68.75rem) {
  .action-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .action-board {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 47.5rem) {
  .action-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .search-control {
    max-width: none;
  }
  .toolbar-filters {
    flex-wrap: wrap;
  }
  .toolbar-filters select {
    flex: 1;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 30rem) {
  .action-summary {
    grid-template-columns: 1fr;
  }
  .action-card-meta {
    flex-wrap: wrap;
  }
}
</style>
