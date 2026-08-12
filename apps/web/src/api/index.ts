/**
 * 前端 API 合同占位区。
 * 后续接入时只需要替换这些函数的实现，不需要改动页面组件。
 * 认证约定：HttpOnly Cookie，不在前端保存 token。
 */
import { axios, anet } from "@/utils/request";

export interface CaptchaPayload {
  captchaId: string;
  imgUrl: string;
}

interface ApiResponse<T> {
  code: string;
  message: string;
  data: T;
}

export const api = {
  auth: {
    captcha: async (): Promise<CaptchaPayload> => {
      const response =
        await anet.get<ApiResponse<CaptchaPayload>>("/api/auth/captcha");
      return response.data.data;
    },
    login: async (_payload: unknown) => {},
    register: async (_payload: unknown) => {},
    me: async () => {},
  },
  workspace: {
    list: async () => Promise.reject(new Error("TODO: 接入工作区列表接口")),
    detail: async (_workspaceId: string) =>
      Promise.reject(new Error("TODO: 接入工作区详情接口")),
  },
  project: {
    list: async (_workspaceId: string) =>
      Promise.reject(new Error("TODO: 接入项目列表接口")),
    detail: async (_projectId: string) =>
      Promise.reject(new Error("TODO: 接入项目详情接口")),
  },
  assets: {
    list: async (_projectId: string) =>
      Promise.reject(new Error("TODO: 接入资产列表接口")),
    upload: async (_projectId: string, _file: File) =>
      Promise.reject(new Error("TODO: 接入资产上传接口")),
    retry: async (_assetId: string) =>
      Promise.reject(new Error("TODO: 接入资产重试接口")),
    remove: async (_assetId: string) =>
      Promise.reject(new Error("TODO: 接入资产删除接口")),
  },
  retrieval: {
    search: async (_payload: unknown) =>
      Promise.reject(new Error("TODO: 接入检索接口")),
  },
  runs: {
    create: async (_payload: unknown) =>
      Promise.reject(new Error("TODO: 接入调研创建接口")),
    detail: async (_runId: string) =>
      Promise.reject(new Error("TODO: 接入调研详情接口")),
    cancel: async (_runId: string) =>
      Promise.reject(new Error("TODO: 接入调研取消接口")),
    eventsUrl: (_runId: string) => "TODO: 接入 SSE 地址",
  },
  reports: {
    list: async (_projectId: string) =>
      Promise.reject(new Error("TODO: 接入报告列表接口")),
    detail: async (_reportId: string) =>
      Promise.reject(new Error("TODO: 接入报告详情接口")),
  },
  evaluation: {
    summary: async (_projectId: string) =>
      Promise.reject(new Error("TODO: 接入评估指标接口")),
  },
};
