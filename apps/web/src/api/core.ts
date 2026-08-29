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

function getResponseMessage(data: unknown) {
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
