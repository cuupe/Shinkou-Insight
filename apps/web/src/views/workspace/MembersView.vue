<script setup lang="ts">
import { Plus, Users } from "@lucide/vue";
import { computed, ref, watch } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import SearchField from "@/components/common/SearchField.vue";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dateFormatWithseconds } from "@/lib/utils";
import { useWorkspace } from "@/composables/useWorkspace";
import { workspaceApi } from "@/api/workspace";
import { getApiErrorMessage } from "@/api/core";
const { notify, workspaceId, currentUser } = useWorkspace();
type MemberRow = {
  id?: number | string;
  userId?: number | string;
  name: string;
  phone: string;
  department: string;
  title: string;
  inviteNote: string;
  role: string;
  date: string;
  active: string;
};
const members = ref<MemberRow[]>([]);
const roleFilter = ref("全部");
const searchQuery = ref("");
const inviteOpen = ref(false);
const invitePhone = ref("");
const inviteDepartment = ref("");
const inviteTitle = ref("");
const inviteNote = ref("");
const inviteRole = ref("MEMBER");
const inviteError = ref("");
const loading = ref(false);
const loadError = ref("");
let loadRequestActive = false;
const roleOptions = ["OWNER", "ADMIN", "MEMBER"];
function memberDisplayFields(member: { department?: string; title?: string }) {
  return {
    department: member.department || "暂无",
    title: member.title || "暂无",
  };
}
function memberActivityFields(member: { lastActiveAt?: string; status?: string }) {
  return {
    active: member.lastActiveAt
      ? String(dateFormatWithseconds(
          currentUser.value?.timezone || "Asia/Shanghai",
          new Date(member.lastActiveAt),
        ) || "暂无")
      : member.status || "暂无",
  };
}
async function loadMembers() {
  if (!workspaceId.value || workspaceId.value === "-1" || loadRequestActive) return;
  loadRequestActive = true;
  loading.value = true;
  loadError.value = "";
  try {
    const remoteMembers = await workspaceApi.members(workspaceId.value);
    members.value = remoteMembers.map((member) => ({
      name: member.userName || "未命名成员",
      id: member.id,
      userId: member.userId,
      phone: member.phoneNumber || "—",
      department: "—",
      title: "—",
      ...(memberDisplayFields(member) as unknown as Record<string, never>), /*
        department: member.department || "暂无",
        title: member.title || "暂无",
      },
      */ inviteNote: "",
      role: member.role || "MEMBER",
      date:
        dateFormatWithseconds(
          currentUser.value?.timezone || "Asia/Shanghai",
          new Date(member.createdAt),
        ) || "—",
      active: member.status || "—",
      ...(memberActivityFields(member) as unknown as Record<string, never>), /*
        active: member.lastActiveAt
          ? dateFormatWithseconds(
              currentUser.value?.timezone || "Asia/Shanghai",
              new Date(member.lastActiveAt),
            )
          : member.status || "暂无",
      },
    */ }));
  } catch (error) {
    loadError.value = getApiErrorMessage(error, "成员列表加载失败，请稍后重试");
  } finally {
    loading.value = false;
    loadRequestActive = false;
  }
}
watch(workspaceId, (value) => {
  if (value && value !== "-1") void loadMembers();
}, { immediate: true });
function isCurrentUser(member: (typeof members.value)[number]) {
  const me = currentUser.value;
  if (!me) return false;
  if (member.userId != null && String(member.userId) === String(me.id))
    return true;
  return Boolean(member.phone) && member.phone === me.phoneNumber;
}
const currentUserRole = computed(
  () => members.value.find((member) => isCurrentUser(member))?.role || "MEMBER",
);
const canManageMembers = computed(() =>
  ["OWNER", "ADMIN"].includes(currentUserRole.value),
);
const assignableRoles = computed(() =>
  currentUserRole.value === "OWNER" ? ["ADMIN", "MEMBER"] : ["MEMBER"],
);
const activeCount = computed(
  () => members.value.filter((member) => member.active !== "待接受邀请").length,
);
const pendingCount = computed(
  () => members.value.filter((member) => member.active === "待接受邀请").length,
);
const filteredMembers = computed(() =>
  members.value.filter((member) => {
    const keyword = searchQuery.value.trim().toLowerCase();
    const matchesSearch =
      !keyword ||
      member.name.toLowerCase().includes(keyword) ||
      member.phone.toLowerCase().includes(keyword) ||
      member.department.toLowerCase().includes(keyword) ||
      member.title.toLowerCase().includes(keyword);
    const matchesRole =
      roleFilter.value === "全部" || member.role === roleFilter.value;
    return matchesSearch && matchesRole;
  }),
);
function openInviteDialog() {
  if (!canManageMembers.value) {
    notify("只有工作区所有者或管理员可以邀请成员");
    return;
  }
  invitePhone.value = "";
  inviteDepartment.value = "";
  inviteTitle.value = "";
  inviteNote.value = "";
  inviteRole.value = "MEMBER";
  inviteError.value = "";
  inviteOpen.value = true;
}
async function inviteMember() {
  if (!canManageMembers.value) return;
  const phone = invitePhone.value.trim();
  const department = inviteDepartment.value.trim();
  const title = inviteTitle.value.trim();
  const note = inviteNote.value.trim();
  if (!/^1\d{10}$/.test(phone)) {
    inviteError.value = "请输入正确的 11 位手机号，邀请将通过短信发送";
    return;
  }
  if (department.length < 2 || title.length < 2) {
    inviteError.value = "请补充对方的部门和职位，便于确认权限范围";
    return;
  }
  if (note.length < 5) {
    inviteError.value = "请填写至少 5 个字的邀请说明";
    return;
  }
  if (members.value.some((member) => member.phone === phone)) {
    inviteError.value = "该手机号已经在成员列表中";
    return;
  }
  if (!assignableRoles.value.includes(inviteRole.value)) {
    inviteError.value = "当前账号没有分配该角色的权限";
    return;
  }
  try {
    await workspaceApi.invite(workspaceId.value, {
      phoneNumber: phone,
      role: inviteRole.value,
      department,
      title,
      inviteNote: note,
    });
  } catch (error) {
    inviteError.value = error instanceof Error ? error.message : "邀请发送失败";
    return;
  }
  await loadMembers();
  notify(`已向手机号 ${phone} 发送邀请`);
  inviteOpen.value = false;
}
async function updateMemberRole(
  member: (typeof members.value)[number],
  nextRole: unknown,
) {
  if (
    !canEditRole(member) ||
    typeof nextRole !== "string" ||
    !assignableRoles.value.includes(nextRole)
  ) {
    notify("当前账号没有修改该成员权限的权限");
    return;
  }
  if (member.role === nextRole) return;
  try {
    await workspaceApi.updateMemberRole(
      workspaceId.value,
      member.id || "",
      nextRole,
    );
  } catch (error) {
    notify(error instanceof Error ? error.message : "成员角色保存失败");
    return;
  }
  member.role = nextRole;
  notify(`${member.name} 的角色已更新为 ${nextRole}`);
}
function canEditRole(member: (typeof members.value)[number]) {
  if (!canManageMembers.value || isCurrentUser(member)) return false;
  if (currentUserRole.value === "OWNER") return member.role !== "OWNER";
  return member.role === "MEMBER";
}
function memberRoleOptions(member: (typeof members.value)[number]) {
  return canEditRole(member) ? assignableRoles.value : [member.role];
}
</script>

<template>
  <PageHeader
    eyebrow="WORKSPACE / ACCESS"
    title="成员与权限"
    subtitle="控制谁可以访问工作区和项目"
    ><template #action
      ><button
        v-if="canManageMembers"
        class="button button-primary"
        type="button"
        @click="openInviteDialog"
      >
        <Plus :size="17" />邀请成员</button
      ><span v-else class="permission-hint"
        >仅所有者或管理员可管理成员</span
      ></template
    ></PageHeader
  >
  <section class="panel table-panel members-panel">
    <div class="member-summary">
      <div>
        <span>成员总数</span><strong>{{ members.length }}</strong>
      </div>
      <div>
        <span>已激活</span><strong>{{ activeCount }}</strong>
      </div>
      <div>
        <span>待接受邀请</span><strong>{{ pendingCount }}</strong>
      </div>
    </div>
    <div class="panel-heading members-heading">
      <div>
        <h2>
          工作区成员 <span class="count-chip">{{ members.length }}</span>
        </h2>
        <p>所有成员默认可以查看工作区概览。</p>
      </div>
      <div class="members-toolbar">
        <SearchField
          v-model="searchQuery"
          placeholder="搜索姓名、手机号或部门…"
          aria-label="搜索姓名、手机号或部门"
        />
        <Select v-model="roleFilter">
          <SelectTrigger class="member-filter-select" aria-label="筛选成员角色">
            <SelectValue placeholder="全部角色" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="全部">全部角色</SelectItem>
            <SelectItem v-for="role in roleOptions" :key="role" :value="role">
              {{ role }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
    <div v-if="loading && !members.length" class="member-load-state" role="status">
      <Users :size="20" />
      <strong>正在读取成员列表</strong>
      <span>正在同步当前工作区的成员与权限。</span>
    </div>
    <div v-else-if="loadError" class="member-load-state member-load-error" role="alert">
      <Users :size="20" />
      <strong>{{ loadError }}</strong>
      <span>请确认当前会话有效，或稍后重新加载。</span>
      <button class="button button-secondary button-compact" type="button" @click="loadMembers">重新加载</button>
    </div>
    <div v-else class="data-table member-table">
      <div class="table-row table-header">
        <span>成员 / 手机号</span><span>部门 / 职位</span><span>角色</span
        ><span>加入时间</span><span>最后活跃</span>
      </div>
      <div
        v-for="member in filteredMembers"
        :key="member.phone"
        class="table-row"
      >
        <div class="member-cell">
          <span
            ><strong>{{ member.name }}</strong
            ><small>{{ member.phone }}</small></span
          >
        </div>
        <div class="member-org">
          <strong>{{ member.department }}</strong>
          <small>{{ member.title }}</small>
        </div>
        <Select
          v-if="canEditRole(member)"
          :model-value="member.role"
          @update:model-value="(value) => updateMemberRole(member, value)"
        >
          <SelectTrigger
            class="member-role-select"
            :aria-label="`更新${member.name}的角色`"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="role in memberRoleOptions(member)"
              :key="role"
              :value="role"
            >
              {{ role }}
            </SelectItem>
          </SelectContent>
        </Select>
        <span
          v-else
          class="role-readonly"
          :title="`当前账号不能修改${member.name}的角色`"
        >
          {{ member.role }} </span
        ><span class="muted-cell">{{ member.date }}</span
        ><span class="muted-cell member-active-cell">{{ member.active }}</span>
      </div>
    </div>
    <div v-if="!loading && !loadError && !filteredMembers.length" class="empty-state panel-empty-state">
      <Users :size="20" />
      <strong>{{ members.length ? "没有匹配的成员" : "暂无成员数据" }}</strong>
      <span>{{ members.length ? "试试其他关键词或角色筛选条件。" : "后端返回成员后会显示在这里。" }}</span>
    </div>
  </section>
  <Dialog v-model:open="inviteOpen">
    <DialogContent class="invite-dialog">
      <form @submit.prevent="inviteMember">
        <DialogHeader>
          <DialogTitle>邀请新成员</DialogTitle>
          <DialogDescription
            >填写邀请所需的联系方式与权限信息，姓名可在对方接受邀请后补充。</DialogDescription
          >
        </DialogHeader>
        <div class="invite-form">
          <Field>
            <FieldLabel for="invite-phone">手机号</FieldLabel>
            <Input
              id="invite-phone"
              v-model="invitePhone"
              type="tel"
              placeholder="请输入 11 位手机号"
              autocomplete="tel"
              :aria-invalid="Boolean(inviteError)"
            />
          </Field>
          <div class="invite-form-grid">
            <Field>
              <FieldLabel for="invite-department">所属部门</FieldLabel>
              <Input
                id="invite-department"
                v-model="inviteDepartment"
                type="text"
                placeholder="例如：平台研发部"
                :aria-invalid="Boolean(inviteError)"
              />
            </Field>
            <Field>
              <FieldLabel for="invite-title">职位 / 职能</FieldLabel>
              <Input
                id="invite-title"
                v-model="inviteTitle"
                type="text"
                placeholder="例如：后端工程师"
                :aria-invalid="Boolean(inviteError)"
              />
            </Field>
          </div>
          <Field>
            <FieldLabel>初始角色</FieldLabel>
            <Select v-model="inviteRole">
              <SelectTrigger aria-label="设置成员初始角色">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="role in assignableRoles"
                  :key="role"
                  :value="role"
                >
                  {{ role }}
                </SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel for="invite-note">邀请说明</FieldLabel>
            <textarea
              id="invite-note"
              v-model="inviteNote"
              rows="3"
              placeholder="说明邀请原因、参与项目或需要查看的资料范围"
              :aria-invalid="Boolean(inviteError)"
            />
          </Field>
          <p v-if="inviteError" class="invite-error" role="alert">
            {{ inviteError }}
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" type="button" @click="inviteOpen = false"
            >取消</Button
          >
          <Button type="submit">发送邀请</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.member-table .table-row {
  grid-template-columns: 1.55fr 1.35fr 1fr 1fr 1fr;
}
.role-badge {
  color: #708288;
  background: #f3f6f6;
  border-radius: 0.3125rem;
  padding: 0.3125rem 0.4375rem;
  font-size: 0.5rem;
  width: fit-content;
  letter-spacing: 0.04em;
}

.member-org {
  display: grid;
  min-width: 0;
  gap: 0.25rem;
}

.member-org strong,
.member-org small {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.member-org strong {
  color: var(--workspace-text);
  font-size: 0.6875rem;
  font-weight: 600;
}

.member-org small {
  color: var(--workspace-muted);
  font-size: 0.625rem;
}

.invite-dialog form {
  display: grid;
  gap: 1.25rem;
}

.invite-form {
  display: grid;
  gap: 1rem;
}

.invite-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.member-load-state {
  display: grid;
  min-height: 12rem;
  place-items: center;
  align-content: center;
  gap: 0.5rem;
  padding: 2rem;
  color: var(--workspace-muted);
  text-align: center;
}

.member-load-state svg {
  color: var(--teal-dark);
}

.member-load-state strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}

.member-load-state span {
  font-size: 0.625rem;
}

.member-load-error svg {
  color: #c15b5b;
}

.invite-form textarea {
  width: 100%;
  resize: vertical;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  padding: 0.625rem 0.75rem;
  background: var(--surface);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.75rem;
  line-height: 1.5;
}

.invite-form textarea::placeholder {
  color: var(--workspace-subtle);
}

.invite-form textarea:focus {
  border-color: var(--teal);
  outline: 0.125rem solid color-mix(in oklab, var(--teal) 22%, transparent);
}

.invite-error {
  margin: -0.375rem 0 0;
  color: var(--destructive);
  font-size: 0.75rem;
}

.members-panel {
  overflow: hidden;
}

.member-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.0625rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  background: var(--surface-raised);
}

.member-summary > div {
  display: grid;
  gap: 0.3125rem;
  padding: 1rem 1.5rem;
}

.member-summary > div + div {
  border-left: 0.0625rem solid var(--workspace-divider);
}

.member-summary span {
  color: var(--workspace-muted);
  font-size: 0.625rem;
}

.member-summary strong {
  color: var(--workspace-text);
  font-size: 1.125rem;
}

.members-heading {
  align-items: center;
}

.permission-hint {
  color: var(--workspace-muted);
  font-size: 0.6875rem;
}

.members-toolbar {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.member-filter-select {
  width: 7.5rem;
}

.member-role-select {
  width: 6.5rem;
  min-height: 1.875rem;
}

.role-readonly {
  width: 6.5rem;
  color: var(--workspace-muted);
  font-size: 0.625rem;
  font-weight: 650;
  letter-spacing: 0.04em;
}

.member-active-cell {
  white-space: nowrap;
}

@media (max-width: 47.5rem) {
  .member-summary > div {
    padding: 0.875rem 1rem;
  }

  .members-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .members-toolbar {
    width: 100%;
  }

  :deep(.search-field-page) {
    flex: 1;
  }

  .member-table {
    overflow-x: auto;
  }

  .member-table .table-row {
    min-width: 54rem;
  }

  .invite-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
