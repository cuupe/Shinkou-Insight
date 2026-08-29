<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
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

const { notify, workspaceId, workspace } = useWorkspace();
const workspaceName = ref(workspace.name);
const workspaceSlug = ref(workspace.slug);
const workspaceDescription = ref(workspace.description);
const slugError = ref("");
const deleteOpen = ref(false);
const deleteConfirmation = ref("");
const preferences = reactive({
  webSearch: true,
  citationsRequired: true,
  retention: "90 天",
});

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

onMounted(async () => {
  try {
    const remote = await workspaceApi.detail(workspaceId.value);
    workspaceName.value = remote.name;
    workspaceSlug.value = remote.code || workspaceSlug.value;
    workspaceDescription.value = remote.description || "";
    applyPreferences(remote.preferences);
  } catch {
    notify("工作区设置加载失败");
  }
});

async function saveSettings() {
  if (!workspaceName.value.trim()) {
    notify("请输入工作区名称");
    return;
  }
  if (!/^[a-z0-9-]+$/.test(workspaceSlug.value)) {
    slugError.value = "只能使用小写字母、数字和连字符";
    return;
  }
  slugError.value = "";
  try {
    const remote = await workspaceApi.update(workspaceId.value, {
      name: workspaceName.value.trim(),
      code: workspaceSlug.value,
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

function confirmDelete() {
  if (deleteConfirmation.value !== workspaceName.value) {
    notify("请输入正确的工作区名称");
    return;
  }
  deleteOpen.value = false;
  deleteConfirmation.value = "";
  notify("当前版本暂不支持删除工作区，请联系平台管理员");
}

function openDeleteDialog() {
  deleteConfirmation.value = "";
  deleteOpen.value = true;
}

async function savePreferences() {
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
        </div>
        <CheckCircle2 :size="18" class="section-icon" />
      </div>
      <div class="form-grid">
        <label class="field-label"
          >工作区名称<input v-model="workspaceName" maxlength="40" /></label
        ><label class="field-label"
          >工作区标识
          <div class="input-with-action">
            <input v-model="workspaceSlug" @input="slugError = ''" /><button
              type="button"
              aria-label="复制工作区标识"
              @click="copySlug"
            >
              <Copy :size="14" />
            </button>
          </div>
          <small v-if="slugError" class="field-error">{{
            slugError
          }}</small></label
        ><label class="field-label field-wide"
          >工作区描述<textarea v-model="workspaceDescription" rows="3" />
        </label>
      </div>
      <button class="button button-primary" type="button" @click="saveSettings">
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
            class="switch-input" /><span class="switch-ui"
        /></label>
        <label class="preference-row"
          ><span
            ><strong>强制引用证据</strong
            ><small>要求 Agent 为关键结论提供可追溯引用</small></span
          ><input
            v-model="preferences.citationsRequired"
            type="checkbox"
            class="switch-input" /><span class="switch-ui"
        /></label>
        <label class="preference-row"
          ><span
            ><strong>运行记录保留</strong
            ><small>超过保留期的运行记录会进入归档状态</small></span
          ><select v-model="preferences.retention">
            <option>30 天</option>
            <option>90 天</option>
            <option>1 年</option>
            <option>永久</option>
          </select></label
        >
      </div>
      <button
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
        class="button button-danger"
        type="button"
        @click="openDeleteDialog"
      >
        删除工作区
      </button>
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
            :disabled="deleteConfirmation !== workspaceName"
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
.section-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.section-icon {
  color: var(--teal-dark);
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
  font-size: 0.5625rem;
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
  font-size: 0.6875rem;
}
.preference-row small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.preference-row select {
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  padding: 0.375rem 0.5rem;
  color: var(--workspace-text);
  background: var(--surface-soft);
  font: inherit;
  font-size: 0.5625rem;
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
  font-size: 0.625rem;
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
  font-size: 0.625rem;
}
.danger-confirm input:focus {
  border-color: #c87979;
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
