import { anet, unwrap } from "./core";
import { workspacePath } from "./paths";
import type { ApiResponse, Workspace, WorkspaceMember } from "./types";

export const workspaceApi = {
  list: () =>
    unwrap<Workspace[]>(anet.get<ApiResponse<Workspace[]>>("/workspaces/my")),

  detail: (workspaceId: number | string) =>
    unwrap<Workspace>(
      anet.get<ApiResponse<Workspace>>(workspacePath(workspaceId)),
    ),

  update: (workspaceId: number | string, payload: Record<string, unknown>) =>
    unwrap<Workspace>(
      anet.patch<ApiResponse<Workspace>>(workspacePath(workspaceId), payload),
    ),

  members: (workspaceId: number | string) =>
    unwrap<WorkspaceMember[]>(
      anet.get<ApiResponse<WorkspaceMember[]>>(
        `${workspacePath(workspaceId)}/members`,
      ),
    ),
};
