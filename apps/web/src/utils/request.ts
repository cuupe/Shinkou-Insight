import Axios from "axios";

// 当前后端接口根路径是 /auth；兼容环境变量误配置为 .../api 的情况。
const configuredBaseURL = import.meta.env.VITE_API_BASE_URL || "";
const baseURL = configuredBaseURL.replace(/\/api\/?$/, "");

export const axios = Axios.create({
  baseURL,
  withCredentials: false,
});

// Authentication and workspace APIs use the HttpOnly session cookie.
export const anet = Axios.create({
  baseURL,
  withCredentials: true,
  xsrfCookieName: "XSRF-TOKEN",
  xsrfHeaderName: "X-XSRF-TOKEN",
});

// CSRF token is issued lazily before the first state-changing request. The
// shared promise prevents concurrent requests from creating multiple tokens.
const csrfClient = Axios.create({
  baseURL,
  withCredentials: true,
});
let csrfRequest: Promise<unknown> | null = null;

function hasCsrfCookie() {
  if (typeof document === "undefined") return true;
  return document.cookie.split(";").some((cookie) => {
    return cookie.trim().startsWith("XSRF-TOKEN=");
  });
}

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
  const method = config.method?.toUpperCase();
  const isStateChanging = method && !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);

  if (isStateChanging && config.url !== "/auth/csrf") {
    await ensureCsrfToken();
  }

  return config;
});
