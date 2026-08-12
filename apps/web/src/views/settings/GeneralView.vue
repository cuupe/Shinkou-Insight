<script setup lang="ts">
import Layout from "@/components/settings/Layout.vue";
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
          >工作区名称<input value="Shinkou Labs" /></label
        ><label class="field-label"
          >工作区标识<input value="shinkou-labs" /></label
        ><label class="field-label field-wide"
          >工作区描述<textarea rows="3">
面向企业知识的智能调研与决策工作区。</textarea>
        </label>
      </div>
    </div>
    <div class="settings-section danger-section">
      <div>
        <h2>危险区域</h2>
        <p>删除工作区将移除所有项目、资产和运行记录。</p>
      </div>
      <button class="button button-danger" type="button">删除工作区</button>
    </div></Layout
  >
</template>
