<script setup lang="ts">
import { ArrowRight, Plus } from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { notify } = useWorkspace();
const prompts = [
  {
    name: "research-planner",
    version: "v3.2",
    updated: "今天 09:12",
    status: "生产中",
  },
  {
    name: "evidence-reviewer",
    version: "v2.8",
    updated: "昨天 18:03",
    status: "生产中",
  },
  {
    name: "report-writer",
    version: "v1.6",
    updated: "8 月 05 日",
    status: "草稿",
  },
];
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
            @click="notify('Prompt 编辑接口待接入')"
          >
            <ArrowRight :size="15" />
          </button>
        </div>
      </div>
      <button
        class="button button-secondary"
        type="button"
        @click="notify('新建 Prompt 接口待接入')"
      >
        <Plus :size="16" />新建 Prompt
      </button>
    </div></Layout
  >
</template>
