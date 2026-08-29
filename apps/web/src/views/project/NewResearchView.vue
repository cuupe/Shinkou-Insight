<script setup lang="ts">
import { ArrowRight, Globe2, Play, ShieldCheck } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const researchPreviewSteps = [
  "拆解调研问题并生成检索计划",
  "优先引用项目知识库中的可验证资料",
  "整理结论、风险和待确认问题",
];
const {
  newRunGoal,
  allowWeb,
  maxRounds,
  runStarted,
  router,
  routeTo,
  startRun,
} = useWorkspace();

function startResearch() {
  void startRun();
}
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / RESEARCH"
    title="创建调研"
    subtitle="描述问题，配置 Agent 的调研边界"
    ><template #action
      ><span v-if="runStarted" class="status-badge status-indexed"
        ><i />调研已创建</span
      ></template
    ></PageHeader
  >
  <div class="run-create-layout">
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>调研目标</h2>
          <p>目标越清晰，最终报告越容易验证。</p>
        </div>
      </div>
      <textarea
        v-model="newRunGoal"
        rows="7"
        placeholder="描述你希望 Agent 研究的问题…"
      />
      <div class="run-options">
        <label
          ><Globe2 :size="17" /><span
            ><strong>允许 Web Search</strong
            ><small>补充公开资料与最新信息</small></span
          ><input v-model="allowWeb" type="checkbox" /></label
        ><label
          ><ShieldCheck :size="17" /><span
            ><strong>最多调研轮数</strong
            ><small>控制任务深度与成本</small></span
          ><input v-model.number="maxRounds" type="number" min="1" max="12"
        /></label>
      </div>
      <button class="button button-primary" type="button" @click="startResearch">
        <Play :size="16" />开始调研
      </button>
    </section>
    <section class="panel run-preview-panel">
      <p class="eyebrow">RUN PREVIEW</p>
      <h2>Agent 将会做什么</h2>
      <ol>
        <li v-for="step in researchPreviewSteps" :key="step">{{ step }}</li>
      </ol>
      <div v-if="runStarted" class="success-note">
        任务已创建，已加入调研运行列表。
      </div>
      <button
        v-else
        class="text-button"
        type="button"
        @click="router.push(routeTo('project-playground'))"
      >
        先测试检索 <ArrowRight :size="14" />
      </button>
    </section>
  </div>
</template>

<style scoped>
.run-create-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) 20.625rem;
  gap: 1.25rem;
  align-items: start;
}
.run-create-layout > .panel:first-child {
  padding: 1.5rem;
}
.run-create-layout > .panel:first-child > textarea {
  width: 100%;
  min-height: 10rem;
  resize: vertical;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
  padding: 0.75rem 0.8125rem;
  font: inherit;
  font-size: 0.6875rem;
  line-height: 1.65;
  outline: 0;
}
.run-create-layout > .panel:first-child > textarea:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 12%, transparent);
}
.run-options {
  display: grid;
  gap: 0.625rem;
  margin: 1rem 0;
}
.run-options label {
  display: flex;
  align-items: center;
  gap: 0.6875rem;
  padding: 0.75rem 0.8125rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-soft);
}
.run-options label > svg {
  flex: 0 0 auto;
  color: var(--teal-dark);
}
.run-options label > span {
  display: grid;
  flex: 1;
  gap: 0.25rem;
}
.run-options strong {
  color: var(--workspace-text);
  font-size: 0.625rem;
}
.run-options small {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.run-options input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  accent-color: var(--teal);
}
.run-options input[type="number"] {
  width: 4.5rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
  padding: 0.4375rem 0.5rem;
  font: inherit;
  font-size: 0.625rem;
}
.run-create-layout > .panel:first-child > .button {
  width: 100%;
}
.run-form-panel {
  padding: 1.4375rem 1.5625rem 0.4375rem;
}
.form-step {
  display: grid;
  grid-template-columns: 1.8125rem 1fr;
  gap: 0.9375rem;
  padding-bottom: 1.5625rem;
  margin-bottom: 1.5625rem;
  border-bottom: 0.0625rem solid #edf1f1;
}
.form-step:last-child {
  border-bottom: 0;
  margin-bottom: 0;
}
.step-number {
  display: grid;
  place-items: center;
  width: 1.625rem;
  height: 1.625rem;
  border-radius: 50%;
  background: #e7f6f3;
  color: var(--teal-dark);
  font-size: 0.5625rem;
  font-weight: 800;
}
.step-content h2 {
  color: #34474d;
  font-size: 0.8125rem;
  margin: 0;
}
.step-content > p {
  color: #99a6a9;
  font-size: 0.625rem;
  margin: 0.375rem 0 1rem;
}
.step-content textarea {
  width: 100%;
  border: 0.0625rem solid #dfe9e8;
  border-radius: 0.4375rem;
  padding: 0.6875rem;
  font: inherit;
  font-size: 0.6875rem;
  color: #475b61;
  line-height: 1.6;
  outline: 0;
  resize: vertical;
}
.toggle-row.bordered {
  margin: 0 0 1.125rem;
  border: 0.0625rem solid #e6eeee;
  border-radius: 0.5rem;
  padding: 0.6875rem;
}
.compact-label {
  grid-template-columns: 1fr auto;
  align-items: center;
}
.number-input {
  display: flex;
  align-items: center;
  border: 0.0625rem solid #e1eaea;
  border-radius: 0.4375rem;
  height: 1.9375rem;
  overflow: hidden;
}
.number-input button {
  width: 1.75rem;
  height: 100%;
  border: 0;
  background: #f6f9f9;
  color: #74868a;
  cursor: pointer;
}
.number-input strong {
  min-width: 1.5rem;
  text-align: center;
  color: #4d6267;
  font-size: 0.6875rem;
}
.two-inputs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.run-preview-panel {
  padding: 1.5rem;
  padding-bottom: 1.25rem;
}
.run-preview-panel > .eyebrow {
  margin: 0 0 0.625rem;
}
.run-preview-panel > h2 {
  color: var(--workspace-text);
  font-size: 1rem;
  margin: 0;
}
.run-preview-panel > ol {
  display: grid;
  gap: 0.75rem;
  margin: 1.25rem 0;
  padding-left: 1.125rem;
  color: var(--workspace-muted);
  font-size: 0.625rem;
  line-height: 1.5;
}
.run-preview-panel > ol li::marker {
  color: var(--teal-dark);
  font-weight: 700;
}
.run-preview-panel .success-note {
  margin: 1rem 0;
}
.preview-stat {
  display: flex;
  justify-content: space-between;
  padding: 0.875rem 1.5rem;
  color: #94a1a5;
  font-size: 0.625rem;
}
.preview-stat strong {
  color: #344b50;
  font-size: 0.8125rem;
}
.preview-stat small {
  color: #99a7aa;
  font-size: 0.5625rem;
  font-weight: 500;
}
.preview-divider {
  border-top: 0.0625rem solid #edf1f1;
  margin: 1rem 1.5rem;
}
.strategy-note {
  display: flex;
  gap: 0.5625rem;
  margin: 0 1.5rem;
  padding: 0.875rem;
  background: #f2faf9;
  border-radius: 0.4375rem;
  color: var(--teal-dark);
}
.strategy-note p {
  margin: 0;
  color: #6c8f8c;
  font-size: 0.5625rem;
  line-height: 1.6;
}
.run-preview-panel .full-button {
  margin-left: 1.5rem;
  width: calc(100% - 3rem);
}

@media (max-width: 68.75rem) {
  .run-create-layout {
    grid-template-columns: 1fr;
  }

  .run-preview-panel {
    max-width: none;
  }
}

@media (max-width: 47.5rem) {
  .two-inputs {
    grid-template-columns: 1fr;
  }
}
</style>
