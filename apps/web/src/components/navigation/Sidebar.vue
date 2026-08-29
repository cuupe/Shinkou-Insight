<script setup lang="ts">
import {
  ChevronDown,
  ChevronRight,
  Sparkles,
  X,
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
  routeTo,
  notify,
} = useWorkspace();

function closeMenu() {
  mobileOpen.value = false;
}
</script>

<template>
  <!-- 侧边栏 -->
  <aside class="app-sidebar" :class="{ 'is-open': mobileOpen }">
    <!-- 品牌 -->
    <div class="sidebar-brand">
      <div class="sidebar-brand-inner">
        <div class="brand-mark">
          <Sparkles :size="17" />
        </div>

        <div>
          <strong>Shinkou</strong>
          <span>INSIGHT</span>
        </div>
      </div>

      <!-- 移动端关闭按钮 -->
      <button
        class="mobile-menu"
        :class="{ 'is-showed': !mobileOpen }"
        type="button"
        aria-label="关闭导航"
        @click="closeMenu"
      >
        <X :size="20" />
      </button>
    </div>

    <!-- 工作区 -->
    <button
      class="workspace-switcher"
      type="button"
      @click="notify(`当前工作区：${workspace.name || '暂无工作区信息'}`)"
    >
      <span class="workspace-avatar">
        {{ workspace.initials || "—" }}
      </span>

      <span class="workspace-switcher-copy">
        <strong>{{ workspace.name || "当前工作区" }}</strong>
        <small>{{ workspace.plan || "暂无套餐信息" }}</small>
      </span>

      <ChevronDown :size="15" />
    </button>

    <!-- 导航 -->
    <div class="sidebar-scroll">
      <p class="nav-caption">工作区</p>

      <nav class="side-nav">
        <RouterLink
          v-for="item in workspaceNav"
          :key="item.name"
          :to="routeTo(item.name)"
          :class="{ active: currentName === item.name }"
        >
          <component :is="item.icon" :size="17" />

          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <p class="nav-caption project-caption">当前项目</p>

      <div class="current-project">
        <span class="project-dot" />

        <span class="project-name">
          {{ selectedProject?.name || "暂无项目" }}
        </span>

        <ChevronRight :size="14" />
      </div>

      <nav class="side-nav">
        <RouterLink
          v-for="item in projectNav"
          :key="item.name"
          :to="routeTo(item.name)"
          :class="{ active: currentName === item.name }"
        >
          <component :is="item.icon" :size="17" />

          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </div>

    <!-- 底部 -->
    <div class="sidebar-footer">
      <div class="usage-label">
        <span>本月用量</span>
        <span>{{ workspace.usagePercent || "暂无数据" }}</span>
      </div>

      <div class="usage-track">
        <i :style="{ width: workspace.usagePercent || '0%' }" />
      </div>

    </div>
  </aside>
</template>

<style scoped>
.app-sidebar {
  width: 15.5rem;
  min-width: 15.5rem;

  height: 100vh;
  min-height: 0;
  max-height: 100vh;

  position: sticky;
  top: 0;
  align-self: flex-start;

  z-index: 20;

  display: flex;
  flex-direction: column;

  overflow: hidden;

  background: var(--sidebar-bg);
  color: var(--sidebar-text);

  /*
   * 默认显示
   */
  transform: translateX(0);

  transition: transform 0.25s ease;
}

/*
 * 宽屏：
 * mobileOpen = false 时收起侧边栏占位（面板本身滑出）
 */
.app-sidebar:not(.is-open) {
  transform: translateX(-100%);
}

/*
 * mobileOpen = true 时展开
 */
.app-sidebar.is-open {
  transform: translateX(0);
}

.sidebar-brand {
  display: flex;
  height: 4.75rem;
  align-items: center;
  justify-content: space-between;
  gap: 0.6875rem;
  padding: 0 1.375rem;
  letter-spacing: -0.02em;
}

.sidebar-brand-inner {
  display: flex;
  height: 4.75rem;
  align-items: center;
  gap: 0.6875rem;
  letter-spacing: -0.02em;
}

.sidebar-brand strong,
.sidebar-brand span,
.workspace-switcher-copy strong,
.workspace-switcher-copy small {
  display: block;
}

.sidebar-brand strong {
  font-size: 1rem;
  line-height: 1;
}

.sidebar-brand span {
  margin-top: 0.3125rem;
  color: #6f7f8a;
  font-size: 0.5rem;
  font-weight: 700;
  letter-spacing: 0.22em;
}

.brand-mark {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border-radius: 0.625rem;
  background: var(--teal);
  color: #082f2b;
}

.is-showed {
  display: none;
}

.icon-button,
.mobile-menu {
  position: relative;

  display: inline-grid;
  width: 2rem;
  height: 2rem;

  place-items: center;

  padding: 0;

  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5625rem;

  background: var(--surface);
  color: var(--workspace-muted);

  cursor: pointer;

  z-index: 20;
}

.icon-button:hover,
.mobile-menu:hover {
  border-color: #bfd4d2;
  color: var(--teal-dark);
}

.workspace-switcher {
  display: flex;
  width: calc(100% - 1.75rem);
  align-items: center;
  gap: 0.5625rem;

  margin: 0 0.875rem 1.625rem;
  padding: 0.625rem;

  border: 0.0625rem solid rgb(255 255 255 / 9%);
  border-radius: 0.6875rem;

  background: rgb(255 255 255 / 6%);
  color: inherit;

  text-align: left;
  cursor: pointer;
}

.workspace-switcher:hover {
  background: rgb(255 255 255 / 10%);
}

.workspace-avatar {
  display: grid;
  width: 1.8125rem;
  height: 1.8125rem;
  flex: 0 0 auto;
  place-items: center;

  border-radius: 0.5625rem;

  background: #dff7f3;
  color: #0b756b;

  font-size: 0.625rem;
  font-weight: 800;
}

.workspace-switcher-copy {
  min-width: 0;
  flex: 1;
}

.workspace-switcher-copy strong,
.workspace-switcher-copy small {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.workspace-switcher-copy strong {
  font-size: 0.75rem;
}

.workspace-switcher-copy small {
  margin-top: 0.1875rem;
  color: var(--sidebar-muted);
  font-size: 0.5625rem;
}

.sidebar-scroll {
  flex: 1 1 auto;
  min-height: 0;

  overflow-y: auto;

  padding: 0 0.75rem;
}

.nav-caption {
  margin: 0 0.6875rem 0.5625rem;

  color: #5e707e;

  font-size: 0.625rem;
  font-weight: 700;

  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.project-caption {
  margin-top: 1.75rem;
}

.side-nav {
  display: grid;
  gap: 0.1875rem;
}

.side-nav a {
  display: flex;

  min-height: 2.3125rem;

  align-items: center;
  gap: 0.6875rem;

  padding: 0 0.6875rem;

  border-radius: 0.5625rem;

  color: var(--sidebar-muted);

  font-size: 0.75rem;

  text-decoration: none;

  transition:
    background 0.2s ease,
    color 0.2s ease;
}

.side-nav a:hover {
  background: rgb(255 255 255 / 6%);
  color: var(--sidebar-text);
}

.side-nav a.active {
  background: rgb(20 184 166 / 15%);
  box-shadow: inset 0.125rem 0 0 var(--teal);
  color: #ecfffc;
}

.side-nav a.active svg {
  color: var(--teal);
}

.current-project {
  display: flex;
  align-items: center;
  gap: 0.5rem;

  padding: 0.5rem 0.625rem 0.6875rem;

  color: #cad5da;

  font-size: 0.6875rem;
}

.project-dot {
  display: inline-block;

  width: 0.4375rem;
  height: 0.4375rem;

  flex: 0 0 auto;

  border-radius: 50%;

  background: var(--teal);
}

.project-name {
  min-width: 0;
  flex: 1;

  overflow: hidden;

  white-space: nowrap;
  text-overflow: ellipsis;
}

.sidebar-footer {
  flex: 0 0 auto;

  padding: 1.0625rem 1.125rem 1.1875rem;

  border-top: 0.0625rem solid rgb(255 255 255 / 8%);
}

.usage-label {
  display: flex;
  justify-content: space-between;

  margin-bottom: 0.5rem;

  color: #9aaab3;

  font-size: 0.625rem;
}

.usage-track {
  height: 0.3125rem;

  overflow: hidden;

  border-radius: 62.4375rem;

  background: rgb(255 255 255 / 10%);
}

.usage-track i {
  display: block;

  height: 100%;

  border-radius: inherit;

  background: var(--teal);
}

.sidebar-scrim {
  display: none;
}

/* 移动端 */
@media screen and (max-width: 47.5rem) {
  .app-sidebar {
    /* position: fixed; */
    top: 0;
    left: 0;
    bottom: 0;
    display: fixed;
    width: 15.5rem;
    min-width: 15.5rem;

    height: 100dvh;
    max-height: 100dvh;

    z-index: 1000;

    transform: translate3d(-100%, 0, 0);

    transition: transform 0.25s ease;
    will-change: transform;
  }

  .app-sidebar.is-open {
    transform: translate3d(0, 0, 0);
  }

  /*
   * 遮罩
   */
  .sidebar-scrim {
    display: block;

    position: fixed;
    inset: 0;

    z-index: 999;

    background: rgb(9 25 31 / 30%);
  }
}
</style>
