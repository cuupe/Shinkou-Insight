<script setup lang="ts">
import { ArrowRight, Plus } from "@lucide/vue";
import { ref } from "vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { promptConfigs } from "@/data/mock";
const { notify } = useWorkspace();
const prompts = ref(promptConfigs.map((prompt) => ({ ...prompt })));

function editPrompt(prompt: (typeof prompts.value)[number]) {
  const version = window.prompt("请输入 Prompt 版本", prompt.version);
  if (!version?.trim()) return;
  prompt.version = version.trim();
  prompt.updated = "刚刚";
  notify(`${prompt.name} 已更新`);
}

function createPrompt() {
  const name = window.prompt("请输入 Prompt 名称");
  if (!name?.trim()) return;
  prompts.value.push({
    name: name.trim(),
    version: "v0.1",
    updated: "刚刚",
    status: "草稿",
  });
  notify("Prompt 已创建");
}
</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="Prompt 版本"
    subtitle="配置工作区的基础能力与 Agent 行为"
    ><div class="settings-section">
      <div>
        <h2>Prompt 版本</h2>
        <p>版本化管理调研和报告生成所使用的提示词。</p>
      </div>
      <div class="prompt-list">
        <div v-for="prompt in prompts" :key="prompt.name" class="prompt-row">
          <code>{{ prompt.name }}</code
          ><span>{{ prompt.version }}</span
          ><small>{{ prompt.updated }}</small
          ><span class="status-badge status-indexed"
            ><i />{{ prompt.status }}</span
          ><button
            class="icon-button small"
            type="button"
            @click="editPrompt(prompt)"
          >
            <ArrowRight :size="15" />
          </button>
        </div>
      </div>
      <button
        class="button button-secondary"
        type="button"
        @click="createPrompt"
      >
        <Plus :size="16" />新建 Prompt
      </button>
    </div></Layout
  >
</template>
