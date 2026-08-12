<script setup lang="ts">
import { ChevronDown, MoreHorizontal, Plus } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { ref } from "vue";
const { notify } = useWorkspace();
const members = ref([
  {
    name: "林默",
    email: "lin.mo@shinkou.ai",
    role: "OWNER",
    date: "2026/06/12",
    active: "刚刚",
  },
  {
    name: "周然",
    email: "ran.zhou@shinkou.ai",
    role: "ADMIN",
    date: "2026/06/14",
    active: "12 分钟前",
  },
  {
    name: "陈雪",
    email: "xue.chen@shinkou.ai",
    role: "MEMBER",
    date: "2026/07/03",
    active: "今天 09:32",
  },
  {
    name: "顾言",
    email: "yan.gu@shinkou.ai",
    role: "MEMBER",
    date: "2026/07/18",
    active: "昨天",
  },
]);
</script>

<template>
  <PageHeader
    eyebrow="WORKSPACE / ACCESS"
    title="成员与权限"
    subtitle="控制谁可以访问工作区和项目"
    ><template #action
      ><button
        class="button button-primary"
        type="button"
        @click="notify('邀请成员接口待接入')"
      >
        <Plus :size="17" />邀请成员
      </button></template
    ></PageHeader
  >
  <section class="panel table-panel">
    <div class="panel-heading">
      <div>
        <h2>
          工作区成员 <span class="count-chip">{{ members.length }}</span>
        </h2>
        <p>所有成员默认可以查看工作区概览。</p>
      </div>
      <button
        class="select-button"
        type="button"
        @click="notify('成员筛选接口待接入')"
      >
        全部角色 <ChevronDown :size="14" />
      </button>
    </div>
    <div class="data-table member-table">
      <div class="table-row table-header">
        <span>成员</span><span>角色</span><span>加入时间</span
        ><span>最后活跃</span><span />
      </div>
      <div
        v-for="(member, index) in members"
        :key="member.email"
        class="table-row"
      >
        <div class="member-cell">
          <span class="member-avatar" :class="`member-color-${index}`">{{
            member.name.slice(0, 1)
          }}</span
          ><span
            ><strong>{{ member.name }}</strong
            ><small>{{ member.email }}</small></span
          >
        </div>
        <span class="role-badge">{{ member.role }}</span
        ><span class="muted-cell">{{ member.date }}</span
        ><span class="muted-cell">{{ member.active }}</span
        ><button
          class="icon-button small"
          type="button"
          @click="notify('成员操作接口待接入')"
        >
          <MoreHorizontal :size="17" />
        </button>
      </div>
    </div>
  </section>
</template>
