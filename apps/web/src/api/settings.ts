import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ApiResponse } from "./types";

export interface ProjectModelConfig {
  id: number | string;
  projectId: number;
  name: string;
  provider: string;
  modelId: string;
  endpoint: string;
  authType: string;
  hasCredential: boolean;
  config?: string;
  enabled: boolean;
  scope?: "PERSONAL" | string;
}

export interface ProjectToolConfig {
  id: number | string;
  projectId: number;
  name: string;
  connectorType: string;
  endpoint: string;
  authType: string;
  hasCredential: boolean;
  config?: string;
  enabled: boolean;
  scope?: "PERSONAL" | "TEAM" | string;
}

export interface WebSearchConfig {
  id?: number | string;
  projectId: number;
  provider: "brave" | "duckduckgo" | string;
  baseUrl: string;
  language: string;
  hasCredential: boolean;
  enabled: boolean;
}

const settingsPath = (workspaceId: number | string, projectId: number) =>
  `${projectPath(workspaceId, projectId)}/settings`;

export const settingsApi = {
  models: {
    list: (workspaceId: number | string, projectId: number) =>
      unwrap<ProjectModelConfig[]>(
        anet.get<ApiResponse<ProjectModelConfig[]>>(
          `${settingsPath(workspaceId, projectId)}/models`,
        ),
      ),
    create: (
      workspaceId: number | string,
      projectId: number,
      payload: Record<string, unknown>,
    ) =>
      unwrap<ProjectModelConfig>(
        anet.post<ApiResponse<ProjectModelConfig>>(
          `${settingsPath(workspaceId, projectId)}/models`,
          payload,
        ),
      ),
    update: (
      workspaceId: number | string,
      projectId: number,
      id: number | string,
      payload: Record<string, unknown>,
    ) =>
      unwrap<ProjectModelConfig>(
        anet.patch<ApiResponse<ProjectModelConfig>>(
          `${settingsPath(workspaceId, projectId)}/models/${id}`,
          payload,
        ),
      ),
    remove: (workspaceId: number | string, projectId: number, id: number | string) =>
      unwrap<void>(
        anet.delete<ApiResponse<void>>(
          `${settingsPath(workspaceId, projectId)}/models/${id}`,
        ),
      ),
    test: (workspaceId: number | string, projectId: number, id: number | string) =>
      unwrap<{ status: string; model?: string; latencyMs?: number }>(
        anet.post<ApiResponse<{ status: string; model?: string; latencyMs?: number }>>(
          `${settingsPath(workspaceId, projectId)}/models/${id}/test`,
        ),
      ),
    testEmbedding: (workspaceId: number | string, projectId: number, id: number | string) =>
      unwrap<{ status: string; model?: string; dimension?: number; latencyMs?: number }>(
        anet.post<ApiResponse<{ status: string; model?: string; dimension?: number; latencyMs?: number }>>(
          `${settingsPath(workspaceId, projectId)}/models/${id}/test-embedding`,
        ),
      ),
  },
  tools: {
    list: (workspaceId: number | string, projectId: number) =>
      unwrap<ProjectToolConfig[]>(
        anet.get<ApiResponse<ProjectToolConfig[]>>(
          `${settingsPath(workspaceId, projectId)}/tools`,
        ),
      ),
    create: (
      workspaceId: number | string,
      projectId: number,
      payload: Record<string, unknown>,
    ) =>
      unwrap<ProjectToolConfig>(
        anet.post<ApiResponse<ProjectToolConfig>>(
          `${settingsPath(workspaceId, projectId)}/tools`,
          payload,
        ),
      ),
    update: (
      workspaceId: number | string,
      projectId: number,
      id: number | string,
      payload: Record<string, unknown>,
    ) =>
      unwrap<ProjectToolConfig>(
        anet.patch<ApiResponse<ProjectToolConfig>>(
          `${settingsPath(workspaceId, projectId)}/tools/${id}`,
          payload,
        ),
      ),
    remove: (workspaceId: number | string, projectId: number, id: number | string) =>
      unwrap<void>(
        anet.delete<ApiResponse<void>>(
          `${settingsPath(workspaceId, projectId)}/tools/${id}`,
        ),
      ),
  },
  webSearch: {
    get: (workspaceId: number | string, projectId: number) =>
      unwrap<WebSearchConfig | null>(
        anet.get<ApiResponse<WebSearchConfig | null>>(
          `${settingsPath(workspaceId, projectId)}/web-search`,
        ),
      ),
    save: (
      workspaceId: number | string,
      projectId: number,
      payload: Record<string, unknown>,
    ) =>
      unwrap<WebSearchConfig>(
        anet.put<ApiResponse<WebSearchConfig>>(
          `${settingsPath(workspaceId, projectId)}/web-search`,
          payload,
        ),
      ),
    test: (workspaceId: number | string, projectId: number) =>
      unwrap<{ status: string; provider?: string; resultCount?: number; latencyMs?: number }>(
        anet.post<ApiResponse<{ status: string; provider?: string; resultCount?: number; latencyMs?: number }>>(
          `${settingsPath(workspaceId, projectId)}/web-search/test`,
        ),
      ),
  },
};
