import { anet, unwrap } from "./core";
import { projectPath, workspacePath } from "./paths";
import type { ApiResponse } from "./types";

export interface ProjectModelConfig {
  id: number | string;
  workspaceId: number | string;
  projectId?: number;
  name: string;
  provider: string;
  modelId: string;
  endpoint: string;
  authType: string;
  hasCredential: boolean;
  config?: string;
  enabled: boolean;
  defaultModel: boolean;
  editable: boolean;
  createdBy?: number | string;
  visibility?: "PERSONAL" | "PROJECT_CREATOR" | "DEFAULT" | string;
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
  provider: "brave" | "duckduckgo" | "multi" | "hybrid" | string;
  baseUrl: string;
  language: string;
  hasCredential: boolean;
  enabled: boolean;
}

export interface LocalToolSpec {
  name: string;
  version: string;
  description: string;
  permission: "READ" | "WRITE" | string;
  timeoutSeconds: number;
  maxConcurrency: number;
  requiresConfirmation: boolean;
  inputSchema?: Record<string, unknown>;
  source: "builtin" | "custom" | "mcp" | string;
}

export interface LocalFileToolsStatus {
  supportedExtensions: string[];
  ocr: {
    enabled: boolean;
    tesseract: boolean;
    poppler: boolean;
    languages?: string | null;
  };
  media: {
    ffmpeg: boolean;
    ffprobe: boolean;
    whisper: boolean;
    model?: string | null;
  };
  office: { libreoffice: boolean };
}

export interface LocalToolsStatus {
  tools: LocalToolSpec[];
  async: boolean;
  chains: boolean;
  custom: {
    directory: string;
    modules: string[];
    tools: string[];
    errors: string[];
  };
  files: LocalFileToolsStatus;
}

const settingsPath = (workspaceId: number | string, projectId: number) =>
  `${projectPath(workspaceId, projectId)}/settings`;
const workspaceModelPath = (workspaceId: number | string) =>
  `${workspacePath(workspaceId)}/settings/models`;

export const settingsApi = {
  models: {
    list: (workspaceId: number | string, projectId?: number) =>
      unwrap<ProjectModelConfig[]>(
        anet.get<ApiResponse<ProjectModelConfig[]>>(
          projectId == null
            ? workspaceModelPath(workspaceId)
            : `${settingsPath(workspaceId, projectId)}/models`,
        ),
      ),
    create: (workspaceId: number | string, payload: Record<string, unknown>) =>
      unwrap<ProjectModelConfig>(
        anet.post<ApiResponse<ProjectModelConfig>>(
          workspaceModelPath(workspaceId),
          payload,
        ),
      ),
    update: (
      workspaceId: number | string,
      id: number | string,
      payload: Record<string, unknown>,
    ) =>
      unwrap<ProjectModelConfig>(
        anet.patch<ApiResponse<ProjectModelConfig>>(
          `${workspaceModelPath(workspaceId)}/${id}`,
          payload,
        ),
      ),
    remove: (workspaceId: number | string, id: number | string) =>
      unwrap<void>(
        anet.delete<ApiResponse<void>>(
          `${workspaceModelPath(workspaceId)}/${id}`,
        ),
      ),
    test: (workspaceId: number | string, id: number | string) =>
      unwrap<{ status: string; model?: string; latencyMs?: number }>(
        anet.post<
          ApiResponse<{ status: string; model?: string; latencyMs?: number }>
        >(`${workspaceModelPath(workspaceId)}/${id}/test`),
      ),
    context: (workspaceId: number | string, id: number | string) =>
      unwrap<{
        status: string;
        available?: boolean;
        model?: string;
        contextWindow?: number;
        source?: string;
        detail?: string;
        latencyMs?: number;
      }>(
        anet.post<
          ApiResponse<{
            status: string;
            available?: boolean;
            model?: string;
            contextWindow?: number;
            source?: string;
            detail?: string;
            latencyMs?: number;
          }>
        >(`${workspaceModelPath(workspaceId)}/${id}/context`),
      ),
    testEmbedding: (workspaceId: number | string, id: number | string) =>
      unwrap<{
        status: string;
        model?: string;
        dimension?: number;
        latencyMs?: number;
      }>(
        anet.post<
          ApiResponse<{
            status: string;
            model?: string;
            dimension?: number;
            latencyMs?: number;
          }>
        >(`${workspaceModelPath(workspaceId)}/${id}/test-embedding`),
      ),
    setDefault: (
      workspaceId: number | string,
      modelId: number | string | null,
    ) =>
      unwrap<ProjectModelConfig[]>(
        anet.put<ApiResponse<ProjectModelConfig[]>>(
          `${workspaceModelPath(workspaceId)}/default`,
          { modelId },
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
    remove: (
      workspaceId: number | string,
      projectId: number,
      id: number | string,
    ) =>
      unwrap<void>(
        anet.delete<ApiResponse<void>>(
          `${settingsPath(workspaceId, projectId)}/tools/${id}`,
        ),
      ),
  },
  localTools: {
    get: (workspaceId: number | string, projectId: number) =>
      unwrap<LocalToolsStatus>(
        anet.get<ApiResponse<LocalToolsStatus>>(
          `${settingsPath(workspaceId, projectId)}/local-tools`,
        ),
      ),
    reload: (workspaceId: number | string, projectId: number) =>
      unwrap<LocalToolsStatus>(
        anet.post<ApiResponse<LocalToolsStatus>>(
          `${settingsPath(workspaceId, projectId)}/local-tools/reload`,
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
      unwrap<{
        status: string;
        provider?: string;
        resultCount?: number;
        latencyMs?: number;
      }>(
        anet.post<
          ApiResponse<{
            status: string;
            provider?: string;
            resultCount?: number;
            latencyMs?: number;
          }>
        >(`${settingsPath(workspaceId, projectId)}/web-search/test`),
      ),
  },
};
