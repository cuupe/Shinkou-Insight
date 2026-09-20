import { anet, unwrap } from "./core";
import { workspacePath } from "./paths";
import type {
  ApiResponse,
  Workspace,
  WorkspaceInvitation,
  WorkspaceMember,
} from "./types";

export const workspaceApi = {
  list: () =>
    unwrap<Workspace[]>(anet.get<ApiResponse<Workspace[]>>("/workspaces/my")),

  create: (payload: { name: string; code?: string; description?: string }) =>
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

  remove: (workspaceId: number | string) =>
    unwrap<void>(anet.delete<ApiResponse<void>>(workspacePath(workspaceId))),

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
    unwrap<Record<string, unknown>>(
      anet.post<ApiResponse<Record<string, unknown>>>(
        `${workspacePath(workspaceId)}/invitations`,
        payload,
      ),
    ),

  myInvitations: () =>
    unwrap<WorkspaceInvitation[]>(
      anet.get<ApiResponse<WorkspaceInvitation[]>>("/workspace-invitations/me"),
    ),

  acceptInvitation: (invitationId: number | string) =>
    unwrap<{ workspaceId: number | string; status: string }>(
      anet.post<ApiResponse<{ workspaceId: number | string; status: string }>>(
        `/workspace-invitations/${invitationId}/accept`,
      ),
    ),

  declineInvitation: (invitationId: number | string) =>
    unwrap<void>(
      anet.post<ApiResponse<void>>(
        `/workspace-invitations/${invitationId}/decline`,
      ),
    ),

  revokeInvitation: (
    workspaceId: number | string,
    invitationId: number | string,
  ) =>
    unwrap<void>(
      anet.delete<ApiResponse<void>>(
        `${workspacePath(workspaceId)}/invitations/${invitationId}`,
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

  updatePreferences: (
    workspaceId: number | string,
    payload: Record<string, unknown>,
  ) =>
    unwrap<Workspace>(
      anet.patch<ApiResponse<Workspace>>(
        `${workspacePath(workspaceId)}/preferences`,
        payload,
      ),
    ),
};
