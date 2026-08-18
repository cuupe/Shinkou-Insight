import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ActionItem, ApiResponse } from "./types";

export const actionItemsApi = {
  list: (workspaceId: number | string, projectId: number | string) =>
    unwrap<ActionItem[]>(
      anet.get<ApiResponse<ActionItem[]>>(
        `${projectPath(workspaceId, projectId)}/action-items`,
      ),
    ),

  update: (
    workspaceId: number | string,
    projectId: number | string,
    id: number | string,
    payload: Record<string, unknown>,
  ) =>
    unwrap<ActionItem>(
      anet.patch<ApiResponse<ActionItem>>(
        `${projectPath(workspaceId, projectId)}/action-items/${id}`,
        payload,
      ),
    ),

  accept: (
    workspaceId: number | string,
    projectId: number | string,
    id: number | string,
  ) => actionItemsApi.update(workspaceId, projectId, id, { status: "accepted" }),

  reject: (
    workspaceId: number | string,
    projectId: number | string,
    id: number | string,
  ) => actionItemsApi.update(workspaceId, projectId, id, { status: "rejected" }),
};
