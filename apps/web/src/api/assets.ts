import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ApiResponse, KnowledgeAsset } from "./types";

export const assetsApi = {
  list: (workspaceId: number | string, projectId: number | string) =>
    unwrap<KnowledgeAsset[]>(
      anet.get<ApiResponse<KnowledgeAsset[]>>(
        `${projectPath(workspaceId, projectId)}/assets`,
      ),
    ),

  detail: (
    workspaceId: number | string,
    projectId: number | string,
    assetId: number | string,
  ) =>
    unwrap<KnowledgeAsset>(
      anet.get<ApiResponse<KnowledgeAsset>>(
        `${projectPath(workspaceId, projectId)}/assets/${assetId}`,
      ),
    ),

  upload: (
    workspaceId: number | string,
    projectId: number | string,
    file: File,
    options: { name?: string; language?: string } = {},
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (options.name) formData.append("name", options.name);
    if (options.language) formData.append("language", options.language);

    return unwrap<KnowledgeAsset>(
      anet.post<ApiResponse<KnowledgeAsset>>(
        `${projectPath(workspaceId, projectId)}/assets`,
        formData,
      ),
    );
  },

  reindex: (
    workspaceId: number | string,
    projectId: number | string,
    assetId: number | string,
  ) =>
    unwrap<KnowledgeAsset>(
      anet.post<ApiResponse<KnowledgeAsset>>(
        `${projectPath(workspaceId, projectId)}/assets/${assetId}/reindex`,
      ),
    ),

  remove: (
    workspaceId: number | string,
    projectId: number | string,
    assetId: number | string,
  ) =>
    unwrap<void>(
      anet.delete<ApiResponse<void>>(
        `${projectPath(workspaceId, projectId)}/assets/${assetId}`,
      ),
    ),

  chunks: (
    workspaceId: number | string,
    projectId: number | string,
    assetId: number | string,
  ) =>
    unwrap<Record<string, unknown>[]>(
      anet.get<ApiResponse<Record<string, unknown>[]>>(
        `${projectPath(workspaceId, projectId)}/assets/${assetId}/chunks`,
      ),
    ),

  content: (
    workspaceId: number | string,
    projectId: number | string,
    assetId: number | string,
  ) =>
    unwrap<string>(
      anet.get<ApiResponse<string>>(
        `${projectPath(workspaceId, projectId)}/assets/${assetId}/content`,
      ),
    ),
};
