import { anet, unwrap } from "./core";
import { workspacePath } from "./paths";
import type { ApiResponse, EvaluationRun } from "./types";

export const evaluationApi = {
  create: (workspaceId: number | string, payload: Record<string, unknown>) =>
    unwrap<EvaluationRun>(
      anet.post<ApiResponse<EvaluationRun>>(
        `${workspacePath(workspaceId)}/evaluation-runs`,
        payload,
      ),
    ),

  detail: (workspaceId: number | string, id: number | string) =>
    unwrap<EvaluationRun>(
      anet.get<ApiResponse<EvaluationRun>>(
        `${workspacePath(workspaceId)}/evaluation-runs/${id}`,
      ),
    ),
};
