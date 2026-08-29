<script setup lang="ts">
import {
  Activity,
  BarChart3,
  Bell,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Database,
  FileText,
  LogOut,
  Menu,
  Users,
} from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { useWorkspace } from "@/composables/useWorkspace";
import SearchField from "@/components/common/SearchField.vue";
import ThemeToggle from "@/components/common/ThemeToggle.vue";
import { authApi } from "@/api/auth";
import {
  useNotifications,
  type NotificationItem,
  type NotificationKind,
} from "@/composables/useNotifications";

const {
  workspace,
  workspaceId,
  selectedProject,
  currentName,
  isProject,
  pageTitle,
  searchQuery,
  toast,
  mobileOpen,
  displayName,
  roleLabel,
  notify,
  router,
  routeTo,
} = useWorkspace();

const userMenuOpen = ref(false);
const notificationOpen = ref(false);
const notificationFilter = ref<"all" | "unread">("all");
const loggingOut = ref(false);
const { notifications, unreadCount, loading, markRead, markAllRead } =
  useNotifications(workspaceId);

const filteredNotifications = computed(() =>
  notificationFilter.value === "unread"
    ? notifications.value.filter((notification) => !notification.read)
    : notifications.value,
);

const breadcrumbItems = computed(() => {
  const items: Array<{
    label: string;
    to?: ReturnType<typeof routeTo>;
  }> = [];

  if (isProject.value) {
    items.push({
      label: selectedProject.value?.name || "当前项目",
      to: routeTo("project-overview"),
    });

    if (currentName.value === "project-asset-detail") {
      items.push({
        label: "知识库",
        to: routeTo("project-assets"),
      });
    } else if (currentName.value === "project-run-detail") {
      items.push({
        label: "调研运行",
        to: routeTo("project-runs"),
      });
    }
  } else {
    items.push({
      label: workspace.name || "当前工作区",
      to: routeTo("workspace-dashboard"),
    });
  }

  items.push({
    label: pageTitle.value,
  });

  return items;
});

function toggleUserMenu() {
  notificationOpen.value = false;
  userMenuOpen.value = !userMenuOpen.value;
}

function toggleNotificationMenu() {
  userMenuOpen.value = false;
  notificationOpen.value = !notificationOpen.value;
}

function notificationIcon(kind: NotificationKind) {
  return {
    research: Activity,
    knowledge: Database,
    report: FileText,
    evaluation: BarChart3,
    workspace: Users,
  }[kind];
}

function openNotification(notification: NotificationItem) {
  markRead(notification.id);
  notificationOpen.value = false;

  if (notification.routeName) {
    if (notification.routeName.startsWith("project-") && notification.projectId) {
      router.push({
        name: notification.routeName,
        params: {
          workspaceId: workspaceId.value,
          projectId: notification.projectId,
        },
      });
    } else {
      router.push(routeTo(notification.routeName));
    }
  }
}

function openNotificationsPage() {
  notificationOpen.value = false;
  router.push(routeTo("notifications"));
}

function openUserSettings() {
  userMenuOpen.value = false;
  router.push(routeTo("user-settings"));
}

function openHelpCenter() {
  userMenuOpen.value = false;
  router.push(routeTo("help-center"));
}

function toggleMobileMenu() {
  mobileOpen.value = !mobileOpen.value;
}

async function handleLogout() {
  if (loggingOut.value) return;

  loggingOut.value = true;
  userMenuOpen.value = false;

  try {
    await authApi.logout();
  } catch {
  } finally {
    loggingOut.value = false;
    notify("已退出登录");
    router.push({ name: "login" });
  }
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target as HTMLElement;

  if (!target.closest(".user-menu-wrap")) {
    userMenuOpen.value = false;
  }

  if (!target.closest(".notification-menu-wrap")) {
    notificationOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener("click", handleDocumentClick);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
});
</script>

<template>
  <header class="app-topbar">
    <div class="topbar-leading">
      <button
        class="mobile-menu"
        :class="{ 'is-showed': mobileOpen }"
        type="button"
        :aria-label="mobileOpen ? '关闭导航' : '打开导航'"
        :aria-expanded="mobileOpen"
        @click.stop="toggleMobileMenu"
      >
        <Menu :size="20" />
      </button>

      <nav class="breadcrumbs" aria-label="页面路径">
        <template
          v-for="(item, index) in breadcrumbItems"
          :key="`${item.label}-${index}`"
        >
          <RouterLink v-if="item.to" class="breadcrumb-link" :to="item.to">
            {{ item.label }}
          </RouterLink>

          <strong v-else aria-current="page">
            {{ item.label }}
          </strong>

          <ChevronRight v-if="index < breadcrumbItems.length - 1" :size="14" />
        </template>
      </nav>
    </div>

    <div
      id="topbar-page-context"
      class="topbar-page-slot"
      aria-live="polite"
    ></div>

    <div class="topbar-actions">
      <SearchField
        v-model="searchQuery"
        variant="topbar"
        placeholder="搜索知识库、报告…"
        aria-label="搜索知识库、报告"
        shortcut="⌘ K"
      />

      <ThemeToggle />

      <div class="notification-menu-wrap">
        <button
          class="icon-button"
          type="button"
          aria-label="打开通知中心"
          :aria-expanded="notificationOpen"
          @click.stop="toggleNotificationMenu"
        >
          <Bell :size="18" />

          <span v-if="unreadCount" class="notification-count">
            {{ unreadCount > 9 ? "9+" : unreadCount }}
          </span>
        </button>

        <div
          v-if="notificationOpen"
          class="notification-popover"
          role="dialog"
          aria-label="通知中心"
        >
          <div class="notification-popover-heading">
            <div>
              <strong>通知</strong>
              <small>
                {{ unreadCount ? `${unreadCount} 条未读` : "全部已读" }}
              </small>
            </div>

            <button
              type="button"
              :disabled="!unreadCount"
              @click="markAllRead"
            >
              全部已读
            </button>
          </div>

          <div class="notification-filter" role="tablist" aria-label="通知筛选">
            <button
              type="button"
              :class="{ active: notificationFilter === 'all' }"
              role="tab"
              :aria-selected="notificationFilter === 'all'"
              @click="notificationFilter = 'all'"
            >
              全部 <span>{{ notifications.length }}</span>
            </button>

            <button
              type="button"
              :class="{ active: notificationFilter === 'unread' }"
              role="tab"
              :aria-selected="notificationFilter === 'unread'"
              @click="notificationFilter = 'unread'"
            >
              未读 <span>{{ unreadCount }}</span>
            </button>
          </div>

          <div v-if="loading" class="notification-empty">
            <strong>正在加载通知</strong>
          </div>

          <div v-else-if="filteredNotifications.length" class="notification-list">
            <button
              v-for="notification in filteredNotifications"
              :key="notification.id"
              class="notification-item"
              :class="{ 'is-unread': !notification.read }"
              type="button"
              @click="openNotification(notification)"
            >
              <span class="notification-item-icon" :class="`kind-${notification.kind}`">
                <component :is="notificationIcon(notification.kind)" :size="15" />
              </span>

              <span class="notification-item-copy">
                <strong>{{ notification.title }}</strong>
                <small>{{ notification.body }}</small>
                <em>{{ notification.time }}</em>
              </span>

              <i v-if="!notification.read" class="notification-unread-dot" aria-label="未读"></i>
            </button>
          </div>

          <div v-else class="notification-empty">
            <Bell :size="18" />
            <strong>{{ notificationFilter === "unread" ? "暂无未读通知" : "暂无通知" }}</strong>
            <span>新的调研、报告和工作区动态会显示在这里。</span>
          </div>

          <button class="notification-view-all" type="button" @click="openNotificationsPage">
            查看全部通知
            <ChevronRight :size="14" />
          </button>
        </div>
      </div>

      <div class="user-menu-wrap">
        <button
          class="user-menu"
          type="button"
          aria-label="打开用户菜单"
          :aria-expanded="userMenuOpen"
          @click.stop="toggleUserMenu"
        >
          <span class="user-name">
            {{ displayName }}
          </span>

          <ChevronDown :size="14" />
        </button>

        <div v-if="userMenuOpen" class="user-popover" role="menu">
          <div class="user-popover-heading">
            <strong>
              {{ displayName }}
            </strong>

            <small>
              {{ roleLabel }}
            </small>
          </div>

          <button type="button" role="menuitem" @click="openUserSettings">
            个人信息设置
          </button>

          <button
            class="help-menu-item"
            type="button"
            role="menuitem"
            @click="openHelpCenter"
          >
            <CircleHelp :size="14" />
            <span>帮助中心</span>
          </button>

          <div class="user-popover-divider"></div>

          <button
            class="logout-menu-item"
            type="button"
            role="menuitem"
            :disabled="loggingOut"
            @click="handleLogout"
          >
            <LogOut :size="14" />

            <span>
              {{ loggingOut ? "正在退出…" : "退出登录" }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </header>

  <div v-if="toast" class="toast-message">
    <Check :size="16" />

    <span>
      {{ toast }}
    </span>
  </div>
</template>

<style scoped>
.app-topbar {
  position: sticky;
  top: 0;
  z-index: 10;

  display: flex;
  height: 4.75rem;

  align-items: center;
  justify-content: space-between;

  gap: 1.5rem;

  padding: 0 clamp(1rem, 3vw, 2.125rem);

  border-bottom: 0.0625rem solid var(--workspace-border);

  background: color-mix(in oklab, var(--surface) 76%, transparent);
}

.topbar-leading,
.topbar-actions,
.breadcrumbs {
  display: flex;
  align-items: center;
}

.topbar-leading {
  min-width: 0;
}

.topbar-page-slot {
  min-width: 0;
  flex: 1 1 auto;

  /*
   * 中间区域只是占位，
   * 不应该阻止左右按钮接收点击。
   */
  pointer-events: none;
}

.topbar-actions {
  position: relative;
  z-index: 20;

  flex: 0 0 auto;

  gap: 1rem;

  pointer-events: auto;
}

.breadcrumbs {
  gap: 0.5rem;

  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.breadcrumbs strong {
  color: var(--workspace-text);
  font-weight: 600;
}

.breadcrumbs a {
  color: inherit;
  text-decoration: none;
  transition: color 160ms ease;
}

.breadcrumbs a:hover {
  color: var(--workspace-text);
  text-decoration: underline;
  text-underline-offset: 0.1875rem;
}

/* =========================================================
   Mobile menu
   ========================================================= */

.mobile-menu {
  position: relative;
  z-index: 20;

  width: 2rem;
  height: 2rem;

  place-items: center;

  padding: 0;
  display: inline-grid;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5625rem;

  background: var(--surface);
  color: var(--workspace-muted);

  cursor: pointer;

  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.mobile-menu:hover,
.mobile-menu:focus-visible {
  border-color: #bfd4d2;
  color: var(--teal-dark);
}

.mobile-menu:active {
  transform: translateY(1px);
}

/* =========================================================
   Icon button
   ========================================================= */

.icon-button {
  position: relative;
  z-index: 20;

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

  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.is-showed {
  display: none;
}

.icon-button:hover,
.icon-button:focus-visible {
  border-color: #bfd4d2;
  color: var(--teal-dark);
}

.icon-button:active {
  transform: translateY(1px);
}

.icon-button.small {
  width: 1.75rem;
  height: 1.75rem;

  border: 0;

  background: var(--surface-soft);
}

/* =========================================================
   Notification
   ========================================================= */

.notification-menu-wrap {
  position: relative;
  z-index: 30;
}

.notification-count {
  position: absolute;

  top: -0.3125rem;
  right: -0.375rem;

  min-width: 1rem;
  height: 1rem;

  padding: 0 0.25rem;

  border: 0.125rem solid var(--surface);
  border-radius: 999px;

  background: var(--teal);
  color: #ffffff;

  font-size: 0.5rem;
  font-weight: 700;
  line-height: 0.75rem;
  text-align: center;

  pointer-events: none;
}

.notification-popover {
  position: absolute;

  top: calc(100% + 0.625rem);
  right: 0;

  z-index: 30;

  width: min(25rem, calc(100vw - 2rem));
  max-height: min(35rem, calc(100dvh - 5.5rem));

  overflow: hidden;

  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.875rem;

  background: var(--surface);

  box-shadow: 0 1rem 2.5rem rgb(21 53 52 / 15%);
}

.notification-popover-heading {
  display: flex;

  align-items: center;
  justify-content: space-between;

  gap: 1rem;
  padding: 1rem 1rem 0.75rem;

  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.notification-popover-heading > div {
  display: grid;
  gap: 0.25rem;
}

.notification-popover-heading strong {
  color: var(--workspace-text);
  font-size: 0.875rem;
}

.notification-popover-heading small {
  color: var(--workspace-muted);
  font-size: 0.625rem;
}

.notification-popover-heading button,
.notification-filter button {
  padding: 0;

  border: 0;
  background: transparent;

  color: var(--teal-dark);

  font: inherit;
  font-size: 0.625rem;
  cursor: pointer;
}

.notification-popover-heading button:disabled {
  color: var(--workspace-muted);
  cursor: default;
  opacity: 0.55;
}

.notification-filter {
  display: flex;
  gap: 1rem;
  padding: 0.625rem 1rem 0.375rem;
}

.notification-filter button {
  color: var(--workspace-muted);
  font-weight: 600;
}

.notification-filter button.active {
  color: var(--teal-dark);
}

.notification-filter button span {
  margin-left: 0.125rem;
  color: inherit;
  opacity: 0.75;
}

.notification-list {
  display: grid;
  gap: 0.25rem;

  max-height: min(25rem, calc(100dvh - 12rem));
  padding: 0.375rem 0.5rem;
  overflow-y: auto;
}

.notification-item {
  position: relative;

  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr) auto;
  align-items: start;

  width: 100%;
  gap: 0.625rem;
  padding: 0.6875rem 0.625rem;

  border: 0;
  border-radius: 0.625rem;

  background: transparent;
  color: inherit;

  text-align: left;
  cursor: pointer;
}

.notification-item:hover,
.notification-item:focus-visible {
  background: var(--surface-soft);
}

.notification-item.is-unread {
  background: color-mix(in oklab, var(--teal-soft) 42%, transparent);
}

.notification-item-icon {
  display: inline-grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border-radius: 0.625rem;
  color: var(--teal-dark);
  background: var(--teal-soft);
}

.notification-item-icon.kind-research {
  color: #6d58b5;
  background: #f0ebff;
}

.notification-item-icon.kind-knowledge {
  color: #4778a8;
  background: #e9f3fb;
}

.notification-item-icon.kind-report {
  color: #af6a35;
  background: #fff2e6;
}

.notification-item-icon.kind-evaluation {
  color: #188b82;
  background: #e4f7f3;
}

.notification-item-icon.kind-workspace {
  color: #a34f74;
  background: #fcecf3;
}

.notification-item-copy {
  display: grid;
  min-width: 0;
  gap: 0.25rem;
}

.notification-item-copy strong {
  overflow: hidden;
  color: var(--workspace-text);
  font-size: 0.6875rem;
  font-weight: 700;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.notification-item-copy small {
  display: -webkit-box;
  overflow: hidden;
  color: var(--workspace-muted);
  font-size: 0.625rem;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.notification-item-copy em {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  font-style: normal;
}

.notification-unread-dot {
  width: 0.375rem;
  height: 0.375rem;
  margin-top: 0.25rem;
  border-radius: 50%;
  background: var(--teal);
}

.notification-empty {
  display: grid;
  justify-items: center;
  gap: 0.375rem;
  padding: 2.25rem 1.25rem;
  color: var(--workspace-muted);
  text-align: center;
}

.notification-empty svg {
  color: var(--teal);
}

.notification-empty strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}

.notification-empty span {
  font-size: 0.625rem;
}

.notification-view-all {
  display: flex;
  width: calc(100% - 1rem);
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  margin: 0.25rem 0.5rem 0.5rem;
  padding: 0.625rem;
  border: 0;
  border-top: 0.0625rem solid var(--workspace-divider);
  background: transparent;
  color: var(--teal-dark);
  font: inherit;
  font-size: 0.625rem;
  font-weight: 600;
  cursor: pointer;
}

.notification-view-all:hover,
.notification-view-all:focus-visible {
  color: var(--workspace-text);
}

/* =========================================================
   User menu
   ========================================================= */

.user-menu-wrap {
  position: relative;
  z-index: 30;
}

.user-menu {
  display: flex;

  align-items: center;

  gap: 0.5rem;

  padding: 0;

  border: 0;

  background: none;

  color: var(--workspace-muted);

  cursor: pointer;

  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.user-menu:hover,
.user-menu:focus-visible {
  color: var(--workspace-text);
}

.user-name {
  max-width: 8rem;

  overflow: hidden;

  color: var(--workspace-text);

  font-size: 0.6875rem;
  font-weight: 600;

  white-space: nowrap;

  text-overflow: ellipsis;
}

/* =========================================================
   User popover
   ========================================================= */

.user-popover {
  position: absolute;

  top: calc(100% + 0.625rem);
  right: 0;

  z-index: 30;

  width: 12rem;

  padding: 0.5rem;

  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;

  background: var(--surface);

  box-shadow: 0 0.75rem 2rem rgb(21 53 52 / 12%);
}

.user-popover-heading {
  display: grid;

  gap: 0.25rem;

  padding: 0.5rem 0.625rem 0.625rem;

  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.user-popover-heading strong {
  color: var(--workspace-text);
  font-size: 0.6875rem;
}

.user-popover-heading small {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}

.user-popover-divider {
  height: 0.0625rem;

  margin: 0.25rem 0;

  background: var(--workspace-divider);
}

.user-popover > button {
  width: 100%;

  padding: 0.5625rem 0.625rem;

  border: 0;
  border-radius: 0.375rem;

  background: transparent;

  color: var(--workspace-muted);

  text-align: left;

  font: inherit;
  font-size: 0.6875rem;

  cursor: pointer;

  touch-action: manipulation;
}

.user-popover > button:hover,
.user-popover > button:focus-visible {
  background: var(--surface-soft);
  color: var(--workspace-text);
}

.user-popover > .help-menu-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.user-popover > .help-menu-item svg {
  color: var(--teal-dark);
}

.user-popover > .logout-menu-item {
  display: flex;

  align-items: center;

  gap: 0.375rem;

  color: #b85757;
}

.user-popover > .logout-menu-item:hover,
.user-popover > .logout-menu-item:focus-visible {
  color: #a44444;
  background: #fff4f4;
}

.user-popover > .logout-menu-item:disabled {
  cursor: wait;
  opacity: 0.6;
}

/* =========================================================
   Toast
   ========================================================= */

.toast-message {
  position: fixed;

  right: 1.5rem;
  bottom: 1.5rem;

  z-index: 40;

  display: flex;

  align-items: center;

  gap: 0.5rem;

  padding: 0.6875rem 0.9375rem;

  border-radius: 0.5rem;

  background: #163e3b;

  color: #ecfffb;

  font-size: 0.6875rem;

  box-shadow: 0 0.75rem 1.875rem rgb(13 53 49 / 20%);
}

/* =========================================================
   Mobile
   ========================================================= */

@media (max-width: 47.5rem) {
  .app-topbar {
    height: 4rem;
    padding: 0 1rem;
  }

  .mobile-menu {
    display: inline-grid;
    margin-right: 0.5rem;
  }

  .is-showed {
    display: none;
  }

  .mobile-menu:hover,
  .icon-button:hover {
    border-color: #bfd4d2;
    color: var(--teal-dark);
  }

  .topbar-leading {
    flex: 0 0 auto;
  }

  .breadcrumbs {
    display: none;
  }

  .topbar-page-slot {
    flex: 1 1 auto;
    pointer-events: none;
  }

  .topbar-actions {
    gap: 0.5rem;
    flex: 0 0 auto;
  }

  .user-name {
    display: none;
  }
}
</style>
