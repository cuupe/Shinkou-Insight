import type { ActionItem } from "../api/types.ts";
const actionDateFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai",
});
export type ActionRow = ActionItem & {
  id: string;
  description: string;
  owner: string;
  due: string;
  priority: string;
  status: string;
};
export function actionRow(item: ActionItem): ActionRow {
  const status = String(item.status || "DRAFT")
    .toUpperCase()
    .replace(/-/g, "_");
  const priority = String(item.priority || "MEDIUM").toUpperCase();
  return {
    ...item,
    id: String(item.id),
    title: String(item.title || "未命名行动项"),
    description: String(item.description || ""),
    owner: String(item.owner || "未分配"),
    due: String(item.dueAt || "待安排"),
    priority:
      priority === "HIGH" || priority === "高"
        ? "高"
        : priority === "LOW" || priority === "低"
          ? "低"
          : "中",
    status:
      (
        {
          DRAFT: "todo",
          TODO: "todo",
          IN_PROGRESS: "in-progress",
          ACCEPTED: "in-progress",
          PENDING_ACCEPTANCE: "pending-acceptance",
          DONE: "done",
          COMPLETED: "done",
          REJECTED: "rejected",
        } as Record<string, string>
      )[status] || "todo",
  };
}
export function actionCommand(item: ActionItem) {
  const status = actionRow(item).status;
  if (
    item.canManage &&
    actionMetadataEditable(item) &&
    !item.acceptanceCriteria?.trim()
  )
    return { command: "assign", label: "完善验收标准" };
  if (item.canManage && actionMetadataEditable(item) && !item.ownerId)
    return { command: "assign", label: "分派负责人" };
  if (status === "pending-acceptance")
    return item.canAccept ? { command: "accept", label: "验收任务" } : null;
  if (status === "done")
    return item.canManage ? { command: "start", label: "重新打开" } : null;
  if (!item.canEdit) return null;
  if (status === "in-progress") return { command: "submit", label: "提交验收" };
  return {
    command: "start",
    label: status === "rejected" ? "继续处理" : "开始处理",
  };
}
export function actionMetadataEditable(item: ActionItem) {
  const status = actionRow(item).status;
  return (
    !!item.canManage &&
    status !== "pending-acceptance" &&
    (status !== "done" || !item.acceptedAt)
  );
}

export function isActionVerified(item: ActionItem) {
  return actionRow(item).status === "done" && !!item.acceptedAt;
}

export function actionDisplayStatus(item: ActionItem) {
  const status = actionRow(item).status;
  return status === "done" && !isActionVerified(item) ? "todo" : status;
}

export function actionBoardBucket(item: ActionItem) {
  const status = actionDisplayStatus(item);
  return status === "rejected" ? "todo" : status;
}

export function actionDue(
  item: ActionItem,
  today = actionDateFormatter.format(new Date()),
) {
  const value = String(item.dueAt || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value))
    return {
      label: "未设截止",
      full: "尚未设置截止日期",
      overdue: false,
      today: false,
    };
  const overdue = !isActionVerified(item) && value < today;
  const dueToday = !isActionVerified(item) && value === today;
  return {
    label: dueToday
      ? "今天截止"
      : `${Number(value.slice(5, 7))}月${Number(value.slice(8, 10))}日`,
    full: `截止日期：${value}${overdue ? "（已逾期）" : ""}`,
    overdue,
    today: dueToday,
  };
}

export function actionStatusLabel(item: ActionItem) {
  const status = actionRow(item).status;
  if (status === "done" && !isActionVerified(item)) return "待补验收";
  return (
    (
      {
        todo: "待处理",
        "in-progress": "进行中",
        "pending-acceptance": "待验收",
        done: "已验收",
        rejected: "退回修改",
      } as Record<string, string>
    )[status] || "待处理"
  );
}
