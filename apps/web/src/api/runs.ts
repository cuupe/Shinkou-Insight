import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ApiResponse, ResearchRun } from "./types";

export const runsApi = {
  create: (
    workspaceId: number | string,
    projectId: number,
    payload: { goal: string } & Record<string, unknown>,
  ) =>
    unwrap<ResearchRun>(
      anet.post<ApiResponse<ResearchRun>>(
        `${projectPath(workspaceId, projectId)}/runs`,
        payload,
      ),
    ),

  list: (workspaceId: number | string, projectId: number) =>
    unwrap<ResearchRun[]>(
      anet.get<ApiResponse<ResearchRun[]>>(
        `${projectPath(workspaceId, projectId)}/runs`,
      ),
    ),

  detail: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
    signal?: AbortSignal,
  ) =>
    unwrap<ResearchRun>(
      anet.get<ApiResponse<ResearchRun>>(
        `${projectPath(workspaceId, projectId)}/runs/${runId}`,
        { signal, timeout: 10000 },
      ),
    ),

  cancel: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) =>
    unwrap<ResearchRun>(
      anet.post<ApiResponse<ResearchRun>>(
        `${projectPath(workspaceId, projectId)}/runs/${runId}/cancel`,
      ),
    ),

  retry: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) =>
    unwrap<ResearchRun>(
      anet.post<ApiResponse<ResearchRun>>(
        `${projectPath(workspaceId, projectId)}/runs/${runId}/retry`,
      ),
    ),

  updatePlan: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
    payload: Record<string, unknown>,
  ) =>
    unwrap<Record<string, unknown>>(
      anet.patch<ApiResponse<Record<string, unknown>>>(
        `${projectPath(workspaceId, projectId)}/runs/${runId}/plan`,
        payload,
      ),
    ),

  steps: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) =>
    unwrap<Record<string, unknown>[]>(
      anet.get<ApiResponse<Record<string, unknown>[]>>(
        `${projectPath(workspaceId, projectId)}/runs/${runId}/steps`,
      ),
    ),

  tools: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) =>
    unwrap<Record<string, unknown>[]>(
      anet.get<ApiResponse<Record<string, unknown>[]>>(
        `${projectPath(workspaceId, projectId)}/runs/${runId}/tools`,
      ),
    ),

  evidences: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) =>
    unwrap<Record<string, unknown>[]>(
      anet.get<ApiResponse<Record<string, unknown>[]>>(
        `${projectPath(workspaceId, projectId)}/runs/${runId}/evidences`,
      ),
    ),

  eventsUrl: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) => `${projectPath(workspaceId, projectId)}/runs/${runId}/events`,
};
