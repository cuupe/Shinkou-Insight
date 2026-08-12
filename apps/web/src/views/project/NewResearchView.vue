<script setup lang="ts">
import { ArrowRight, Globe2, Play, ShieldCheck } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const {
  newRunGoal,
  allowWeb,
  maxRounds,
  runStarted,
  startRun,
  router,
  routeTo,
} = useWorkspace();
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / RESEARCH"
    title="创建调研"
    subtitle="描述问题，配置 Agent 的调研边界"
    ><template #action
      ><span class="status-badge status-muted"><i />接口待接入</span></template
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
      <button class="button button-primary" type="button" @click="startRun">
        <Play :size="16" />开始调研
      </button>
    </section>
    <section class="panel run-preview-panel">
      <p class="eyebrow">RUN PREVIEW</p>
      <h2>Agent 将会做什么</h2>
      <ol>
        <li>拆解调研问题并生成检索计划</li>
        <li>优先引用项目知识库中的可验证资料</li>
        <li>整理结论、风险和待确认问题</li>
      </ol>
      <div v-if="runStarted" class="success-note">
        任务已创建，等待接入调研接口。
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
