<script setup lang="ts">
import { Check, ChevronDown, CircleHelp, Plus } from "@lucide/vue";
import { computed, ref } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { actionItemDefaults, actionItemStatusFilters } from "@/data/mock";
const { actionItems, notify } = useWorkspace();
const filterStatus = ref("全部");
const filteredActionItems = computed(() =>
  filterStatus.value === "全部"
    ? actionItems
    : actionItems.filter((item) => item.status === filterStatus.value),
);
const filterLabel = computed(() =>
  ({
    全部: "全部状态",
    todo: "待处理",
    "in-progress": "进行中",
    done: "已完成",
  })[filterStatus.value] || "全部状态",
);
function cycleFilter() {
  filterStatus.value = actionItemStatusFilters[
    (actionItemStatusFilters.indexOf(filterStatus.value) + 1) % actionItemStatusFilters.length
  ]!;
}
function createActionItem() {
  const title = window.prompt("请输入行动项名称");
  if (!title?.trim()) return;
  actionItems.unshift({
    id: `action-local-${Date.now()}`,
    title: title.trim(),
    ...actionItemDefaults,
  });
  notify("行动项已创建");
}
function toggleActionItem(item: (typeof actionItems)[number]) {
  item.status = item.status === "done" ? "todo" : "done";
  notify(item.status === "done" ? "行动项已完成" : "行动项已重新打开");
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / FOLLOW-UP"
    title="行动项"
    subtitle="跟踪调研结论落地前仍需完成的工作"
    ><template #action
      ><button
        class="button button-primary"
        type="button"
        @click="createActionItem"
      >
        <Plus :size="17" />新建行动项
      </button></template
    ></PageHeader
  >
  <div class="action-summary">
    <div>
      <strong>{{
        actionItems.filter((item) => item.status !== "done").length
      }}</strong
      ><span>待完成</span>
    </div>
    <div>
      <strong>{{ actionItems.filter((item) => item.priority === "高").length }}</strong
      ><span>高优先级</span>
    </div>
    <button
      class="select-button"
      type="button"
      @click="cycleFilter"
    >
      {{ filterLabel }} <ChevronDown :size="14" />
    </button>
  </div>
  <section class="panel action-list">
    <div v-for="item in filteredActionItems" :key="item.id" class="action-row">
      <button
        class="action-check"
        :class="{ done: item.status === 'done' }"
        type="button"
        :aria-label="item.status === 'done' ? '重新打开行动项' : '完成行动项'"
        @click="toggleActionItem(item)"
      >
        <Check v-if="item.status === 'done'" :size="14" />
      </button>
      <div>
        <strong>{{ item.title }}</strong
        ><small>{{ item.owner }} · 截止 {{ item.due }}</small>
      </div>
      <span class="priority-badge" :class="`priority-${item.priority}`">{{
        item.priority
      }}</span
      ><CircleHelp
        v-if="item.status === 'in-progress'"
        :size="17"
        class="amber-text"
      /><button
        class="text-button"
        type="button"
        @click="toggleActionItem(item)"
      >
        {{ item.status === "done" ? "重新打开" : "完成" }}
      </button>
    </div>
  </section>
</template>
