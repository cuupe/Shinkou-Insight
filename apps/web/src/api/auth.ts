import { anet, unwrap } from "./core";
import type {
  ApiResponse,
  AuthUser,
  CaptchaPayload,
  CsrfTokenResponse,
  LoginByPasswordPayload,
  LoginBySmsPayload,
  LoginResponse,
  RegisterPayload,
  RegisterResponse,
  SmsResponse,
} from "./types";

export const authApi = {
  csrf: () =>
    unwrap<CsrfTokenResponse>(
      anet.get<ApiResponse<CsrfTokenResponse>>("/auth/csrf"),
    ),

  captcha: () =>
    unwrap<CaptchaPayload>(
      anet.get<ApiResponse<CaptchaPayload>>("/auth/captcha"),
    ),

  login: {
    password: (payload: LoginByPasswordPayload) =>
      unwrap<LoginResponse>(
        anet.post<ApiResponse<LoginResponse>>(
          "/auth/login/password",
          payload,
        ),
      ),

    sms: (payload: LoginBySmsPayload) =>
      unwrap<LoginResponse>(
        anet.post<ApiResponse<LoginResponse>>("/auth/login/sms", payload),
      ),
  },

  sms: () =>
    unwrap<SmsResponse>(anet.get<ApiResponse<SmsResponse>>("/auth/sms")),

  register: (payload: RegisterPayload) =>
    unwrap<RegisterResponse>(
      anet.post<ApiResponse<RegisterResponse>>("/auth/register", payload),
    ),

  me: () => unwrap<AuthUser>(anet.get<ApiResponse<AuthUser>>("/auth/me")),

  logout: () => unwrap<void>(anet.post<ApiResponse<void>>("/auth/logout")),
};
