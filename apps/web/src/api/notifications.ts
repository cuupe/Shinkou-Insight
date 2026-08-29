import { anet, unwrap } from "./core";
import { workspacePath } from "./paths";
import type { ApiResponse, NotificationRecord } from "./types";

export const notificationsApi = {
  list: (workspaceId: number | string) =>
    unwrap<NotificationRecord[]>(
      anet.get<ApiResponse<NotificationRecord[]>>(
        `${workspacePath(workspaceId)}/notifications`,
      ),
    ),

  markRead: (workspaceId: number | string, id: number | string) =>
    unwrap<void>(
      anet.patch<ApiResponse<void>>(
        `${workspacePath(workspaceId)}/notifications/${id}/read`,
      ),
    ),

  markAllRead: (workspaceId: number | string) =>
    unwrap<void>(
      anet.patch<ApiResponse<void>>(
        `${workspacePath(workspaceId)}/notifications/read-all`,
      ),
    ),
};
