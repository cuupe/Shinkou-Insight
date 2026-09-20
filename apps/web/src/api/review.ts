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

  run: (workspaceId: number | string, projectId: number) =>
    unwrap<ProjectReviewRun>(
      anet.post<ApiResponse<ProjectReviewRun>>(
        `${projectPath(workspaceId, projectId)}/review/runs`,
      ),
    ),
};
