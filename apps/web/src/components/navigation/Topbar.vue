<script setup lang="ts">
import {
  Bell,
  Check,
  ChevronDown,
  ChevronRight,
  Menu,
  Search,
} from "@lucide/vue";
import { useWorkspace } from "@/composables/useWorkspace";
import ThemeToggle from "@/components/common/ThemeToggle.vue";

const {
  workspace,
  currentName,
  isProject,
  pageTitle,
  searchQuery,
  toast,
  mobileOpen,
  notify,
} = useWorkspace();
</script>

<template>
  <header class="app-topbar">
    <div class="topbar-leading">
      <button
        class="mobile-menu"
        type="button"
        aria-label="打开导航"
        @click="mobileOpen = true"
      >
        <Menu :size="20" />
      </button>
      <div class="breadcrumbs">
        <span>{{ isProject ? "消息队列技术选型" : workspace.name }}</span
        ><ChevronRight :size="14" /><strong>{{ pageTitle }}</strong>
      </div>
    </div>
    <div class="topbar-actions">
      <label class="global-search"
        ><Search :size="16" /><input
          v-model="searchQuery"
          placeholder="搜索资产、报告…"
        /><kbd>⌘ K</kbd></label
      ><ThemeToggle /><button
        class="icon-button"
        type="button"
        aria-label="通知"
        @click="notify('暂无新的通知')"
      >
        <Bell :size="18" /><i class="notification-dot" /></button
      ><button
        class="user-menu"
        type="button"
        @click="notify('个人设置接口待接入')"
      >
        <span class="user-avatar">LM</span><span class="user-name">林默</span
        ><ChevronDown :size="14" />
      </button>
    </div>
  </header>
  <div v-if="toast" class="toast-message"><Check :size="16" />{{ toast }}</div>
</template>
