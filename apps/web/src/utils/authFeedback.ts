import {
  getApiErrorCode,
  getApiErrorMessage,
  getApiErrorStatus,
  isApiUnavailable,
} from "@/api/core";

export type AuthErrorField = "phone" | "password" | "smsCode" | "captcha";
export type AuthErrorContext =
  "login-password" | "login-sms" | "register" | "send-sms";

export interface AuthFeedback {
  title: string;
  message: string;
  field?: AuthErrorField;
  markSmsExpired?: boolean;
}

export function getAuthFeedback(
  error: unknown,
  context: AuthErrorContext,
  fallback: string,
): AuthFeedback {
  const code = getApiErrorCode(error);
  const status = getApiErrorStatus(error);
  const message = getApiErrorMessage(error, fallback);

  if (isApiUnavailable(error)) {
    return {
      title: "暂时无法连接服务器",
      message: "请确认后端服务已启动，检查网络后再试。",
    };
  }

  if (
    status === 403 &&
    message.trim().toLowerCase() === "invalid cors request"
  ) {
    return {
      title: "前后端地址配置不一致",
      message:
        "登录请求被服务端拦截，请确认前端地址已加入后端允许列表，并重启后端服务。",
    };
  }

  switch (code) {
    case "AUTH_LOGIN_FAILED":
      return {
        title: "登录信息不正确",
        message: "手机号或密码错误，请检查后重试；还没有账号可以先注册。",
        field: context === "login-password" ? "password" : "phone",
      };
    case "AUTH_ACCOUNT_UNAVAILABLE":
      return {
        title: "账号不可用",
        message: "该手机号未注册或账号已被停用，请检查手机号，或先注册账号。",
        field: "phone",
      };
    case "AUTH_ACCOUNT_LOCKED":
      return {
        title: "账号暂时锁定",
        message: "登录失败次数过多，请 15 分钟后再试。",
      };
    case "CAPTCHA_INVALID":
      return {
        title: "图片验证码不正确",
        message: "验证码可能输错或已过期，请点击图片刷新后重新输入。",
        field: "captcha",
      };
    case "SMS_CODE_INVALID":
      return {
        title: "短信验证码无效",
        message: "验证码可能输错或已过期，请重新获取后再试。",
        field: "smsCode",
        markSmsExpired: true,
      };
    case "PHONE_ALREADY_REGISTERED":
      return {
        title: "手机号已注册",
        message: "这个手机号已经有账号了，请直接登录，不需要重复注册。",
        field: "phone",
      };
    case "INVALID_PHONE":
      return {
        title: "手机号格式不正确",
        message: "请输入正确的 11 位手机号。",
        field: "phone",
      };
    case "VALIDATION_ERROR":
      return {
        title: "提交信息不完整",
        message,
      };
    default:
      if (status && status >= 500) {
        return {
          title: "服务器暂时出错",
          message: "服务端没有完成这次操作，请稍后重试。",
        };
      }
      return {
        title: "操作失败",
        message,
      };
  }
}
