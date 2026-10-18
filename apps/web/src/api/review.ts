import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type {
  ApiResponse,
  ProjectReviewPolicy,
  ProjectReviewRun,
} from "./types";

export const reviewApi = {
  policy: (workspaceId: number | string, projectId: number) =>
    unwrap<ProjectReviewPolicy>(
      anet.get<ApiResponse<ProjectReviewPolicy>>(
        `${projectPath(workspaceId, projectId)}/review/policy`,
      ),
    ),

  savePolicy: (
    workspaceId: number | string,
    projectId: number,
    payload: Pick<
      ProjectReviewPolicy,
      | "requireCitations"
      | "verifyNumbers"
      | "escalateConflicts"
      | "labelExternal"
    >,
  ) =>
    unwrap<ProjectReviewPolicy>(
      anet.put<ApiResponse<ProjectReviewPolicy>>(
        `${projectPath(workspaceId, projectId)}/review/policy`,
        payload,
      ),
    ),

  latest: (workspaceId: number | string, projectId: number) =>
    unwrap<ProjectReviewRun | null>(
      anet.get<ApiResponse<ProjectReviewRun | null>>(
        `${projectPath(workspaceId, projectId)}/review/latest`,
      ),
    ),

  history: (workspaceId: number | string, projectId: number) =>
    unwrap<ProjectReviewRun[]>(
      anet.get<ApiResponse<ProjectReviewRun[]>>(
        `${projectPath(workspaceId, projectId)}/review/runs`,
      ),
    ),

  decide: (
    workspaceId: number | string,
    projectId: number,
    id: number | string,
    payload: {
      decision: "APPROVED" | "CHANGES_REQUESTED";
      comment: string;
      confirmations: string[];
    },
  ) =>
    unwrap<ProjectReviewRun>(
      anet.post<ApiResponse<ProjectReviewRun>>(
        `${projectPath(workspaceId, projectId)}/review/runs/${id}/decision`,
        payload,
      ),
    ),

  run: (
    workspaceId: number | string,
    projectId: number,
    reportId?: number | string,
  ) =>
    unwrap<ProjectReviewRun>(
      anet.post<ApiResponse<ProjectReviewRun>>(
        `${projectPath(workspaceId, projectId)}/review/runs`,
        { reportId },
      ),
    ),
};
