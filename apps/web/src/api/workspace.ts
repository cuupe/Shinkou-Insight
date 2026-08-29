import { anet, unwrap } from "./core";
import { workspacePath } from "./paths";
import type { ApiResponse, Workspace, WorkspaceMember } from "./types";

export const workspaceApi = {
  list: () =>
    unwrap<Workspace[]>(anet.get<ApiResponse<Workspace[]>>("/workspaces/my")),

  create: (payload: {
    name: string;
    code?: string;
    description?: string;
  }) =>
    unwrap<Workspace>(
      anet.post<ApiResponse<Workspace>>("/workspaces", payload),
    ),

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

  invite: (
    workspaceId: number | string,
    payload: {
      phoneNumber: string;
      role: string;
      department?: string;
      title?: string;
      inviteNote?: string;
    },
  ) =>
    unwrap<Record<string, string>>(
      anet.post<ApiResponse<Record<string, string>>>(
        `${workspacePath(workspaceId)}/invitations`,
        payload,
      ),
    ),

  updateMemberRole: (
    workspaceId: number | string,
    memberId: number | string,
    role: string,
  ) =>
    unwrap<void>(
      anet.patch<ApiResponse<void>>(
        `${workspacePath(workspaceId)}/members/${memberId}`,
        { role },
      ),
    ),

  updatePreferences: (workspaceId: number | string, payload: Record<string, unknown>) =>
    unwrap<Workspace>(
      anet.patch<ApiResponse<Workspace>>(
        `${workspacePath(workspaceId)}/preferences`,
        payload,
      ),
    ),
};
