import Axios, { type AxiosError } from "axios";

const baseURL: string = "/api";

// Authentication and workspace APIs use the HttpOnly session cookie.
export const anet = Axios.create({
  baseURL,
  withCredentials: true,
  timeout: 10000,
  xsrfCookieName: "XSRF-TOKEN",
  xsrfHeaderName: "X-XSRF-TOKEN",
});

// Keep the legacy export on the same secured client so a new API module cannot
// accidentally bypass the session, CSRF, timeout, or response interceptors.
export const axios = anet;

// CSRF token is issued lazily before the first state-changing request. The
// shared promise prevents concurrent requests from creating multiple tokens.
const csrfClient = Axios.create({
  baseURL,
  withCredentials: true,
  timeout: 5000,
});
let csrfRequest: Promise<unknown> | null = null;
let authFailureHandler: ((reason: "unauthorized" | "backend-unavailable") => void) | null = null;
let authFailureInProgress = false;
const SESSION_INVALID_KEY = "shinkou-session-invalid";

export function setAuthFailureHandler(
  handler: (reason: "unauthorized" | "backend-unavailable") => void,
) {
  authFailureHandler = handler;
}

export function isSessionLocallyInvalid() {
  try {
    return sessionStorage.getItem(SESSION_INVALID_KEY) === "1";
  } catch {
    return false;
  }
}

export function clearLocalSessionFailure() {
  try {
    sessionStorage.removeItem(SESSION_INVALID_KEY);
  } catch {
    // Storage can be disabled by the browser; the server session remains the
    // source of truth in that case.
  }
}

function markSessionInvalid() {
  try {
    sessionStorage.setItem(SESSION_INVALID_KEY, "1");
  } catch {
    // Redirecting still provides a safe fallback when storage is unavailable.
  }
}

function clearCsrfCookie() {
  if (typeof document === "undefined") return;
  document.cookie = "XSRF-TOKEN=; Max-Age=0; path=/";
}

function hasCsrfCookie() {
  if (typeof document === "undefined") return true;
  return document.cookie.split(";").some((cookie) => {
    return cookie.trim().startsWith("XSRF-TOKEN=");
  });
}

function isPublicAuthRequest(config?: AxiosError["config"]) {
  const url = config?.url ?? "";
  return [
    "/auth/captcha",
    "/auth/csrf",
    "/auth/login/",
    "/auth/register",
    "/auth/sms",
    "/auth/password/reset",
    "/auth/logout",
  ].some((path) => url === path || url.startsWith(path));
}

function handleAuthFailure(reason: "unauthorized" | "backend-unavailable") {
  if (authFailureInProgress) return;
  authFailureInProgress = true;
  // 后端不可用不代表当前登录会话失效。测试连接、网络抖动或后端重启
  // 都可能暂时返回 502/503；保留当前页面和会话，交给业务页面展示错误。
  if (reason === "unauthorized") {
    markSessionInvalid();
    clearCsrfCookie();
  }
  authFailureHandler?.(reason);

  // Allow a later, genuine session failure to be handled after the current
  // request burst has settled without causing redirect loops.
  window.setTimeout(() => {
    authFailureInProgress = false;
  }, 1000);
}

csrfClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (!error.response || [502, 503, 504].includes(error.response.status)) {
      handleAuthFailure("backend-unavailable");
    }
    return Promise.reject(error);
  },
);

export function ensureCsrfToken() {
  if (hasCsrfCookie()) return Promise.resolve();
  if (!csrfRequest) {
    csrfRequest = csrfClient.get("/auth/csrf").finally(() => {
      csrfRequest = null;
    });
  }
  return csrfRequest;
}

anet.interceptors.request.use(async (config) => {
  config.headers = config.headers ?? {};
  config.headers["X-Requested-With"] = "XMLHttpRequest";

  const method = config.method?.toUpperCase();
  const isStateChanging =
    method && !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);

  if (isStateChanging && config.url !== "/auth/csrf") {
    await ensureCsrfToken();
  }

  return config;
});

anet.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status;
    const unavailable =
      !error.response || [502, 503, 504].includes(status ?? 0);

    // Login/captcha/registration failures are user-facing form errors and
    // must not kick the user out of the login page.
    if (!isPublicAuthRequest(error.config)) {
      if (status === 401) {
        handleAuthFailure("unauthorized");
      } else if (unavailable) {
        handleAuthFailure("backend-unavailable");
      }
    }

    return Promise.reject(error);
  },
);
