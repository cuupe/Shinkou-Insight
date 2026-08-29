import { anet, unwrap } from "./core";
import { clearLocalSessionFailure } from "@/utils/request";
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
  SmsPurpose,
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
    password: async (payload: LoginByPasswordPayload) => {
      const result = await unwrap<LoginResponse>(
        anet.post<ApiResponse<LoginResponse>>("/auth/login/password", payload),
      );
      clearLocalSessionFailure();
      return result;
    },

    sms: async (payload: LoginBySmsPayload) => {
      const result = await unwrap<LoginResponse>(
        anet.post<ApiResponse<LoginResponse>>("/auth/login/sms", payload),
      );
      clearLocalSessionFailure();
      return result;
    },
  },

  sms: (payload: { phoneNumber: string; purpose: SmsPurpose }) =>
    unwrap<SmsResponse>(
      anet.get<ApiResponse<SmsResponse>>("/auth/sms", { params: payload }),
    ),

  register: (payload: RegisterPayload) =>
    unwrap<RegisterResponse>(
      anet.post<ApiResponse<RegisterResponse>>("/auth/register", payload),
    ),

  me: () => unwrap<AuthUser>(anet.get<ApiResponse<AuthUser>>("/auth/me")),

  updateProfile: (payload: {
    userName: string;
    email?: string;
    timezone: string;
  }) =>
    unwrap<AuthUser>(anet.patch<ApiResponse<AuthUser>>("/auth/me", payload)),

  updatePreferences: (payload: { activity: boolean; weeklyDigest: boolean }) =>
    unwrap<AuthUser>(
      anet.patch<ApiResponse<AuthUser>>("/auth/me/preferences", payload),
    ),

  updatePassword: (payload: {
    currentPassword: string;
    newPassword: string;
    verifyCodeId: string;
    verifyCode: string;
  }) => unwrap<void>(anet.put<ApiResponse<void>>("/auth/me/password", payload)),

  updatePhone: (payload: {
    newPhoneNumber: string;
    currentPassword: string;
    verifyCodeId: string;
    verifyCode: string;
  }) => unwrap<AuthUser>(anet.put<ApiResponse<AuthUser>>("/auth/me/phone", payload)),

  logout: async () => {
    const result = await unwrap<void>(anet.post<ApiResponse<void>>("/auth/logout"));
    clearLocalSessionFailure();
    return result;
  },
};
