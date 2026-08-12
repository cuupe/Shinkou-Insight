<script setup lang="ts">
import { Check, ChevronDown, CircleHelp, Plus } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { actionItems, notify } = useWorkspace();
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
        @click="notify('新建行动项接口待接入')"
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
    <div><strong>2</strong><span>高优先级</span></div>
    <button
      class="select-button"
      type="button"
      @click="notify('行动项筛选接口待接入')"
    >
      全部状态 <ChevronDown :size="14" />
    </button>
  </div>
  <section class="panel action-list">
    <div v-for="item in actionItems" :key="item.id" class="action-row">
      <span class="action-check" :class="{ done: item.status === 'done' }"
        ><Check v-if="item.status === 'done'" :size="14"
      /></span>
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
        @click="notify('行动项编辑接口待接入')"
      >
        查看
      </button>
    </div>
  </section>
</template>
