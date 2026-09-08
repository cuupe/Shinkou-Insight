import { AxiosError, isAxiosError } from "axios";
import { anet } from "@/utils/request";
import type { ApiResponse } from "./types";

export { anet };

export async function unwrap<T>(
  request: Promise<{ data: ApiResponse<T> }>,
): Promise<T> {
  const response = await request;
  const body = response.data;
  if (!body || body.code !== "SUCCESS") {
    throw new ApiError(body?.message || "接口返回数据格式不正确", body?.code);
  }

  return body.data;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiErrorPayload = {
  code?: unknown;
  message?: unknown;
};

function getErrorPayload(error: unknown): ApiErrorPayload | undefined {
  if (!isAxiosError(error) || !error.response?.data) return undefined;
  const payload = error.response.data;
  return typeof payload === "object" ? (payload as ApiErrorPayload) : undefined;
}

export function getApiErrorCode(error: unknown) {
  if (error instanceof ApiError) return error.code;
  const code = getErrorPayload(error)?.code;
  return typeof code === "string" && code.trim() ? code : undefined;
}

export function getApiErrorStatus(error: unknown) {
  return isAxiosError(error) ? error.response?.status : undefined;
}

export function isApiUnavailable(error: unknown) {
  if (!isAxiosError(error)) return false;
  return !error.response || [502, 503, 504].includes(error.response.status);
}

function getResponseMessage(data: unknown) {
  if (typeof data === "string" && data.trim()) return data.trim();
  if (!data || typeof data !== "object") return undefined;

  const message = (data as { message?: unknown }).message;
  return typeof message === "string" && message.trim() ? message : undefined;
}

export function getApiErrorMessage(
  error: unknown,
  fallback = "请求失败，请稍后重试",
) {
  if (error instanceof ApiError) {
    return error.message || fallback;
  }

  if (error instanceof AxiosError || isAxiosError(error)) {
    return getResponseMessage(error.response?.data) || fallback;
  }

  return fallback;
}
