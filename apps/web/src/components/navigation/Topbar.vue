<script setup lang="ts">
import {
  Bell,
  Check,
  ChevronDown,
  ChevronRight,
  Menu,
  Search,
} from "@lucide/vue";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useWorkspace } from "@/composables/useWorkspace";
import ThemeToggle from "@/components/common/ThemeToggle.vue";
import { userProfile } from "@/data/mock";

const {
  workspace,
  selectedProject,
  currentName,
  isProject,
  pageTitle,
  searchQuery,
  toast,
  mobileOpen,
  notify,
  router,
  routeTo,
} = useWorkspace();
const userMenuOpen = ref(false);

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value;
}

function openUserSettings() {
  userMenuOpen.value = false;
  router.push(routeTo("user-settings"));
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target as HTMLElement;
  if (!target.closest(".user-menu-wrap")) userMenuOpen.value = false;
}

onMounted(() => document.addEventListener("click", handleDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", handleDocumentClick));
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
        <span>{{ isProject ? selectedProject?.name : workspace.name }}</span
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
      ><div class="user-menu-wrap">
        <button
          class="user-menu"
          type="button"
          aria-label="打开用户菜单"
          :aria-expanded="userMenuOpen"
          @click.stop="toggleUserMenu"
        >
          <span class="user-avatar">{{ userProfile.initials }}</span
          ><span class="user-name">{{ userProfile.name }}</span
          ><ChevronDown :size="14" />
        </button>
        <div v-if="userMenuOpen" class="user-popover" role="menu">
          <div class="user-popover-heading">
            <strong>{{ userProfile.name }}</strong
            ><small>{{ userProfile.roleLabel }}</small>
          </div>
          <button type="button" role="menuitem" @click="openUserSettings">
            个人信息设置
          </button>
          <button
            type="button"
            role="menuitem"
            @click="notify('当前账号已登录')"
          >
            账号状态：正常
          </button>
        </div>
      </div>
    </div>
  </header>
  <div v-if="toast" class="toast-message"><Check :size="16" />{{ toast }}</div>
</template>
