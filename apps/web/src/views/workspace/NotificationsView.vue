<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Activity,
  BarChart3,
  Bell,
  Check,
  Database,
  FileText,
  Users,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useNotifications, type NotificationItem, type NotificationKind } from "@/composables/useNotifications";
import { useWorkspace } from "@/composables/useWorkspace";

const { router, routeTo, workspaceId } = useWorkspace();
const { notifications, unreadCount, loading, markRead, markAllRead } = useNotifications(workspaceId);
const filter = ref<"all" | "unread">("all");

const filteredNotifications = computed(() =>
  filter.value === "unread"
    ? notifications.value.filter((notification) => !notification.read)
    : notifications.value,
);
const kindCount = computed(
  () => new Set(notifications.value.map((notification) => notification.kind)).size,
);

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
  if (!notification.routeName) return;
  if (notification.routeName.startsWith("project-") && notification.projectId) {
    router.push({
      name: notification.routeName,
      params: {
        workspaceId: workspaceId.value,
        projectId: notification.projectId,
      },
    });
    return;
  }
  router.push(routeTo(notification.routeName));
}
</script>

<template>
  <div class="notifications-page">
    <PageHeader
      eyebrow="NOTIFICATION CENTER"
      title="通知中心"
      subtitle="集中查看调研、知识库、报告和工作区中的最新动态。"
    >
      <template #actions>
        <button
          class="notifications-mark-all"
          type="button"
          :disabled="!unreadCount"
          @click="markAllRead"
        >
          <Check :size="15" />
          全部标为已读
        </button>
      </template>
    </PageHeader>

    <section class="notifications-summary" aria-label="通知概览">
      <div class="notifications-summary-card">
        <span>全部通知</span>
        <strong>{{ notifications.length }}</strong>
        <small>工作区近期动态</small>
      </div>

      <div class="notifications-summary-card is-highlighted">
        <span>未读通知</span>
        <strong>{{ unreadCount }}</strong>
        <small>{{ unreadCount ? "有内容需要查看" : "你已经处理完所有通知" }}</small>
      </div>

      <div class="notifications-summary-card">
        <span>通知类型</span>
        <strong>{{ kindCount }}</strong>
        <small>调研、知识库、报告等</small>
      </div>
    </section>

    <section class="notifications-panel" aria-label="通知列表">
      <div class="notifications-panel-header">
        <div>
          <span class="section-kicker">ACTIVITY FEED</span>
          <h2>最近通知</h2>
        </div>

        <div class="notifications-tabs" role="tablist" aria-label="通知筛选">
          <button
            type="button"
            :class="{ active: filter === 'all' }"
            role="tab"
            :aria-selected="filter === 'all'"
            @click="filter = 'all'"
          >
            全部 <span>{{ notifications.length }}</span>
          </button>
          <button
            type="button"
            :class="{ active: filter === 'unread' }"
            role="tab"
            :aria-selected="filter === 'unread'"
            @click="filter = 'unread'"
          >
            未读 <span>{{ unreadCount }}</span>
          </button>
        </div>
      </div>

      <div v-if="loading" class="notifications-page-empty">
        <strong>正在加载通知</strong>
      </div>

      <div v-else-if="filteredNotifications.length" class="notifications-feed">
        <button
          v-for="notification in filteredNotifications"
          :key="notification.id"
          class="notifications-feed-item"
          :class="{ 'is-unread': !notification.read }"
          type="button"
          @click="openNotification(notification)"
        >
          <span class="notifications-feed-icon" :class="`kind-${notification.kind}`">
            <component :is="notificationIcon(notification.kind)" :size="18" />
          </span>

          <span class="notifications-feed-copy">
            <span class="notifications-feed-title">
              <strong>{{ notification.title }}</strong>
              <i v-if="!notification.read">未读</i>
            </span>
            <small>{{ notification.body }}</small>
            <em>{{ notification.time }}</em>
          </span>

          <span class="notifications-feed-arrow">查看</span>
        </button>
      </div>

      <div v-else class="notifications-page-empty">
        <Bell :size="24" />
        <strong>{{ filter === "unread" ? "暂无未读通知" : "暂无通知" }}</strong>
        <span>新的调研、报告和工作区动态会显示在这里。</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.notifications-page {
  display: grid;
  gap: 1.25rem;
  min-height: 100%;
  padding-bottom: 2rem;
}

.notifications-mark-all {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface);
  color: var(--workspace-muted);
  font: inherit;
  font-size: 0.6875rem;
  cursor: pointer;
}

.notifications-mark-all:hover,
.notifications-mark-all:focus-visible {
  border-color: #a8cbc7;
  color: var(--teal-dark);
}

.notifications-mark-all:disabled {
  cursor: default;
  opacity: 0.5;
}

.notifications-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.875rem;
}

.notifications-summary-card {
  display: grid;
  gap: 0.3rem;
  min-height: 7.5rem;
  padding: 1.125rem 1.25rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: 0 0.5rem 1.5rem rgb(21 53 52 / 4%);
}

.notifications-summary-card.is-highlighted {
  border-color: #c5e3df;
  background: linear-gradient(135deg, #f3fbf9, var(--surface));
}

.notifications-summary-card span,
.notifications-summary-card small {
  color: var(--workspace-muted);
  font-size: 0.625rem;
}

.notifications-summary-card strong {
  color: var(--workspace-text);
  font-size: 1.75rem;
  line-height: 1;
}

.notifications-summary-card small {
  margin-top: auto;
}

.notifications-panel {
  overflow: hidden;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.875rem;
  background: var(--surface);
  box-shadow: 0 0.75rem 2rem rgb(21 53 52 / 5%);
}

.notifications-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.375rem 1rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.section-kicker {
  color: var(--teal-dark);
  font-size: 0.5625rem;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.notifications-panel h2 {
  margin: 0.25rem 0 0;
  color: var(--workspace-text);
  font-size: 1rem;
}

.notifications-tabs {
  display: flex;
  gap: 0.875rem;
}

.notifications-tabs button {
  padding: 0.375rem 0;
  border: 0;
  border-bottom: 0.125rem solid transparent;
  background: transparent;
  color: var(--workspace-muted);
  font: inherit;
  font-size: 0.6875rem;
  cursor: pointer;
}

.notifications-tabs button.active {
  border-bottom-color: var(--teal);
  color: var(--teal-dark);
  font-weight: 700;
}

.notifications-tabs button span {
  margin-left: 0.125rem;
  opacity: 0.75;
}

.notifications-feed {
  display: grid;
}

.notifications-feed-item {
  display: grid;
  grid-template-columns: 2.5rem minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.875rem;
  width: 100%;
  padding: 1rem 1.375rem;
  border: 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.notifications-feed-item:last-child {
  border-bottom: 0;
}

.notifications-feed-item:hover,
.notifications-feed-item:focus-visible,
.notifications-feed-item.is-unread {
  background: color-mix(in oklab, var(--teal-soft) 36%, transparent);
}

.notifications-feed-icon {
  display: inline-grid;
  width: 2.5rem;
  height: 2.5rem;
  place-items: center;
  border-radius: 0.75rem;
  color: var(--teal-dark);
  background: var(--teal-soft);
}

.notifications-feed-icon.kind-research { color: #6d58b5; background: #f0ebff; }
.notifications-feed-icon.kind-knowledge { color: #4778a8; background: #e9f3fb; }
.notifications-feed-icon.kind-report { color: #af6a35; background: #fff2e6; }
.notifications-feed-icon.kind-evaluation { color: #188b82; background: #e4f7f3; }
.notifications-feed-icon.kind-workspace { color: #a34f74; background: #fcecf3; }

.notifications-feed-copy {
  display: grid;
  min-width: 0;
  gap: 0.3rem;
}

.notifications-feed-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.notifications-feed-title strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}

.notifications-feed-title i {
  padding: 0.125rem 0.375rem;
  border-radius: 999px;
  background: var(--teal-soft);
  color: var(--teal-dark);
  font-size: 0.5rem;
  font-style: normal;
  font-weight: 700;
}

.notifications-feed-copy small {
  overflow: hidden;
  color: var(--workspace-muted);
  font-size: 0.6875rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notifications-feed-copy em {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  font-style: normal;
}

.notifications-feed-arrow {
  color: var(--teal-dark);
  font-size: 0.625rem;
  opacity: 0;
  transition: opacity 160ms ease;
}

.notifications-feed-item:hover .notifications-feed-arrow,
.notifications-feed-item:focus-visible .notifications-feed-arrow {
  opacity: 1;
}

.notifications-page-empty {
  display: grid;
  justify-items: center;
  gap: 0.5rem;
  padding: 4rem 1.5rem;
  color: var(--workspace-muted);
  text-align: center;
}

.notifications-page-empty svg { color: var(--teal); }
.notifications-page-empty strong { color: var(--workspace-text); font-size: 0.875rem; }
.notifications-page-empty span { font-size: 0.6875rem; }

@media (max-width: 47.5rem) {
  .notifications-summary { grid-template-columns: 1fr; }
  .notifications-summary-card { min-height: 6rem; }
  .notifications-panel-header { align-items: flex-start; flex-direction: column; }
  .notifications-feed-item { grid-template-columns: 2.25rem minmax(0, 1fr); padding: 0.875rem 1rem; }
  .notifications-feed-icon { width: 2.25rem; height: 2.25rem; }
  .notifications-feed-arrow { display: none; }
}
</style>
