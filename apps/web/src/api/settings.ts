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
}

const settingsPath = (workspaceId: number | string, projectId: number) =>
  `${projectPath(workspaceId, projectId)}/settings`;

export const settingsApi = {
  prompts: {
    list: (workspaceId: number | string) =>
      unwrap<Record<string, unknown>[]>(
        anet.get<ApiResponse<Record<string, unknown>[]>>(
          `/workspaces/${workspaceId}/settings/prompts`,
        ),
      ),
    create: (workspaceId: number | string, payload: Record<string, unknown>) =>
      unwrap<Record<string, unknown>>(
        anet.post<ApiResponse<Record<string, unknown>>>(
          `/workspaces/${workspaceId}/settings/prompts`,
          payload,
        ),
      ),
    update: (
      workspaceId: number | string,
      id: number | string,
      payload: Record<string, unknown>,
    ) =>
      unwrap<Record<string, unknown>>(
        anet.patch<ApiResponse<Record<string, unknown>>>(
          `/workspaces/${workspaceId}/settings/prompts/${id}`,
          payload,
        ),
      ),
  },
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
};
