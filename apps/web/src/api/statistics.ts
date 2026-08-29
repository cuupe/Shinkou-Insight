import { anet, unwrap } from "./core";
import { projectPath, workspacePath } from "./paths";
import type { ApiResponse, StatisticsResponse } from "./types";

export const statisticsApi = {
  workspace: (workspaceId: number | string, days = 30) =>
    unwrap<StatisticsResponse>(
      anet.get<ApiResponse<StatisticsResponse>>(
        `${workspacePath(workspaceId)}/statistics`,
        { params: { days } },
      ),
    ),
  project: (workspaceId: number | string, projectId: number, days = 30) =>
    unwrap<StatisticsResponse>(
      anet.get<ApiResponse<StatisticsResponse>>(
        `${projectPath(workspaceId, projectId)}/statistics`,
        { params: { days } },
      ),
    ),
};
