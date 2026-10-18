import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ActionItem, ApiResponse, ReportActionDraft } from "./types";

export const actionItemsApi = {
  permissions: (workspaceId: number | string, projectId: number) =>
    unwrap<{ canManage: boolean }>(
      anet.get<ApiResponse<{ canManage: boolean }>>(
        `${projectPath(workspaceId, projectId)}/action-items/permissions`,
      ),
    ),
  reportDraft: (
    workspaceId: number | string,
    projectId: number,
    reportId: number | string,
  ) =>
    unwrap<ReportActionDraft>(
      anet.get<ApiResponse<ReportActionDraft>>(
        `${projectPath(workspaceId, projectId)}/action-items/report-draft/${reportId}`,
      ),
    ),
  importReport: (
    workspaceId: number | string,
    projectId: number,
    reportId: number | string,
    payload: Record<string, unknown>,
  ) =>
    unwrap<ActionItem[]>(
      anet.post<ApiResponse<ActionItem[]>>(
        `${projectPath(workspaceId, projectId)}/action-items/from-report/${reportId}`,
        payload,
      ),
    ),
  submit: (
    workspaceId: number | string,
    projectId: number,
    id: number | string,
    completionEvidence: string,
  ) =>
    unwrap<ActionItem>(
      anet.post<ApiResponse<ActionItem>>(
        `${projectPath(workspaceId, projectId)}/action-items/${id}/submit`,
        { completionEvidence },
      ),
    ),
  acceptance: (
    workspaceId: number | string,
    projectId: number,
    id: number | string,
    decision: "ACCEPT" | "RETURN",
    comment: string,
  ) =>
    unwrap<ActionItem>(
      anet.post<ApiResponse<ActionItem>>(
        `${projectPath(workspaceId, projectId)}/action-items/${id}/acceptance`,
        { decision, comment },
      ),
    ),
  create: (
    workspaceId: number | string,
    projectId: number,
    payload: Record<string, unknown>,
  ) =>
    unwrap<ActionItem>(
      anet.post<ApiResponse<ActionItem>>(
        `${projectPath(workspaceId, projectId)}/action-items`,
        payload,
      ),
    ),
  list: (workspaceId: number | string, projectId: number) =>
    unwrap<ActionItem[]>(
      anet.get<ApiResponse<ActionItem[]>>(
        `${projectPath(workspaceId, projectId)}/action-items`,
      ),
    ),

  update: (
    workspaceId: number | string,
    projectId: number,
    id: number | string,
    payload: Record<string, unknown>,
  ) =>
    unwrap<ActionItem>(
      anet.patch<ApiResponse<ActionItem>>(
        `${projectPath(workspaceId, projectId)}/action-items/${id}`,
        payload,
      ),
    ),
};
