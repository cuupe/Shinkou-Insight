<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  SlidersHorizontal,
} from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";
import { workspaceApi } from "@/api/workspace";

const {
  notify,
  workspaceId,
  workspace,
  availableWorkspaces,
  currentUser,
  isWorkspaceAdmin,
  router,
} = useWorkspace();
const workspaceName = ref(workspace.name);
const workspaceSlug = ref(workspace.slug);
const workspaceDescription = ref(workspace.description);
const deleteOpen = ref(false);
const deleteConfirmation = ref("");
const replacementWorkspaceId = ref("");
const preferences = reactive({
  webSearch: true,
  citationsRequired: true,
  retention: "90 天",
});
const replacementWorkspaces = computed(() =>
  availableWorkspaces.filter(
    (item) => String(item.id) !== workspaceId.value,
  ),
);

function applyPreferences(value: unknown) {
  if (!value) return;
  try {
    Object.assign(
      preferences,
      typeof value === "string" ? JSON.parse(value) : value,
    );
  } catch {
    // Keep defaults when older records contain malformed preferences.
  }
}

async function loadSettings() {
  try {
    const remote = await workspaceApi.detail(workspaceId.value);
    workspaceName.value = remote.name;
    workspaceSlug.value = remote.code || workspaceSlug.value;
    workspaceDescription.value = remote.description || "";
    applyPreferences(remote.preferences);
  } catch {
    notify("工作区设置加载失败");
  }
}

onMounted(loadSettings);
watch(workspaceId, (next, previous) => {
  if (next && next !== previous) void loadSettings();
});

async function saveSettings() {
  if (!isWorkspaceAdmin.value) {
    notify("只有工作区所有者或管理员可以修改工作区");
    return;
  }
  if (!workspaceName.value.trim()) {
    notify("请输入工作区名称");
    return;
  }
  try {
    const remote = await workspaceApi.update(workspaceId.value, {
      name: workspaceName.value.trim(),
      description: workspaceDescription.value.trim(),
    });
    Object.assign(workspace, {
      name: remote.name,
      slug: remote.code || workspaceSlug.value,
      description: remote.description || "",
    });
  } catch (error) {
    notify(error instanceof Error ? error.message : "工作区设置保存失败");
    return;
  }
  notify(`工作区「${workspaceName.value}」设置已保存`);
}

async function copySlug() {
  try {
    await navigator.clipboard.writeText(workspaceSlug.value);
    notify("工作区标识已复制");
  } catch {
    notify("当前环境不支持复制");
  }
}

async function confirmDelete() {
  if (!isWorkspaceAdmin.value) {
    notify("只有工作区所有者或管理员可以删除工作区");
    return;
  }
  if (deleteConfirmation.value !== workspaceName.value) {
    notify("请输入正确的工作区名称");
    return;
  }
  try {
    const workspacesBeforeDelete = await workspaceApi.list();
    availableWorkspaces.splice(
      0,
      availableWorkspaces.length,
      ...workspacesBeforeDelete,
    );
    const otherWorkspaces = workspacesBeforeDelete.filter(
      (item) => String(item.id) !== workspaceId.value,
    );
    if (
      otherWorkspaces.length > 0 &&
      !otherWorkspaces.some(
        (item) => String(item.id) === replacementWorkspaceId.value,
      )
    ) {
      notify("请先选择删除后要进入的其他工作区");
      return;
    }
    await workspaceApi.remove(workspaceId.value);
    const nextWorkspace = otherWorkspaces.find(
      (item) => String(item.id) === replacementWorkspaceId.value,
    );
    const replacement =
      nextWorkspace ||
      (await workspaceApi.create({
        name: `${currentUser.value?.userName || "我的"} 的工作区`,
      }));

    deleteOpen.value = false;
    deleteConfirmation.value = "";
    replacementWorkspaceId.value = "";
    notify(
      nextWorkspace
        ? "工作区已删除，已切换到其他工作区"
        : "工作区已删除，已为你创建新的工作区",
    );
    await router.replace({
      name: "workspace-dashboard",
      params: { workspaceId: String(replacement.id) },
    });
  } catch (error) {
    notify(error instanceof Error ? error.message : "工作区删除失败");
  }
}

async function openDeleteDialog() {
  if (!isWorkspaceAdmin.value) {
    notify("只有工作区所有者或管理员可以删除工作区");
    return;
  }
  deleteConfirmation.value = "";
  replacementWorkspaceId.value = "";
  try {
    const remoteWorkspaces = await workspaceApi.list();
    availableWorkspaces.splice(
      0,
      availableWorkspaces.length,
      ...remoteWorkspaces,
    );
  } catch {
    // Keep the already loaded workspace list so the confirmation dialog remains usable.
  }
  deleteOpen.value = true;
}

async function savePreferences() {
  if (!isWorkspaceAdmin.value) {
    notify("只有工作区所有者或管理员可以修改工作区");
    return;
  }
  try {
    const remote = await workspaceApi.updatePreferences(
      workspaceId.value,
      preferences,
    );
    applyPreferences(remote.preferences);
    notify("工作区偏好已更新");
  } catch (error) {
    notify(error instanceof Error ? error.message : "工作区偏好保存失败");
  }
}
</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="工作区设置"
    subtitle="配置工作区的基础信息、Agent 能力与数据策略"
  >
    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>工作区信息</h2>
          <p>用于识别团队和默认项目上下文。</p>
          <p v-if="!isWorkspaceAdmin" class="permission-hint">
            仅工作区所有者或管理员可以修改工作区信息。
          </p>
        </div>
        <CheckCircle2 :size="18" class="section-icon" />
      </div>
      <div class="form-grid">
        <label class="field-label"
          >工作区名称<input
            v-model="workspaceName"
            maxlength="40"
            :disabled="!isWorkspaceAdmin" /></label
        ><label class="field-label"
          >工作区标识
           <div class="input-with-action">
             <input :value="workspaceSlug" readonly aria-readonly="true" /><button
               type="button"
               aria-label="复制工作区标识"
              @click="copySlug"
            >
              <Copy :size="14" />
            </button>
           </div>
           <small class="field-hint">创建后不可修改，仅支持复制。</small></label
        ><label class="field-label field-wide"
          >工作区描述<textarea
            v-model="workspaceDescription"
            rows="3"
            :disabled="!isWorkspaceAdmin" />
        </label>
      </div>
      <button
        v-if="isWorkspaceAdmin"
        class="button button-primary"
        type="button"
        @click="saveSettings"
      >
        保存设置
      </button>
    </div>

    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>工作区偏好</h2>
          <p>这些设置会影响 Agent 在当前工作区中的默认行为。</p>
        </div>
        <SlidersHorizontal :size="18" class="section-icon" />
      </div>
      <div class="preference-list">
        <label class="preference-row"
          ><span
            ><strong>允许 Web Search</strong
            ><small>在内部资料不足时补充公开信息</small></span
          ><input
            v-model="preferences.webSearch"
            type="checkbox"
            :disabled="!isWorkspaceAdmin"
            class="switch-input" /><span class="switch-ui"
        /></label>
        <label class="preference-row"
          ><span
            ><strong>强制引用证据</strong
            ><small>要求 Agent 为关键结论提供可追溯引用</small></span
          ><input
            v-model="preferences.citationsRequired"
            type="checkbox"
            :disabled="!isWorkspaceAdmin"
            class="switch-input" /><span class="switch-ui"
        /></label>
        <label class="preference-row"
          ><span
            ><strong>运行记录保留</strong
            ><small>超过保留期的运行记录会进入归档状态</small></span
          ><select v-model="preferences.retention" :disabled="!isWorkspaceAdmin">
            <option>30 天</option>
            <option>90 天</option>
            <option>1 年</option>
            <option>永久</option>
          </select></label
        >
      </div>
      <button
        v-if="isWorkspaceAdmin"
        class="button button-secondary button-sm"
        type="button"
        @click="savePreferences"
      >
        保存偏好
      </button>
    </div>

    <div class="settings-section danger-section">
      <div class="danger-copy">
        <span class="danger-icon"><AlertTriangle :size="16" /></span>
        <div>
          <h2>危险区域</h2>
          <p>删除工作区将移除所有项目、资产和运行记录。</p>
        </div>
      </div>
      <button
        v-if="isWorkspaceAdmin"
        class="button button-danger"
        type="button"
        @click="openDeleteDialog"
      >
        删除工作区
      </button>
      <span v-else class="permission-hint"
        >仅工作区所有者或管理员可以删除工作区</span
      >
    </div>

    <Dialog v-model:open="deleteOpen"
      ><DialogContent class="danger-dialog sm:max-w-lg"
        ><DialogHeader
          ><DialogTitle>确认删除工作区？</DialogTitle
          ><DialogDescription
            >这是不可逆操作。删除后，工作区中的项目、资产和运行记录都将无法恢复。</DialogDescription
          ></DialogHeader
        >
        <div class="danger-confirm">
          请输入工作区名称 <strong>{{ workspaceName }}</strong> 以确认。<input
            v-model="deleteConfirmation"
            :placeholder="workspaceName"
          />
        </div>
        <label v-if="replacementWorkspaces.length" class="delete-target-field">
          删除后进入工作区
          <select v-model="replacementWorkspaceId">
            <option disabled value="">请选择其他工作区</option>
            <option
              v-for="item in replacementWorkspaces"
              :key="String(item.id)"
              :value="String(item.id)"
            >
              {{ item.name }}
            </option>
          </select>
        </label>
        <p v-else class="delete-target-hint">
          当前没有其他工作区。确认删除后，系统会自动创建新的工作区并进入。
        </p>
        <DialogFooter
          ><button
            class="button button-secondary"
            type="button"
            @click="deleteOpen = false"
          >
            取消</button
          ><button
            class="button button-danger"
            type="button"
            :disabled="
              deleteConfirmation !== workspaceName ||
              (replacementWorkspaces.length > 0 && !replacementWorkspaceId)
            "
            @click="confirmDelete"
          >
            确认提交删除
          </button></DialogFooter
        ></DialogContent
      ></Dialog
    >
  </Layout>
</template>

<style scoped>
.form-grid {
  align-items: start;
}

.section-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.section-icon {
  color: var(--teal-dark);
}
.permission-hint {
  margin-top: 0.375rem;
  color: #8a5a24;
  font-size: 0.75rem;
}
.input-with-action {
  display: flex;
  align-items: center;
  border: 0.0625rem solid #dfe9e8;
  border-radius: 0.4375rem;
  background: #fff;
}
.input-with-action:focus-within {
  border-color: #71c9bd;
  box-shadow: 0 0 0 0.1875rem rgba(20, 184, 166, 0.08);
}
.input-with-action input {
  border: 0;
}
.input-with-action button {
  display: grid;
  place-items: center;
  margin-right: 0.375rem;
  border: 0;
  background: transparent;
  color: var(--workspace-muted);
  cursor: pointer;
}
.input-with-action button:hover {
  color: var(--teal-dark);
}
.field-error {
  color: #c55b5b;
  font-size: 0.75rem;
}
.preference-list {
  display: grid;
  max-width: 48.75rem;
  margin-bottom: 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  overflow: hidden;
}
.preference-row {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  cursor: pointer;
}
.preference-row:last-child {
  border-bottom: 0;
}
.preference-row strong,
.preference-row small {
  display: block;
}
.preference-row strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.preference-row small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.preference-row select {
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  padding: 0.375rem 0.5rem;
  color: var(--workspace-text);
  background: var(--surface-soft);
  font: inherit;
  font-size: 0.75rem;
}
.switch-input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.switch-ui {
  width: 2.125rem;
  height: 1.1875rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #d8e2e2;
}
.switch-ui::after {
  display: block;
  width: 0.875rem;
  height: 0.875rem;
  margin: 0.15625rem;
  border-radius: 50%;
  background: #fff;
  content: "";
  transition: transform 0.16s;
}
.switch-input:checked + .switch-ui {
  background: var(--teal);
}
.switch-input:checked + .switch-ui::after {
  transform: translateX(0.9375rem);
}
.danger-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
}
.danger-copy {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
}
.danger-icon {
  display: grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.5rem;
  color: #b64c4c;
  background: #fff0ef;
}
.danger-dialog {
  max-width: 32rem !important;
}
.danger-confirm {
  display: grid;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 1px solid #f0d7d7;
  border-radius: 0.4375rem;
  color: #9d5757;
  background: #fff6f6;
  font-size: 0.75rem;
}
.danger-confirm strong {
  color: #b64c4c;
}
.danger-confirm input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #e7caca;
  border-radius: 0.375rem;
  padding: 0.5rem;
  outline: 0;
  color: #6f4646;
  background: #fff;
  font: inherit;
  font-size: 0.75rem;
}
.danger-confirm input:focus {
  border-color: #c87979;
}
.delete-target-field {
  display: grid;
  gap: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.delete-target-field select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--workspace-border);
  border-radius: 0.375rem;
  padding: 0.5rem;
  color: var(--workspace-text);
  background: var(--surface);
  font: inherit;
  font-size: 0.75rem;
}
.delete-target-hint {
  margin: 0;
  color: #9d5757;
  font-size: 0.75rem;
  line-height: 1.5;
}
.danger-dialog .button-danger:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
@media (max-width: 47.5rem) {
  .danger-section {
    align-items: flex-start;
    flex-direction: column;
  }
  .danger-section .button {
    width: 100%;
  }
  .section-intro {
    gap: 0.5rem;
  }
}
</style>
