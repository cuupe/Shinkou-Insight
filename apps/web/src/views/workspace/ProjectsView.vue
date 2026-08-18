<script setup lang="ts">
import { ArrowRight, MoreHorizontal, Plus } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { projectDefaults } from "@/data/mock";
const { projects, workspaceId, routeTo, notify } = useWorkspace();
function createProject() {
  const name = window.prompt("请输入项目名称");
  if (!name?.trim()) return;
  projects.push({
    id: `project-local-${Date.now()}`,
    name: name.trim(),
    description: projectDefaults.description,
    assets: 0,
    runs: 0,
    reports: 0,
    color: projectDefaults.color,
  });
  notify("项目已创建");
}
function openProjectMenu(name: string) {
  notify(`已打开「${name}」的项目菜单`);
}
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
        @click="createProject"
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
          :aria-label="`打开项目菜单：${project.name}`"
          @click="openProjectMenu(project.name)"
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
      aria-label="创建新项目"
      @click="createProject"
    >
      <span><Plus :size="23" /></span><strong>创建新项目</strong
      ><small>从一个清晰的问题开始</small>
    </button>
  </div>
</template>
