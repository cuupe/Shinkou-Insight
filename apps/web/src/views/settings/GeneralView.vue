<script setup lang="ts">
import { ref } from "vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { workspace } from "@/data/mock";
const { notify } = useWorkspace();
const workspaceName = ref(workspace.name);
const workspaceSlug = ref(workspace.slug);
const workspaceDescription = ref(workspace.description);

function saveSettings() {
  notify(`工作区「${workspaceName.value}」设置已保存`);
}

function deleteWorkspace() {
  if (window.confirm("确定要删除当前工作区吗？此操作不可撤销。")) {
    notify("已提交工作区删除申请");
  }
}
</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="工作区设置"
    subtitle="配置工作区的基础能力与 Agent 行为"
    ><div class="settings-section">
      <div>
        <h2>工作区信息</h2>
        <p>用于识别团队和默认项目上下文。</p>
      </div>
      <div class="form-grid">
        <label class="field-label"
          >工作区名称<input v-model="workspaceName" /></label
        ><label class="field-label"
          >工作区标识<input v-model="workspaceSlug" /></label
        ><label class="field-label field-wide"
          >工作区描述<textarea v-model="workspaceDescription" rows="3" />
        </label>
      </div>
      <button class="button button-primary" type="button" @click="saveSettings">保存设置</button>
    </div>
    <div class="settings-section danger-section">
      <div>
        <h2>危险区域</h2>
        <p>删除工作区将移除所有项目、资产和运行记录。</p>
      </div>
      <button class="button button-danger" type="button" @click="deleteWorkspace">删除工作区</button>
    </div></Layout
  >
</template>
