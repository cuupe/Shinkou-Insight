<script setup lang="ts">
import { computed } from "vue";
import {
  Activity,
  ArrowRight,
  BarChart3,
  ChevronDown,
  ClipboardList,
  Download,
  FolderOpen,
  MessageCircle,
  ShieldCheck,
} from "@lucide/vue";
import { useRoute } from "vue-router";

const route = useRoute();

const workflowSteps = [
  {
    label: "项目定义",
    description: "填写目标、问题与约束",
    route: "project-planning",
    routes: ["project-planning"],
    icon: ClipboardList,
  },
  {
    label: "智能分析",
    description: "检索、对比并形成方案",
    route: "project-runs",
    routes: ["project-runs", "project-run-detail"],
    icon: Activity,
  },
  {
    label: "细节确认",
    description: "在对话中追问和修订",
    route: "project-agent-chat",
    routes: ["project-agent-chat"],
    icon: MessageCircle,
  },
  {
    label: "审查定稿",
    description: "核对证据、风险与责任",
    route: "project-review",
    routes: ["project-review"],
    icon: ShieldCheck,
  },
  {
    label: "导出成果",
    description: "通过审查后生成文件",
    route: "project-reports",
    routes: ["project-reports"],
    icon: Download,
  },
];

const activeStepIndex = computed(() => {
  const routeName = String(route.name || "");
  return workflowSteps.findIndex((step) => step.routes.includes(routeName));
});

const activeStep = computed(() => workflowSteps[activeStepIndex.value]);

function projectRoute(name: string) {
  return {
    name,
    params: {
      workspaceId: route.params.workspaceId,
      projectId: route.params.projectId,
    },
  };
}

function stepClass(index: number) {
  return {
    "is-current": index === activeStepIndex.value,
    "is-before": activeStepIndex.value >= 0 && index < activeStepIndex.value,
  };
}
</script>

<template>
  <details class="project-workflow" aria-label="项目工作流">
    <summary class="project-workflow-summary">
      <span class="project-workflow-summary-copy">
        <span class="project-workflow-kicker">PROJECT DELIVERY FLOW</span>
        <strong>从项目输入到可交付成果</strong>
        <small>先定义问题，再让 Agent 分析，最后由人确认、审查并导出。</small>
      </span>
      <span class="project-workflow-summary-side">
        <span v-if="activeStep" class="project-workflow-current">
          <span class="project-workflow-current-dot" />
          当前阶段：{{ activeStep.label }}
        </span>
        <span class="project-workflow-toggle" aria-hidden="true">
          <ChevronDown :size="16" />
        </span>
      </span>
    </summary>

    <div class="project-workflow-content">
      <nav class="project-workflow-track" aria-label="项目主流程">
        <template v-for="(step, index) in workflowSteps" :key="step.label">
          <RouterLink
            class="project-workflow-step"
            :class="stepClass(index)"
            :to="projectRoute(step.route)"
            :aria-current="index === activeStepIndex ? 'step' : undefined"
          >
            <span class="project-workflow-index">
              <component :is="step.icon" :size="16" />
            </span>
            <span class="project-workflow-copy">
              <strong>{{ step.label }}</strong>
              <small>{{ step.description }}</small>
            </span>
          </RouterLink>
          <span
            v-if="index < workflowSteps.length - 1"
            class="project-workflow-connector"
            :class="{ 'is-before': index < activeStepIndex }"
            aria-hidden="true"
          >
            <ArrowRight :size="14" />
          </span>
        </template>
      </nav>

      <div class="project-workflow-support">
        <span class="project-workflow-support-label">支撑数据</span>
        <RouterLink :to="projectRoute('project-assets')">
          <FolderOpen :size="13" />知识库资料
        </RouterLink>
        <RouterLink :to="projectRoute('project-files')">
          <FolderOpen :size="13" />对话文件
        </RouterLink>
        <RouterLink :to="projectRoute('project-overview')">
          <BarChart3 :size="13" />用量与结果
        </RouterLink>
      </div>
    </div>
  </details>
</template>

<style scoped>
.project-workflow {
  display: block;
  padding: 1rem 1.125rem 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.875rem;
  background:
    linear-gradient(110deg, color-mix(in oklab, var(--teal) 7%, var(--surface)), var(--surface-raised)),
    var(--surface);
  box-shadow: 0 0.75rem 2rem color-mix(in oklab, var(--workspace-border) 35%, transparent);
}

.project-workflow-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  list-style: none;
}

.project-workflow-summary::-webkit-details-marker {
  display: none;
}

.project-workflow-summary-copy {
  display: grid;
  gap: 0.2rem;
  min-width: 0;
}

.project-workflow-summary-copy strong,
.project-workflow-summary-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-workflow-summary-copy strong {
  color: var(--workspace-text);
  font-size: 0.95rem;
}

.project-workflow-summary-copy small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.project-workflow-summary-side {
  display: inline-flex;
  align-items: center;
  gap: 1rem;
  flex: 0 0 auto;
}

.project-workflow-toggle {
  display: grid;
  width: 1.875rem;
  height: 1.875rem;
  place-items: center;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  color: var(--workspace-muted);
  transition:
    background 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.project-workflow-summary:hover .project-workflow-toggle,
.project-workflow-summary:focus-visible .project-workflow-toggle {
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  color: var(--teal-dark);
}

.project-workflow[open] .project-workflow-toggle {
  transform: rotate(180deg);
}

.project-workflow-summary:focus-visible {
  outline: 0.125rem solid color-mix(in oklab, var(--teal) 55%, transparent);
  outline-offset: 0.25rem;
}

.project-workflow-kicker {
  color: var(--teal-dark);
  font-size: 0.625rem;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.project-workflow-content {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 0.0625rem solid
    color-mix(in oklab, var(--workspace-border) 75%, transparent);
}

.project-workflow-current {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.375rem;
  padding: 0.35rem 0.55rem;
  border: 0.0625rem solid color-mix(in oklab, var(--teal) 45%, var(--workspace-border));
  border-radius: 999px;
  color: var(--teal-dark);
  font-size: 0.7rem;
  white-space: nowrap;
}

.project-workflow-current-dot {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 0.18rem color-mix(in oklab, var(--teal) 15%, transparent);
}

.project-workflow-track {
  display: flex;
  align-items: stretch;
  min-width: 0;
}

.project-workflow-step {
  position: relative;
  display: flex;
  flex: 1 1 0;
  align-items: center;
  gap: 0.55rem;
  min-width: 0;
  padding: 0.65rem 0.7rem;
  border: 0.0625rem solid transparent;
  border-radius: 0.625rem;
  color: var(--workspace-muted);
  text-decoration: none;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    color 160ms ease;
}

.project-workflow-step:hover,
.project-workflow-step.is-current {
  border-color: color-mix(in oklab, var(--teal) 48%, var(--workspace-border));
  background: color-mix(in oklab, var(--teal) 9%, var(--surface-raised));
  color: var(--workspace-text);
}

.project-workflow-step.is-before {
  color: color-mix(in oklab, var(--workspace-text) 78%, var(--workspace-muted));
}

.project-workflow-index {
  display: grid;
  flex: 0 0 1.8rem;
  width: 1.8rem;
  height: 1.8rem;
  place-items: center;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 50%;
  background: var(--surface);
  color: var(--workspace-muted);
}

.project-workflow-step.is-current .project-workflow-index {
  border-color: var(--teal);
  background: color-mix(in oklab, var(--teal) 18%, var(--surface));
  color: var(--teal-dark);
}

.project-workflow-step.is-before .project-workflow-index {
  border-color: color-mix(in oklab, var(--teal) 55%, var(--workspace-border));
  color: var(--teal-dark);
}

.project-workflow-copy {
  display: grid;
  gap: 0.12rem;
  min-width: 0;
}

.project-workflow-copy strong,
.project-workflow-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-workflow-copy strong {
  color: inherit;
  font-size: 0.78rem;
}

.project-workflow-copy small {
  color: var(--workspace-muted);
  font-size: 0.68rem;
}

.project-workflow-connector {
  display: grid;
  flex: 0 0 1.2rem;
  place-items: center;
  color: var(--workspace-border-strong, var(--workspace-muted));
}

.project-workflow-connector.is-before {
  color: var(--teal);
}

.project-workflow-support {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding-top: 0.65rem;
  border-top: 0.0625rem solid color-mix(in oklab, var(--workspace-border) 75%, transparent);
  color: var(--workspace-muted);
  font-size: 0.7rem;
}

.project-workflow-support-label {
  margin-right: 0.15rem;
  color: var(--workspace-text);
  font-weight: 700;
}

.project-workflow-support a {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.4rem;
  border-radius: 0.35rem;
  color: inherit;
  text-decoration: none;
}

.project-workflow-support a:hover {
  background: color-mix(in oklab, var(--teal) 8%, var(--surface-raised));
  color: var(--teal-dark);
}

@media (max-width: 60rem) {
  .project-workflow {
    overflow-x: auto;
  }

  .project-workflow-track,
  .project-workflow-support {
    min-width: 53rem;
  }
}

@media (max-width: 42rem) {
  .project-workflow-summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .project-workflow-summary-side {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
