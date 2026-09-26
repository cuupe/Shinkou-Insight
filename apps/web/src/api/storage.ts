import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type { ApiResponse, StorageQuota } from "./types";

export const storageApi = {
  quota: (workspaceId: number | string, projectId: number) =>
    unwrap<StorageQuota>(
      anet.get<ApiResponse<StorageQuota>>(
        `${projectPath(workspaceId, projectId)}/storage/quota`,
      ),
    ),
};
