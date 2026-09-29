import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type {
  ApiResponse,
  KnowledgeAnswerPayload,
  KnowledgeAnswerResponse,
  KnowledgeSearchPayload,
  KnowledgeSearchResponse,
} from "./types";

export const retrievalApi = {
  search: (
    workspaceId: number | string,
    projectId: number,
    payload: KnowledgeSearchPayload,
  ) =>
    unwrap<KnowledgeSearchResponse>(
      anet.post<ApiResponse<KnowledgeSearchResponse>>(
        `${projectPath(workspaceId, projectId)}/knowledge/search`,
        payload,
        { timeout: 95000 },
      ),
    ),

  answer: (
    workspaceId: number | string,
    projectId: number,
    payload: KnowledgeAnswerPayload,
  ) =>
    unwrap<KnowledgeAnswerResponse>(
      anet.post<ApiResponse<KnowledgeAnswerResponse>>(
        `${projectPath(workspaceId, projectId)}/knowledge/answer`,
        payload,
        { timeout: 95000 },
      ),
    ),
};
