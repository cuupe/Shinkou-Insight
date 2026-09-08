import { anet, unwrap } from "./core";
import type { ApiResponse } from "./types";

export type HarnessCase = {
  code: string;
  name: string;
  category: string;
  severity: string;
  description: string;
  modelProbe?: boolean;
};

export type HarnessRun = {
  id: number | string;
  workspaceId: number | string;
  projectId?: number | string;
  status: string;
  mode: string;
  totalCases: number;
  passedCases: number;
  failedCases: number;
  blockedCases: number;
  score: number;
  errorMessage?: string;
  startedAt?: string;
  finishedAt?: string;
  createdAt?: string;
};

export type HarnessResult = {
  id?: number | string;
  runId: number | string;
  caseCode: string;
  name: string;
  category: string;
  severity: string;
  status: string;
  message: string;
  evidence?: string;
};

export type AuditLogEntry = {
  id: number | string;
  workspaceId?: number | string;
  projectId?: number | string;
  actorUserId?: number | string;
  action: string;
  resourceType: string;
  resourceId?: string;
  outcome: string;
  details?: string;
  createdAt?: string;
};

const root = (workspaceId: number | string) => `/workspaces/${workspaceId}/security-harness`;

export const securityApi = {
  cases: (workspaceId: number | string) => unwrap<HarnessCase[]>(anet.get<ApiResponse<HarnessCase[]>>(`${root(workspaceId)}/cases`)),
  runs: (workspaceId: number | string) => unwrap<HarnessRun[]>(anet.get<ApiResponse<HarnessRun[]>>(`${root(workspaceId)}/runs`)),
  start: (workspaceId: number | string, payload: { projectId: number; caseIds?: string[]; includeModelProbes?: boolean }) => unwrap<HarnessRun>(anet.post<ApiResponse<HarnessRun>>(`${root(workspaceId)}/runs`, payload)),
  detail: (workspaceId: number | string, runId: number | string) => unwrap<{ run: HarnessRun; results: HarnessResult[] }>(anet.get<ApiResponse<{ run: HarnessRun; results: HarnessResult[] }>>(`${root(workspaceId)}/runs/${runId}`)),
  auditLogs: (workspaceId: number | string, limit = 50) => unwrap<AuditLogEntry[]>(anet.get<ApiResponse<AuditLogEntry[]>>(`/workspaces/${workspaceId}/audit-logs`, { params: { limit } })),
};
