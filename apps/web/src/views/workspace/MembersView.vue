<script setup lang="ts">
import { ChevronDown, MoreHorizontal, Plus } from "@lucide/vue";
import { computed, ref } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { memberInviteDefaults, memberRoleCycle, memberRoleFilters, workspaceMembers } from "@/data/mock";
const { notify } = useWorkspace();
const members = ref(workspaceMembers.map((member) => ({ ...member })));
const roleFilter = ref("全部");
const filteredMembers = computed(() =>
  roleFilter.value === "全部"
    ? members.value
    : members.value.filter((member) => member.role === roleFilter.value),
);
function cycleRoleFilter() {
  roleFilter.value = memberRoleFilters[
    (memberRoleFilters.indexOf(roleFilter.value) + 1) % memberRoleFilters.length
  ]!;
}
function inviteMember() {
  const email = window.prompt("请输入成员邮箱");
  if (!email?.includes("@")) return;
  const name = email.split("@")[0] || "新成员";
  members.value.push({
    name,
    email,
    role: memberInviteDefaults.role,
    date: memberInviteDefaults.date,
    active: memberInviteDefaults.active,
  });
  notify(`邀请已发送给 ${email}`);
}
function cycleMemberRole(member: (typeof members.value)[number]) {
  member.role = memberRoleCycle[(memberRoleCycle.indexOf(member.role) + 1) % memberRoleCycle.length]!;
  notify(`${member.name} 的角色已更新为 ${member.role}`);
}
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
        @click="inviteMember"
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
        @click="cycleRoleFilter"
      >
        {{ roleFilter === "全部" ? "全部角色" : roleFilter }}
        <ChevronDown :size="14" />
      </button>
    </div>
    <div class="data-table member-table">
      <div class="table-row table-header">
        <span>成员</span><span>角色</span><span>加入时间</span
        ><span>最后活跃</span><span />
      </div>
      <div
        v-for="(member, index) in filteredMembers"
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
          :aria-label="`更新成员角色：${member.name}`"
          @click="cycleMemberRole(member)"
        >
          <MoreHorizontal :size="17" />
        </button>
      </div>
    </div>
  </section>
</template>
