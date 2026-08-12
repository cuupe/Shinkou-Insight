<script setup lang="ts">
import { ArrowRight, MoreHorizontal, Plus } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const { projects, workspaceId, routeTo, notify } = useWorkspace();
</script>

<template>
  <PageHeader
    eyebrow="WORKSPACE / PROJECTS"
    title="项目"
    subtitle="管理团队正在进行的知识调研"
    ><template #action
      ><button
        class="button button-primary"
        type="button"
        @click="notify('创建项目表单接口待接入')"
      >
        <Plus :size="17" />新建项目
      </button></template
    ></PageHeader
  >
  <div class="project-grid">
    <article v-for="project in projects" :key="project.id" class="project-card">
      <div class="project-card-top">
        <span
          class="project-color"
          :style="{ background: project.color }"
        /><button
          class="icon-button small"
          type="button"
          @click="notify('项目菜单接口待接入')"
        >
          <MoreHorizontal :size="17" />
        </button>
      </div>
      <h2>{{ project.name }}</h2>
      <p>{{ project.description }}</p>
      <div class="project-metrics">
        <span
          ><strong>{{ project.assets }}</strong
          >资产</span
        ><span
          ><strong>{{ project.runs }}</strong
          >运行</span
        ><span
          ><strong>{{ project.reports }}</strong
          >报告</span
        >
      </div>
      <RouterLink
        class="project-card-link"
        :to="{
          name: 'project-overview',
          params: { workspaceId, projectId: project.id },
        }"
        >打开项目 <ArrowRight :size="15"
      /></RouterLink>
    </article>
    <button
      class="project-card project-create-card"
      type="button"
      @click="notify('创建项目表单接口待接入')"
    >
      <span><Plus :size="23" /></span><strong>创建新项目</strong
      ><small>从一个清晰的问题开始</small>
    </button>
  </div>
</template>
