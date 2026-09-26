import { anet, unwrap } from "./core";
import { projectPath } from "./paths";
import type {
  AgentAttachmentUploadResponse,
  AgentAttachmentPreviewResponse,
  AgentSendMessagePayload,
  AgentRunAccepted,
  AgentStreamEvent,
  AgentThreadHistory,
  ApiResponse,
} from "./types";

/**
 * Agent 工作台的后端契约：
 * 1. POST /agent/messages 接收用户消息并返回 runId/messageId；
 * 2. GET /agent/runs/:runId/events 以 SSE 推送 AgentStreamEvent；
 * 3. 前端只依赖事件类型，不依赖具体模型或工作流实现。
 */
export const agentApi = {
  threads: (workspaceId: number | string, projectId: number) =>
    unwrap<AgentThreadHistory[]>(
      anet.get<ApiResponse<AgentThreadHistory[]>>(
        `${projectPath(workspaceId, projectId)}/agent/threads`,
      ),
    ),

  deleteThread: (
    workspaceId: number | string,
    projectId: number,
    threadId: string,
  ) =>
    unwrap<void>(
      anet.delete<ApiResponse<void>>(
        `${projectPath(workspaceId, projectId)}/agent/threads/${encodeURIComponent(threadId)}`,
      ),
    ),

  sendMessage: (
    workspaceId: number | string,
    projectId: number,
    payload: AgentSendMessagePayload,
  ) =>
    unwrap<AgentRunAccepted>(
      anet.post<ApiResponse<AgentRunAccepted>>(
        `${projectPath(workspaceId, projectId)}/agent/messages`,
        payload,
      ),
    ),

  uploadAttachment: (
    workspaceId: number | string,
    projectId: number,
    file: File,
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    return unwrap<AgentAttachmentUploadResponse>(
      anet.post<ApiResponse<AgentAttachmentUploadResponse>>(
        `${projectPath(workspaceId, projectId)}/agent/attachments`,
        formData,
      ),
    );
  },

  listAttachments: (workspaceId: number | string, projectId: number) =>
    unwrap<AgentAttachmentUploadResponse[]>(
      anet.get<ApiResponse<AgentAttachmentUploadResponse[]>>(
        `${projectPath(workspaceId, projectId)}/agent/attachments`,
      ),
    ),

  previewAttachment: (
    workspaceId: number | string,
    projectId: number,
    attachmentId: string | number,
  ) =>
    unwrap<AgentAttachmentPreviewResponse>(
      anet.get<ApiResponse<AgentAttachmentPreviewResponse>>(
        `${projectPath(workspaceId, projectId)}/agent/attachments/${attachmentId}/preview`,
      ),
    ),

  cancelRun: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) =>
    unwrap<void>(
      anet.post<ApiResponse<void>>(
        `${projectPath(workspaceId, projectId)}/agent/runs/${runId}/cancel`,
      ),
    ),

  eventsUrl: (
    workspaceId: number | string,
    projectId: number,
    runId: number | string,
  ) => `/api${projectPath(workspaceId, projectId)}/agent/runs/${runId}/events`,

  parseEvent: (event: MessageEvent<string>): AgentStreamEvent | null => {
    try {
      return JSON.parse(event.data) as AgentStreamEvent;
    } catch {
      return null;
    }
  },
};
