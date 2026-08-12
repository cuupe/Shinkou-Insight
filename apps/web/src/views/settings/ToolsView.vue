<script setup lang="ts">
import { Database, Globe2, ListChecks } from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { notify } = useWorkspace();
const tools = [
  {
    name: "内部知识库",
    description: "检索当前工作区已索引资产",
    icon: Database,
    enabled: true,
  },
  {
    name: "Web Search",
    description: "补充外部公开资料与最新信息",
    icon: Globe2,
    enabled: true,
  },
  {
    name: "Jira",
    description: "读取项目缺陷与行动项状态",
    icon: ListChecks,
    enabled: false,
  },
];
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
            @click="notify('连接器授权接口待接入')"
          >
            {{ tool.enabled ? "管理" : "连接" }}
          </button>
        </div>
      </div>
    </div></Layout
  >
</template>
