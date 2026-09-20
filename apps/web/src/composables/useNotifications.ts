import { computed, ref, watch, type Ref } from "vue";
import { notificationsApi } from "@/api/notifications";
import type { NotificationRecord } from "@/api";

export type NotificationKind =
  "research" | "knowledge" | "report" | "evaluation" | "workspace";

export type NotificationItem = NotificationRecord & {
  kind: NotificationKind;
  time: string;
};

const notifications = ref<NotificationItem[]>([]);
const loading = ref(false);
const loadedWorkspaceId = ref("");
let requestId = 0;

function normalizeKind(kind: string): NotificationKind {
  if (
    ["research", "knowledge", "report", "evaluation", "workspace"].includes(
      kind,
    )
  ) {
    return kind as NotificationKind;
  }
  return "workspace";
}

function relativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";

  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "刚刚";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} 天前`;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
  }).format(new Date(timestamp));
}

function mapNotification(record: NotificationRecord): NotificationItem {
  return {
    ...record,
    kind: normalizeKind(record.kind),
    time: relativeTime(record.createdAt),
  };
}

export function useNotifications(workspaceId: Ref<number | string>) {
  const unreadCount = computed(
    () =>
      notifications.value.filter((notification) => !notification.read).length,
  );

  async function load(force = false) {
    const currentWorkspaceId = String(workspaceId.value || "");
    if (
      !currentWorkspaceId ||
      (loadedWorkspaceId.value === currentWorkspaceId && !force)
    )
      return;

    const currentRequestId = ++requestId;
    loading.value = true;
    try {
      const records = await notificationsApi.list(currentWorkspaceId);
      if (currentRequestId !== requestId) return;
      notifications.value = records.map(mapNotification);
      loadedWorkspaceId.value = currentWorkspaceId;
    } catch {
      if (currentRequestId === requestId) {
        notifications.value = [];
        loadedWorkspaceId.value = currentWorkspaceId;
      }
    } finally {
      if (currentRequestId === requestId) loading.value = false;
    }
  }

  async function markRead(id: number | string) {
    const notification = notifications.value.find((item) => item.id === id);
    if (!notification || notification.read) return;

    notification.read = true;
    try {
      await notificationsApi.markRead(workspaceId.value, id);
    } catch {
      notification.read = false;
    }
  }

  async function markAllRead() {
    const unread = notifications.value.filter(
      (notification) => !notification.read,
    );
    if (!unread.length) return;

    unread.forEach((notification) => {
      notification.read = true;
    });
    try {
      await notificationsApi.markAllRead(workspaceId.value);
    } catch {
      unread.forEach((notification) => {
        notification.read = false;
      });
    }
  }

  watch(
    workspaceId,
    () => {
      loadedWorkspaceId.value = "";
      notifications.value = [];
      void load();
    },
    { immediate: true },
  );

  return {
    notifications,
    unreadCount,
    loading,
    load,
    markRead,
    markAllRead,
  };
}
