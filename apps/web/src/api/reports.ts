import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ApiResponse, Report } from "./types";

export const reportsApi = {
  list: (workspaceId: number | string, projectId: number) =>
    unwrap<Report[]>(
      anet.get<ApiResponse<Report[]>>(
        `${projectPath(workspaceId, projectId)}/reports`,
      ),
    ),

  detail: (workspaceId: number | string, projectId: number, reportId: number | string) =>
    unwrap<Report>(
      anet.get<ApiResponse<Report>>(
        `${projectPath(workspaceId, projectId)}/reports/${reportId}`,
      ),
    ),

  update: (
    workspaceId: number | string,
    projectId: number,
    reportId: number | string,
    payload: Record<string, unknown>,
  ) =>
    unwrap<Report>(
      anet.patch<ApiResponse<Report>>(
        `${projectPath(workspaceId, projectId)}/reports/${reportId}`,
        payload,
      ),
    ),

  export: (
    workspaceId: number | string,
    projectId: number,
    reportId: number | string,
    format = "markdown",
  ) =>
    anet
      .get<Blob>(
        `${projectPath(workspaceId, projectId)}/reports/${reportId}/export`,
        { params: { format }, responseType: "blob" },
      )
      .then((response) => response.data),
};
