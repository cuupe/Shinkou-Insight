<script setup lang="ts">
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Sparkles,
} from "@lucide/vue";
import { RouterLink } from "vue-router";
import { useWorkspace } from "@/composables/useWorkspace";

const {
  workspace,
  selectedProject,
  currentName,
  mobileOpen,
  workspaceNav,
  projectNav,
  settingsNav,
  routeTo,
  notify,
} = useWorkspace();
</script>

<template>
  <div v-if="mobileOpen" class="sidebar-scrim" @click="mobileOpen = false" />
  <aside class="app-sidebar" :class="{ 'is-open': mobileOpen }">
    <div class="sidebar-brand">
      <div class="brand-mark"><Sparkles :size="17" /></div>
      <div><strong>Shinkou</strong><span>INSIGHT</span></div>
    </div>
    <button
      class="workspace-switcher"
      type="button"
      @click="notify('工作区切换接口待接入')"
    >
      <span class="workspace-avatar">{{ workspace.initials }}</span
      ><span class="workspace-switcher-copy"
        ><strong>{{ workspace.name }}</strong
        ><small>{{ workspace.plan }}</small></span
      ><ChevronDown :size="15" />
    </button>
    <div class="sidebar-scroll">
      <p class="nav-caption">工作区</p>
      <nav class="side-nav">
        <RouterLink
          v-for="item in workspaceNav"
          :key="item.name"
          :to="routeTo(item.name)"
          :class="{ active: currentName === item.name }"
          @click="mobileOpen = false"
          ><component :is="item.icon" :size="17" /><span>{{
            item.label
          }}</span></RouterLink
        >
      </nav>
      <p class="nav-caption project-caption">当前项目</p>
      <div class="current-project">
        <span class="project-dot" /><span>{{ selectedProject?.name }}</span
        ><ChevronRight :size="14" />
      </div>
      <nav class="side-nav">
        <RouterLink
          v-for="item in projectNav"
          :key="item.name"
          :to="routeTo(item.name)"
          :class="{ active: currentName === item.name }"
          @click="mobileOpen = false"
          ><component :is="item.icon" :size="17" /><span>{{
            item.label
          }}</span></RouterLink
        >
      </nav>
      <p class="nav-caption project-caption">管理</p>
      <nav class="side-nav">
        <RouterLink
          v-for="item in settingsNav"
          :key="item.name"
          :to="routeTo(item.name)"
          :class="{ active: currentName === item.name }"
          @click="mobileOpen = false"
          ><component :is="item.icon" :size="17" /><span>{{
            item.label
          }}</span></RouterLink
        >
      </nav>
    </div>
    <div class="sidebar-footer">
      <div class="usage-label"><span>本月用量</span><span>68%</span></div>
      <div class="usage-track"><i style="width: 68%" /></div>
      <button
        class="help-link"
        type="button"
        @click="notify('帮助中心接口待接入')"
      >
        <CircleHelp :size="16" />帮助中心<ArrowRight :size="14" />
      </button>
    </div>
  </aside>
</template>
