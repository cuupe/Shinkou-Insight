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
import { projectOverviewData } from "@/data/mock";
const { selectedProject, router, routeTo, assets } = useWorkspace();

function overviewIcon(icon: string) {
  return icon === "database" ? Database : Zap;
}
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
        <span><Users :size="15" />{{ projectOverviewData.memberCountLabel }}</span
        ><span><Clock3 :size="15" />{{ projectOverviewData.updatedLabel }}</span
        ><span><ShieldCheck :size="15" />{{ projectOverviewData.visibilityLabel }}</span>
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
    <button
      v-for="(action, index) in projectOverviewData.quickActions"
      :key="action.label"
      type="button"
      @click="router.push(routeTo(action.route))"
    >
      <span class="quick-icon" :class="`${action.tone}-bg`">
        <Upload v-if="index === 0" :size="18" />
        <Search v-else-if="index === 1" :size="18" />
        <Zap v-else :size="18" />
      </span>
      <span><strong>{{ action.label }}</strong><small>{{ action.description }}</small></span>
      <ArrowRight :size="15" />
    </button>
  </div>
  <div class="overview-grid">
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>{{ projectOverviewData.assetSummary.title }}</h2>
          <p>{{ projectOverviewData.assetSummary.description }}</p>
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
          ><span>{{ projectOverviewData.assetSummary.totalLabel }}</span>
        </div>
        <div>
          <strong class="teal-text">{{
            assets.filter((item) => item.status === "indexed").length
          }}</strong
          ><span>{{ projectOverviewData.assetSummary.indexedLabel }}</span>
        </div>
        <div><strong>{{ projectOverviewData.assetSummary.completion }}</strong><span>{{ projectOverviewData.assetSummary.completionLabel }}</span></div>
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
        <div v-for="capability in projectOverviewData.capabilities" :key="capability.title">
          <component :is="overviewIcon(capability.icon)" :size="18" /><span
            ><strong>{{ capability.title }}</strong
            ><small>{{ capability.description }}</small></span
          >
        </div>
      </div>
    </section>
  </div>
</template>
