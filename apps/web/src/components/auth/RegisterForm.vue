<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import {
  CheckCircle2Icon,
  EyeIcon,
  EyeOffIcon,
  MessageCircleMoreIcon,
} from "@lucide/vue";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import Agreement from "@/components/auth/Agreement.vue";
import AgreementDialog from "@/components/auth/AgreementDialog.vue";
import ImageCaptcha from "@/components/auth/ImageCaptcha.vue";
import SubmitButton from "@/components/auth/SubmitButton.vue";
import { useAuth } from "@/composables/useAuth";
import { useSmsCode } from "@/composables/useSmsCode";
import { ApiError, api } from "@/api";
import { getAuthFeedback } from "@/utils/authFeedback";
import { useRouter } from "vue-router";
const router = useRouter();
const { isPhone, isCode, isCaptcha } = useAuth();
const phone = ref("");
const smsCode = ref("");
const username = ref("");
const password = ref("");
const confirmPassword = ref("");
const captcha = ref("");
const captchaId = ref("");
const agreed = ref(false);
const isSubmitting = ref(false);
const errors = ref<Record<string, string>>({});
const status = ref<{
  type: "success" | "error" | "info";
  title: string;
  message: string;
} | null>(null);
const registrationSucceeded = ref(false);
const showPassword = ref(false);
const showConfirm = ref(false);
const agreementOpen = ref(false);
const agreementType = ref<"terms" | "privacy">("terms");
const smsSending = ref(false);
const {
  codeId: verifyCodeId,
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
function clearPhoneState() {
  clearErrors();
  clearSmsCode();
  smsCode.value = "";
}
function goToLogin() {
  void router.push({ name: "login" });
}
async function sendSms() {
  if (smsSending.value || smsCountdown.value > 0) return;
  if (!isPhone(phone.value)) {
    errors.value = { phone: "请输入正确的 11 位手机号" };
    return;
  }
  errors.value = {};
  status.value = null;
  smsSending.value = true;

  try {
    const response = await api.auth.sms({
      phoneNumber: phone.value.trim(),
      purpose: "REGISTER",
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
      "验证码发送失败，请稍后重试。",
    );
    // 接口错误统一展示在顶部提示，避免与字段下方重复显示同一条文案。
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
async function submit() {
  const next: Record<string, string> = {};
  if (!isPhone(phone.value)) next.phone = "请输入正确的 11 位手机号";
  if (!verifyCodeId.value)
    next.smsCode = smsExpired.value
      ? "手机验证码已过期，请重新获取"
      : "请先获取手机验证码";
  else if (!isCode(smsCode.value)) next.smsCode = "请输入 6 位手机验证码";
  if (username.value.trim().length < 2)
    next.username = "用户名至少需要 2 个字符";
  if (password.value.length < 12) next.password = "密码至少需要 12 个字符";
  if (password.value !== confirmPassword.value)
    next.confirmPassword = "两次输入的密码不一致";
  if (!isCaptcha(captcha.value)) next.captcha = "请输入图片验证码";
  if (!captchaId.value) next.captcha = "图片验证码已过期，请点击图片刷新";
  if (!agreed.value) next.agreement = "请先同意用户协议和隐私政策";
  errors.value = next;
  if (Object.keys(next).length) {
    status.value = {
      type: "error",
      title: "请检查注册信息",
      message: "还有信息未填写正确，请根据字段下方的红色提示修改后再提交。",
    };
    return;
  }
  status.value = null;
  isSubmitting.value = true;
  try {
    await api.auth.register({
      phoneNumber: phone.value,
      userName: username.value.trim(),
      password: password.value,
      captchaId: captchaId.value,
      captcha: captcha.value,
      verifyCodeId: verifyCodeId.value,
      verifyCode: smsCode.value,
    });
    registrationSucceeded.value = true;
  } catch (error) {
    const feedback = getAuthFeedback(
      error,
      "register",
      "注册失败，请稍后重试。",
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
function openAgreement(type: "terms" | "privacy") {
  agreementType.value = type;
  agreementOpen.value = true;
}
</script>

<template>
  <Card class="border-border/80 shadow-xl shadow-foreground/[0.04]"
    ><CardHeader class="px-6 pb-4 pt-6 sm:px-7"
      ><CardTitle class="text-xl">创建你的账号</CardTitle
      ><CardDescription
        >加入团队，开始沉淀有价值的洞察</CardDescription
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
      >
      <form
        v-if="!registrationSucceeded"
        class="flex flex-col gap-5"
        @submit.prevent="submit"
      >
        <FieldGroup
          ><Field :data-invalid="!!errors.phone"
            ><FieldLabel for="register-phone">手机号</FieldLabel
            ><Input
              id="register-phone"
              v-model="phone"
              type="tel"
              autocomplete="tel"
              placeholder="请输入 11 位手机号"
              :aria-invalid="!!errors.phone"
              @input="clearPhoneState"
            /><FieldError v-if="errors.phone">{{
              errors.phone
            }}</FieldError></Field
          ><Field :data-invalid="!!errors.username"
            ><FieldLabel for="register-username">用户名</FieldLabel
            ><Input
              id="register-username"
              v-model="username"
              autocomplete="username"
              placeholder="请输入用户名"
              :aria-invalid="!!errors.username"
              @input="clearErrors"
            /><FieldError v-if="errors.username">{{
              errors.username
            }}</FieldError></Field
          ><Field :data-invalid="!!errors.password"
            ><FieldLabel for="register-password">设置密码</FieldLabel>
            <div class="relative">
              <Input
                id="register-password"
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="至少 12 位，且包含多种字符"
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
          ><Field :data-invalid="!!errors.confirmPassword"
            ><FieldLabel for="register-confirm-password">确认密码</FieldLabel>
            <div class="relative">
              <Input
                id="register-confirm-password"
                v-model="confirmPassword"
                :type="showConfirm ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="再次输入密码"
                class="pr-10"
                :aria-invalid="!!errors.confirmPassword"
                @input="clearErrors"
              /><Button
                type="button"
                variant="ghost"
                size="icon-sm"
                class="absolute right-1 top-1/2 -translate-y-1/2"
                @click="showConfirm = !showConfirm"
                ><EyeOffIcon v-if="showConfirm" /><EyeIcon v-else
              /></Button>
            </div>
            <FieldError v-if="errors.confirmPassword">{{
              errors.confirmPassword
            }}</FieldError></Field
          ></FieldGroup
        ><FieldGroup
          ><Field :data-invalid="!!errors.smsCode"
            ><FieldLabel for="register-sms-code">手机验证码</FieldLabel>
            <div class="flex gap-2">
              <InputOTP
                id="register-sms-code"
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
            ><FieldDescription v-else>验证码 5 分钟内有效。</FieldDescription
            ><FieldError v-if="errors.smsCode">{{
              errors.smsCode
            }}</FieldError></Field
          ></FieldGroup
        ><ImageCaptcha
          id="register-captcha"
          v-model="captcha"
          v-model:captcha-id="captchaId"
          :error="errors.captcha"
          @refresh="captcha = ''"
        /><Agreement
          id="register-agreement"
          v-model="agreed"
          :error="errors.agreement"
          @open="openAgreement"
        /><SubmitButton :loading="isSubmitting">创建账号</SubmitButton>
      </form>
      <div v-else class="flex flex-col items-center gap-4 py-4 text-center">
        <p class="text-sm text-muted-foreground">
          注册信息已保存，现在可以使用手机号和密码登录。
        </p>
        <Button type="button" class="w-full" @click="goToLogin">
          去登录
        </Button>
      </div></CardContent
    ><CardFooter class="border-t px-6 pb-6 pt-4 sm:px-7"
      ><p class="flex items-center gap-2 text-xs text-muted-foreground">
        注册后即可邀请团队成员协作
      </p></CardFooter
    ></Card
  ><AgreementDialog v-model:open="agreementOpen" :type="agreementType" />
</template>
