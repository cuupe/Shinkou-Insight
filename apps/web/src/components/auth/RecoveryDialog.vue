<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { EyeIcon, EyeOffIcon } from "@lucide/vue";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import ImageCaptcha from "@/components/auth/ImageCaptcha.vue";
import { useAuth } from "@/composables/useAuth";
type Status = { type: "success" | "error" | "info"; message: string };
const props = defineProps<{ open: boolean; phone: string }>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();
const { isPhone, isCode, isCaptcha } = useAuth();
const step = ref<"account" | "verify" | "reset">("account");
const account = ref("");
const code = ref("");
const captcha = ref(""); const captchaId = ref("");
const captchaError = ref("");
const password = ref("");
const confirmPassword = ref("");
const status = ref<Status | null>(null);
const showPassword = ref(false);
const title = computed(() =>
  step.value === "verify"
    ? "输入验证码"
    : step.value === "reset"
      ? "设置新密码"
      : "找回你的密码",
);
watch(
  () => props.open,
  (open) => {
    if (open) {
      step.value = "account";
      account.value = props.phone;
      code.value = "";
      captcha.value = "";
      captchaError.value = "";
      password.value = "";
      confirmPassword.value = "";
      status.value = null;
    }
  },
);
function sendCode() {
  if (!isPhone(account.value)) {
    status.value = { type: "error", message: "请输入正确的 11 位手机号。" };
    return;
  }
  if (!isCaptcha(captcha.value)) {
    captchaError.value = "请输入图片验证码";
    status.value = { type: "error", message: captchaError.value };
    return;
  }
  step.value = "verify";
  status.value = { type: "info", message: "验证码已发送，有效期 5 分钟。" };
}
function verify() {
  if (!isCode(code.value)) {
    status.value = { type: "error", message: "请输入 6 位验证码。" };
    return;
  }
  step.value = "reset";
  status.value = null;
}
function reset() {
  if (password.value.length < 8) {
    status.value = { type: "error", message: "新密码至少需要 8 位字符。" };
    return;
  }
  if (password.value !== confirmPassword.value) {
    status.value = { type: "error", message: "两次输入的新密码不一致。" };
    return;
  }
  status.value = { type: "success", message: "密码已重置，请返回登录。" };
  window.setTimeout(() => emit("update:open", false), 900);
}
</script>

<template>
  <Dialog :open="props.open" @update:open="emit('update:open', $event)"
    ><DialogContent class="sm:max-w-md"
      ><DialogHeader
        ><DialogTitle>{{ title }}</DialogTitle
        ><DialogDescription v-if="step === 'account'"
          >输入绑定的手机号，我们会发送验证码帮助你重置密码。</DialogDescription
        ><DialogDescription v-else-if="step === 'verify'"
          >验证码已发送至 {{ account }}，请在下方输入。</DialogDescription
        ><DialogDescription v-else
          >设置一个新的登录密码，完成后即可重新登录。</DialogDescription
        ></DialogHeader
      ><Alert
        v-if="status"
        :variant="status.type === 'error' ? 'destructive' : 'default'"
        ><AlertDescription>{{ status.message }}</AlertDescription></Alert
      ><FieldGroup v-if="step === 'account'"
        ><Field
          ><FieldLabel for="recovery-account">手机号</FieldLabel
          ><Input
            id="recovery-account"
            v-model="account"
            type="tel"
            placeholder="请输入 11 位手机号" /></Field
        ><ImageCaptcha
          id="recovery-captcha"
          v-model="captcha"
          v-model:captcha-id="captchaId"
          :error="captchaError"
          @refresh="
            captcha = '';
            captchaError = '';
          " /></FieldGroup
      ><FieldGroup v-else-if="step === 'verify'"
        ><Field
          ><FieldLabel for="recovery-code">6 位验证码</FieldLabel
          ><InputOTP
            id="recovery-code"
            v-model="code"
            :maxlength="6"
            class="justify-center"
            ><InputOTPGroup
              ><InputOTPSlot
                v-for="index in 6"
                :key="index"
                :index="index - 1" /></InputOTPGroup></InputOTP
          ><FieldDescription>验证码 5 分钟内有效。</FieldDescription></Field
        ></FieldGroup
      ><FieldGroup v-else
        ><Field
          ><FieldLabel for="recovery-new-password">新密码</FieldLabel>
          <div class="relative">
            <Input
              id="recovery-new-password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="至少 8 位字符"
              class="pr-10"
            /><Button
              type="button"
              variant="ghost"
              size="icon-sm"
              class="absolute right-1 top-1/2 -translate-y-1/2"
              @click="showPassword = !showPassword"
              ><EyeOffIcon v-if="showPassword" /><EyeIcon v-else
            /></Button>
          </div>
          <FieldError /></Field
        ><Field
          ><FieldLabel for="recovery-confirm-password">确认新密码</FieldLabel
          ><Input
            id="recovery-confirm-password"
            v-model="confirmPassword"
            type="password"
            placeholder="再次输入新密码" /></Field></FieldGroup
      ><DialogFooter
        ><Button
          type="button"
          variant="ghost"
          @click="emit('update:open', false)"
          >取消</Button
        ><Button
          v-if="step === 'account'"
          type="button"
          class="bg-brand text-brand-foreground hover:bg-brand/90"
          @click="sendCode"
          >发送验证码</Button
        ><Button
          v-else-if="step === 'verify'"
          type="button"
          class="bg-brand text-brand-foreground hover:bg-brand/90"
          @click="verify"
          >验证并继续</Button
        ><Button
          v-else
          type="button"
          class="bg-brand text-brand-foreground hover:bg-brand/90"
          @click="reset"
          >完成重置</Button
        ></DialogFooter
      ></DialogContent
    ></Dialog
  >
</template>
