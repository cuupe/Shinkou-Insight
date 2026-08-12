<script setup lang="ts">
import { ref } from "vue";
import { EyeIcon, EyeOffIcon } from "@lucide/vue";
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
import { useRouter } from "vue-router";
const router = useRouter();
const { isPhone, isCode, isCaptcha } = useAuth();
const phone = ref("");
const smsCode = ref("");
const username = ref("");
const password = ref("");
const confirmPassword = ref("");
const captcha = ref(""); const captchaId = ref("");
const agreed = ref(false);
const isSubmitting = ref(false);
const errors = ref<Record<string, string>>({});
const showPassword = ref(false);
const showConfirm = ref(false);
const agreementOpen = ref(false);
const agreementType = ref<"terms" | "privacy">("terms");
function clearErrors() {
  errors.value = {};
}
function sendSms() {
  if (!isPhone(phone.value)) {
    errors.value = { phone: "请输入正确的 11 位手机号" };
    return;
  }
  if (!isCaptcha(captcha.value)) {
    errors.value = { captcha: "请先输入图片验证码" };
    return;
  }
  errors.value = {};
}
function submit() {
  const next: Record<string, string> = {};
  if (!isPhone(phone.value)) next.phone = "请输入正确的 11 位手机号";
  if (!isCode(smsCode.value)) next.smsCode = "请输入 6 位手机验证码";
  if (username.value.trim().length < 2)
    next.username = "用户名至少需要 2 个字符";
  if (password.value.length < 8) next.password = "密码至少需要 8 位字符";
  if (password.value !== confirmPassword.value)
    next.confirmPassword = "两次输入的密码不一致";
  if (!isCaptcha(captcha.value)) next.captcha = "请输入图片验证码";
  if (!agreed.value) next.agreement = "请先同意用户协议和隐私政策";
  errors.value = next;
  if (Object.keys(next).length) return;
  isSubmitting.value = true;
  window.setTimeout(() => {
    isSubmitting.value = false;
    router.push({ name: "login" });
  }, 650);
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
      ><form class="flex flex-col gap-5" @submit.prevent="submit">
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
              @input="clearErrors"
            /><FieldError v-if="errors.phone">{{
              errors.phone
            }}</FieldError></Field
          ><Field :data-invalid="!!errors.username"
            ><FieldLabel for="register-username">用户名</FieldLabel
            ><Input
              id="register-username"
              v-model="username"
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
                placeholder="至少 8 位字符"
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
      </form></CardContent
    ><CardFooter class="border-t px-6 pb-6 pt-4 sm:px-7"
      ><p class="flex items-center gap-2 text-xs text-muted-foreground">
        注册后即可邀请团队成员协作
      </p></CardFooter
    ></Card
  ><AgreementDialog v-model:open="agreementOpen" :type="agreementType" />
</template>
