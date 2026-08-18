<script setup lang="ts">
import { Database, Globe2, ListChecks } from "@lucide/vue";
import { ref } from "vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { toolConfigs } from "@/data/mock";
const { notify } = useWorkspace();
const toolIcons = { database: Database, globe: Globe2, list: ListChecks };
const tools = ref(
  toolConfigs.map((tool) => ({
    ...tool,
    icon: toolIcons[tool.icon as keyof typeof toolIcons],
  })),
);

function toggleTool(tool: (typeof tools.value)[number]) {
  tool.enabled = !tool.enabled;
  notify(`${tool.name}已${tool.enabled ? "连接" : "断开"}`);
}
</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="工具与连接器"
    subtitle="配置工作区的基础能力与 Agent 行为"
    ><div class="settings-section">
      <div>
        <h2>工具与连接器</h2>
        <p>为 Agent 授权可调用的外部能力。</p>
      </div>
      <div class="config-list">
        <div v-for="tool in tools" :key="tool.name" class="config-row">
          <span class="config-icon"
            ><component :is="tool.icon" :size="17" /></span
          ><span
            ><strong>{{ tool.name }}</strong
            ><small>{{ tool.description }}</small></span
          ><span
            class="status-badge"
            :class="tool.enabled ? 'status-indexed' : 'status-muted'"
            ><i />{{ tool.enabled ? "已连接" : "未连接" }}</span
          ><button
            class="button button-secondary button-sm"
            type="button"
            @click="toggleTool(tool)"
          >
            {{ tool.enabled ? "管理" : "连接" }}
          </button>
        </div>
      </div>
    </div></Layout
  >
</template>
