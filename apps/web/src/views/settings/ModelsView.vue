<script setup lang="ts">
import { Cpu } from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { notify } = useWorkspace();
const models = [
  {
    name: "GPT-4.1",
    provider: "OpenAI",
    use: "调研规划与报告生成",
    enabled: true,
  },
  {
    name: "Qwen 2.5 72B",
    provider: "DashScope",
    use: "内部知识检索改写",
    enabled: true,
  },
  {
    name: "Claude Sonnet 4",
    provider: "Anthropic",
    use: "备用模型",
    enabled: false,
  },
];
</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="模型配置"
    subtitle="配置工作区的基础能力与 Agent 行为"
    ><div class="settings-section">
      <div>
        <h2>模型配置</h2>
        <p>选择 Agent 在不同任务中使用的模型。</p>
      </div>
      <div class="config-list">
        <div v-for="model in models" :key="model.name" class="config-row">
          <span class="config-icon"><Cpu :size="17" /></span
          ><span
            ><strong>{{ model.name }}</strong
            ><small>{{ model.provider }} · {{ model.use }}</small></span
          ><span
            class="status-badge"
            :class="model.enabled ? 'status-indexed' : 'status-muted'"
            ><i />{{ model.enabled ? "已启用" : "未启用" }}</span
          ><button
            class="text-button"
            type="button"
            @click="notify('模型连接测试接口待接入')"
          >
            测试连接
          </button>
        </div>
      </div>
    </div></Layout
  >
</template>
