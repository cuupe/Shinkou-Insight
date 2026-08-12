<script setup lang="ts">
import {
  ArrowRight,
  Clock3,
  Database,
  Plus,
  Search,
  ShieldCheck,
  Upload,
  Users,
  Zap,
} from "@lucide/vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { selectedProject, router, routeTo, assets, notify } = useWorkspace();
</script>

<template>
  <div class="project-hero">
    <div>
      <div class="project-title-line">
        <span class="project-color large" />
        <p class="eyebrow">PROJECT / ACTIVE</p>
      </div>
      <h1>{{ selectedProject?.name }}</h1>
      <p>{{ selectedProject?.description }}</p>
      <div class="hero-meta">
        <span><Users :size="15" />4 位成员</span
        ><span><Clock3 :size="15" />最近更新 今天 10:06</span
        ><span><ShieldCheck :size="15" />内部项目</span>
      </div>
    </div>
    <button
      class="button button-primary"
      type="button"
      @click="router.push(routeTo('project-new-run'))"
    >
      <Plus :size="17" />创建调研
    </button>
  </div>
  <div class="quick-actions">
    <button type="button" @click="router.push(routeTo('project-assets'))">
      <span class="quick-icon teal-bg"><Upload :size="18" /></span
      ><span><strong>上传资料</strong><small>PDF、Markdown、TXT</small></span
      ><ArrowRight :size="15" /></button
    ><button type="button" @click="router.push(routeTo('project-playground'))">
      <span class="quick-icon violet-bg"><Search :size="18" /></span
      ><span><strong>检索测试</strong><small>验证知识库召回</small></span
      ><ArrowRight :size="15" /></button
    ><button type="button" @click="router.push(routeTo('project-new-run'))">
      <span class="quick-icon amber-bg"><Zap :size="18" /></span
      ><span><strong>创建调研</strong><small>让 Agent 开始工作</small></span
      ><ArrowRight :size="15" />
    </button>
  </div>
  <div class="overview-grid">
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>知识资产状态</h2>
          <p>当前项目的资料索引进度</p>
        </div>
        <button
          class="text-button"
          type="button"
          @click="router.push(routeTo('project-assets'))"
        >
          管理资产 <ArrowRight :size="14" />
        </button>
      </div>
      <div class="asset-health">
        <div>
          <strong>{{ assets.length }}</strong
          ><span>全部资料</span>
        </div>
        <div>
          <strong class="teal-text">{{
            assets.filter((item) => item.status === "indexed").length
          }}</strong
          ><span>已索引</span>
        </div>
        <div><strong>86%</strong><span>索引完成率</span></div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>项目能力</h2>
          <p>从知识到决策的完整闭环</p>
        </div>
      </div>
      <div class="capability-list">
        <div>
          <Database :size="18" /><span
            ><strong>知识库已就绪</strong
            ><small>支持混合检索与证据引用</small></span
          >
        </div>
        <div>
          <Zap :size="18" /><span
            ><strong>Agent 可运行</strong
            ><small>可直接创建调研任务</small></span
          >
        </div>
      </div>
    </section>
  </div>
</template>
