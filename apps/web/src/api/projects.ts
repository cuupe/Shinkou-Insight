import { anet, unwrap } from "./core";
import { projectPath, workspacePath } from "./paths";
import type { ApiResponse, Project } from "./types";

export const projectApi = {
  list: (workspaceId: number | string) =>
    unwrap<Project[]>(
      anet.get<ApiResponse<Project[]>>(
        `${workspacePath(workspaceId)}/projects`,
      ),
    ),

  create: (
    workspaceId: number | string,
    payload: Pick<Project, "name"> & Record<string, unknown>,
  ) =>
    unwrap<Project>(
      anet.post<ApiResponse<Project>>(
        `${workspacePath(workspaceId)}/projects`,
        payload,
      ),
    ),

  detail: (workspaceId: number | string, projectId: number | string) =>
    unwrap<Project>(
      anet.get<ApiResponse<Project>>(projectPath(workspaceId, projectId)),
    ),

  update: (
    workspaceId: number | string,
    projectId: number | string,
    payload: Record<string, unknown>,
  ) =>
    unwrap<Project>(
      anet.patch<ApiResponse<Project>>(
        projectPath(workspaceId, projectId),
        payload,
      ),
    ),

  remove: (workspaceId: number | string, projectId: number | string) =>
    unwrap<void>(
      anet.delete<ApiResponse<void>>(projectPath(workspaceId, projectId)),
    ),
};
