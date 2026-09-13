import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ApiResponse, ProjectPlan } from "./types";

export const planningApi = {
  detail: (workspaceId: number | string, projectId: number) =>
    unwrap<ProjectPlan>(
      anet.get<ApiResponse<ProjectPlan>>(
        `${projectPath(workspaceId, projectId)}/planning`,
      ),
    ),

  save: (
    workspaceId: number | string,
    projectId: number,
    payload: Omit<ProjectPlan, "projectId" | "workspaceId" | "updatedAt">,
  ) =>
    unwrap<ProjectPlan>(
      anet.put<ApiResponse<ProjectPlan>>(
        `${projectPath(workspaceId, projectId)}/planning`,
        payload,
      ),
    ),
};
