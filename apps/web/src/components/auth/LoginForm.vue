<script setup lang="ts">
import { ref } from "vue";
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
type Status = { type: "success" | "error" | "info"; message: string };
const { isPhone, isCode, isCaptcha } = useAuth();
const loginMode = ref("password");
const showPassword = ref(false);
const remember = ref(false);
const agreed = ref(false);
const isSubmitting = ref(false);
const status = ref<Status | null>(null);
const errors = ref<Record<string, string>>({});
const phone = ref(localStorage.getItem("shinkou-login-phone") || "");
const password = ref("");
const smsCode = ref("");
const captcha = ref("");
const captchaId = ref("");
const recoveryOpen = ref(false);
const agreementOpen = ref(false);
const agreementType = ref<"terms" | "privacy">("terms");
function clearErrors() {
  errors.value = {};
  status.value = null;
}
function refreshCaptcha() {
  captcha.value = "";
}
function submit() {
  const next: Record<string, string> = {};
  if (!isPhone(phone.value)) next.phone = "请输入正确的 11 位手机号";
  if (loginMode.value === "password" && !password.value)
    next.password = "请输入登录密码";
  if (loginMode.value === "sms" && !isCode(smsCode.value))
    next.smsCode = "请输入 6 位短信验证码";
  if (!isCaptcha(captcha.value)) next.captcha = "请输入图片验证码";
  if (!agreed.value) next.agreement = "请先同意用户协议和隐私政策";
  errors.value = next;
  if (Object.keys(next).length) return;
  isSubmitting.value = true;
  window.setTimeout(() => {
    isSubmitting.value = false;
    if (remember.value && loginMode.value === "password")
      localStorage.setItem("shinkou-login-phone", phone.value);
    else localStorage.removeItem("shinkou-login-phone");
    status.value = {
      type: "success",
      message: "登录成功，正在为你打开工作台…",
    };
  }, 650);
}
function sendSms() {
  if (!isCaptcha(captcha.value)) {
    errors.value = { captcha: "请输入图片验证码" };
    return;
  }
  status.value = { type: "info", message: "短信验证码已发送，有效期 5 分钟。" };
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
        :variant="status.type === 'error' ? 'destructive' : 'default'"
        ><CheckCircle2Icon
          v-if="status.type === 'success'"
        /><MessageCircleMoreIcon v-else /><AlertTitle>{{
          status.type === "success" ? "操作成功" : "提示"
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
                  @input="clearErrors"
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
                    @click="sendSms"
                    >获取验证码</Button
                  >
                </div>
                <FieldDescription>验证码 5 分钟内有效。</FieldDescription
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
