<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import {
  CheckCircle2Icon,
  EyeIcon,
  EyeOffIcon,
  LockKeyholeIcon,
  MessageCircleMoreIcon,
  ShieldCheckIcon,
} from "@lucide/vue";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Agreement from "@/components/auth/Agreement.vue";
import AgreementDialog from "@/components/auth/AgreementDialog.vue";
import ImageCaptcha from "@/components/auth/ImageCaptcha.vue";
import RecoveryDialog from "@/components/auth/RecoveryDialog.vue";
import SubmitButton from "@/components/auth/SubmitButton.vue";
import { useAuth } from "@/composables/useAuth";
import { useSmsCode } from "@/composables/useSmsCode";
import { ApiError, api } from "@/api";
import { getAuthFeedback } from "@/utils/authFeedback";
import { getLastProject } from "@/utils/lastProject";
import { useRouter } from "vue-router";
type Status = {
  type: "success" | "error" | "info";
  title: string;
  message: string;
};
const router = useRouter();
const { isPhone, isCode, isCaptcha } = useAuth();
const rememberedPhone = localStorage.getItem("shinkou-login-phone") || "";
const loginMode = ref("password");
const showPassword = ref(false);
const remember = ref(Boolean(rememberedPhone));
const agreed = ref(false);
const isSubmitting = ref(false);
const status = ref<Status | null>(null);
const errors = ref<Record<string, string>>({});
const phone = ref(rememberedPhone);
const password = ref("");
const smsCode = ref("");
const captcha = ref("");
const captchaId = ref("");
const recoveryOpen = ref(false);
const agreementOpen = ref(false);
const agreementType = ref<"terms" | "privacy">("terms");
const smsSending = ref(false);
const {
  codeId: smsId,
  resendCountdown: smsCountdown,
  expired: smsExpired,
  start: startSmsCode,
  markExpired: markSmsExpired,
  clear: clearSmsCode,
  stopTimer: stopSmsTimer,
} = useSmsCode();
onUnmounted(stopSmsTimer);
watch(smsExpired, (value) => {
  if (value) smsCode.value = "";
});
function clearErrors() {
  errors.value = {};
  status.value = null;
}
function refreshCaptcha() {
  captcha.value = "";
}
function clearSmsState() {
  clearErrors();
  clearSmsCode();
  smsCode.value = "";
}
async function submit() {
  const next: Record<string, string> = {};
  if (!isPhone(phone.value)) next.phone = "请输入正确的 11 位手机号";
  if (loginMode.value === "password" && !password.value)
    next.password = "请输入登录密码";
  if (loginMode.value === "sms") {
    if (!smsId.value)
      next.smsCode = smsExpired.value
        ? "短信验证码已过期，请重新获取"
        : "请先获取短信验证码";
    else if (!isCode(smsCode.value)) next.smsCode = "请输入 6 位短信验证码";
  }
  if (!isCaptcha(captcha.value)) next.captcha = "请输入图片验证码";
  if (!captchaId.value) next.captcha = "图片验证码已过期，请点击图片刷新";
  if (!agreed.value) next.agreement = "请先同意用户协议和隐私政策";
  errors.value = next;
  if (Object.keys(next).length) {
    status.value = {
      type: "error",
      title: "请检查表单",
      message: "还有信息未填写正确，请根据字段下方的红色提示修改后再提交。",
    };
    return;
  }
  isSubmitting.value = true;

  try {
    if (loginMode.value === "password") {
      await api.auth.login.password({
        phoneNumber: phone.value,
        password: password.value,
        captcha: captcha.value,
        captchaId: captchaId.value,
      });
    } else {
      const response = await api.auth.login.sms({
        phoneNumber: phone.value,
        verifyCode: smsCode.value,
        verifyCodeId: smsId.value,
        captcha: captcha.value,
        captchaId: captchaId.value,
      });

      if (!response) throw new ApiError("短信登录失败", "AUTH_LOGIN_FAILED");
    }
    if (remember.value && loginMode.value === "password")
      localStorage.setItem("shinkou-login-phone", phone.value);
    else localStorage.removeItem("shinkou-login-phone");
    status.value = {
      type: "success",
      title: "登录成功",
      message: "登录成功，正在为你打开工作台…",
    };

    // 给用户一个可见的成功反馈，避免登录页瞬间消失让人误以为按钮没有响应。
    await new Promise((resolve) => window.setTimeout(resolve, 450));

    try {
      const landingRoute = await resolveLandingRoute();
      const navigationFailure = await router.replace({
        name: landingRoute.name,
        params: landingRoute.params,
      });

      if (navigationFailure) {
        status.value = {
          type: "error",
          title: "工作台打开失败",
          message: "登录成功，但工作台打开失败，请刷新页面后重试。",
        };
      }
    } catch {
      status.value = {
        type: "error",
        title: "工作台打开失败",
        message: "登录成功，但工作台打开失败，请刷新页面后重试。",
      };
    }
  } catch (error) {
    const feedback = getAuthFeedback(
      error,
      loginMode.value === "password" ? "login-password" : "login-sms",
      "登录失败，请稍后重试。",
    );
    if (feedback.markSmsExpired) {
      markSmsExpired();
      smsCode.value = "";
    }
    // 接口错误统一展示在顶部提示，避免与字段下方重复显示同一条文案。
    errors.value = {};
    status.value = {
      type: "error",
      title: feedback.title,
      message: feedback.message,
    };
  } finally {
    isSubmitting.value = false;
  }
}

async function resolveLandingRoute() {
  const workspaces = await api.workspace.list().catch(() => []);
  const lastProject = getLastProject();

  if (lastProject) {
    const workspace = workspaces.find(
      (item) => String(item.id) === lastProject.workspaceId,
    );
    if (workspace) {
      const projects = await api.project.list(workspace.id).catch(() => []);
      if (projects.some((project) => project.id === lastProject.projectId)) {
        return {
          name: "project-agent-chat" as const,
          params: {
            workspaceId: String(workspace.id),
            projectId: lastProject.projectId,
          },
        };
      }
    }
  }

  return {
    name: "workspace-dashboard" as const,
    params: { workspaceId: String(workspaces[0]?.id || "shinkou-labs") },
  };
}
async function sendSms() {
  if (smsSending.value || smsCountdown.value > 0) return;
  if (!isPhone(phone.value)) {
    errors.value = { phone: "请输入正确的 11 位手机号" };
    return;
  }
  status.value = null;
  smsSending.value = true;
  try {
    const response = await api.auth.sms({
      phoneNumber: phone.value.trim(),
      purpose: "LOGIN",
      captchaId: captchaId.value,
      captcha: captcha.value,
    });
    if (!response.smsId) {
      throw new ApiError("短信验证码发送失败，请稍后重试。", "SMS_ID_MISSING");
    }
    smsCode.value = "";
    startSmsCode(response.smsId);
  } catch (error) {
    const feedback = getAuthFeedback(
      error,
      "send-sms",
      "验证码发送失败，请刷新页面后重试。",
    );
    // 发送验证码失败时只保留顶部提示，避免同一错误在手机号字段下再次出现。
    errors.value = {};
    status.value = {
      type: "error",
      title: feedback.title,
      message: feedback.message,
    };
  } finally {
    smsSending.value = false;
  }
}
function openAgreement(type: "terms" | "privacy") {
  agreementType.value = type;
  agreementOpen.value = true;
}
</script>

<template>
  <Card class="border-border/80 shadow-xl shadow-foreground/[0.04]"
    ><CardHeader class="px-6 pb-4 pt-6 sm:px-7"
      ><CardTitle class="text-xl">登录 Shinkou</CardTitle
      ><CardDescription
        >使用手机号密码或短信验证码登录</CardDescription
      ></CardHeader
    ><CardContent class="px-6 sm:px-7"
      ><Alert
        v-if="status"
        class="mb-5"
        role="alert"
        aria-live="polite"
        :variant="status.type === 'error' ? 'destructive' : 'default'"
        ><CheckCircle2Icon
          v-if="status.type === 'success'"
        /><MessageCircleMoreIcon v-else /><AlertTitle>{{
          status.title
        }}</AlertTitle
        ><AlertDescription>{{ status.message }}</AlertDescription></Alert
      ><Tabs v-model="loginMode"
        ><TabsList
          variant="line"
          class="mb-6 w-full justify-start gap-6 rounded-none border-b"
          ><TabsTrigger value="password" class="flex-none px-0"
            >密码登录</TabsTrigger
          ><TabsTrigger value="sms" class="flex-none px-0"
            >验证码登录</TabsTrigger
          ></TabsList
        ><TabsContent value="password"
          ><form class="flex flex-col gap-5" @submit.prevent="submit">
            <FieldGroup
              ><Field :data-invalid="!!errors.phone"
                ><FieldLabel for="login-phone-password">手机号</FieldLabel
                ><Input
                  id="login-phone-password"
                  v-model="phone"
                  type="tel"
                  autocomplete="tel"
                  placeholder="请输入 11 位手机号"
                  :aria-invalid="!!errors.phone"
                  @input="clearErrors"
                /><FieldError v-if="errors.phone">{{
                  errors.phone
                }}</FieldError></Field
              ><Field :data-invalid="!!errors.password"
                ><div class="flex items-center justify-between">
                  <FieldLabel for="login-password">登录密码</FieldLabel
                  ><Button
                    type="button"
                    variant="link"
                    class="h-auto p-0 text-xs text-muted-foreground"
                    @click="recoveryOpen = true"
                    >忘记密码？</Button
                  >
                </div>
                <div class="relative">
                  <Input
                    id="login-password"
                    v-model="password"
                    :type="showPassword ? 'text' : 'password'"
                    autocomplete="current-password"
                    placeholder="请输入密码"
                    class="pr-10"
                    :aria-invalid="!!errors.password"
                    @input="clearErrors"
                  /><Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    class="absolute right-1 top-1/2 -translate-y-1/2"
                    @click="showPassword = !showPassword"
                    ><EyeOffIcon v-if="showPassword" /><EyeIcon v-else
                  /></Button>
                </div>
                <FieldError v-if="errors.password">{{
                  errors.password
                }}</FieldError></Field
              ></FieldGroup
            ><ImageCaptcha
              id="login-password-captcha"
              v-model="captcha"
              v-model:captcha-id="captchaId"
              :error="errors.captcha"
              @refresh="refreshCaptcha"
            /><Agreement
              id="login-agreement"
              v-model="agreed"
              :error="errors.agreement"
              @open="openAgreement"
            /><Field orientation="horizontal" class="items-center gap-2"
              ><Checkbox id="remember-password" v-model="remember" /><FieldLabel
                for="remember-password"
                class="text-xs font-normal text-muted-foreground"
                >记住登录账号</FieldLabel
              ></Field
            ><SubmitButton :loading="isSubmitting">登录</SubmitButton>
          </form></TabsContent
        ><TabsContent value="sms"
          ><form class="flex flex-col gap-5" @submit.prevent="submit">
            <FieldGroup
              ><Field :data-invalid="!!errors.phone"
                ><FieldLabel for="login-phone">手机号</FieldLabel
                ><Input
                  id="login-phone"
                  v-model="phone"
                  type="tel"
                  autocomplete="tel"
                  placeholder="请输入 11 位手机号"
                  :aria-invalid="!!errors.phone"
                  @input="clearSmsState"
                /><FieldError v-if="errors.phone">{{
                  errors.phone
                }}</FieldError></Field
              ><Field :data-invalid="!!errors.smsCode"
                ><FieldLabel for="login-sms-code">短信验证码</FieldLabel>
                <div class="login-code-row flex gap-2">
                  <InputOTP
                    id="login-sms-code"
                    v-model="smsCode"
                    :maxlength="6"
                    class="min-w-0 flex-1"
                    @input="clearErrors"
                    ><InputOTPGroup class="w-full justify-between"
                      ><InputOTPSlot
                        v-for="index in 6"
                        :key="index"
                        :index="index - 1" /></InputOTPGroup></InputOTP
                  ><Button
                    type="button"
                    variant="outline"
                    class="shrink-0 px-3 text-xs"
                    :disabled="smsSending || smsCountdown > 0"
                    @click="sendSms"
                    ><span v-if="smsSending">发送中...</span
                    ><span v-else-if="smsCountdown > 0"
                      >{{ smsCountdown }}s 后重新获取</span
                    ><span v-else>获取验证码</span></Button
                  >
                </div>
                <FieldDescription v-if="smsExpired"
                  >验证码已过期，请重新获取。</FieldDescription
                ><FieldDescription v-else
                  >验证码 5 分钟内有效。</FieldDescription
                ><FieldError v-if="errors.smsCode">{{
                  errors.smsCode
                }}</FieldError></Field
              ></FieldGroup
            ><ImageCaptcha
              id="login-sms-captcha"
              v-model="captcha"
              v-model:captcha-id="captchaId"
              :error="errors.captcha"
              @refresh="refreshCaptcha"
            /><Agreement
              id="sms-agreement"
              v-model="agreed"
              :error="errors.agreement"
              @open="openAgreement"
            /><SubmitButton :loading="isSubmitting">登录</SubmitButton>
          </form></TabsContent
        ></Tabs
      ></CardContent
    ><CardFooter class="border-t px-6 pb-6 pt-4 sm:px-7"
      ><div class="flex w-full justify-between text-xs text-muted-foreground">
        <span class="flex items-center gap-1.5"
          ><ShieldCheckIcon class="text-brand" />数据全程加密</span
        ><span class="flex items-center gap-1.5"
          ><LockKeyholeIcon />安全登录</span
        >
      </div></CardFooter
    ></Card
  ><RecoveryDialog v-model:open="recoveryOpen" :phone="phone" /><AgreementDialog
    v-model:open="agreementOpen"
    :type="agreementType"
  />
</template>
