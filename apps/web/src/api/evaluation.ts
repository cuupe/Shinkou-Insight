import { anet, unwrap } from "./core";
import { workspacePath } from "./paths";
import type { ApiResponse, EvaluationRun } from "./types";

export const evaluationApi = {
  list: (workspaceId: number | string) =>
    unwrap<EvaluationRun[]>(
      anet.get<ApiResponse<EvaluationRun[]>>(
        `${workspacePath(workspaceId)}/evaluation-cases`,
      ),
    ),
  create: (workspaceId: number | string, payload: Record<string, unknown>) =>
    unwrap<EvaluationRun>(
      anet.post<ApiResponse<EvaluationRun>>(
        `${workspacePath(workspaceId)}/evaluation-cases`,
        payload,
      ),
    ),
};
