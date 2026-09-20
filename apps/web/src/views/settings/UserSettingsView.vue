<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { Bell, CheckCircle2, KeyRound, LogOut, ShieldCheck } from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";
import { timezoneOptions } from "@/data/options";
import { authApi } from "@/api/auth";
import { ApiError, getApiErrorMessage } from "@/api";
import { useAuth } from "@/composables/useAuth";
import { useSmsCode } from "@/composables/useSmsCode";

const { notify, router } = useWorkspace();
const displayName = ref("");
const email = ref("");
const phone = ref("");
const timezone = ref("Asia/Shanghai");
const passwordOpen = ref(false);
const phoneOpen = ref(false);
const loggingOut = ref(false);
const savedAt = ref("");
const preferences = reactive({ activity: true, weeklyDigest: false });
const passwordForm = reactive({ current: "", next: "", confirm: "", code: "" });
const phoneForm = reactive({ newPhone: "", currentPassword: "", code: "" });
const savingProfile = ref(false);
const savingPreferences = ref(false);
const sendingPasswordCode = ref(false);
const sendingPhoneCode = ref(false);
const { isPhone, isCode } = useAuth();
const {
  codeId: passwordCodeId,
  resendCountdown: passwordCodeCountdown,
  expired: passwordCodeExpired,
  start: startPasswordCode,
  markExpired: markPasswordCodeExpired,
  clear: clearPasswordCode,
  stopTimer: stopPasswordCodeTimer,
} = useSmsCode();
const {
  codeId: phoneCodeId,
  resendCountdown: phoneCodeCountdown,
  expired: phoneCodeExpired,
  start: startPhoneCode,
  markExpired: markPhoneCodeExpired,
  clear: clearPhoneCode,
  stopTimer: stopPhoneCodeTimer,
} = useSmsCode();
onUnmounted(() => {
  stopPasswordCodeTimer();
  stopPhoneCodeTimer();
});

function applyUser(user: Awaited<ReturnType<typeof authApi.me>>) {
  displayName.value = user.userName || displayName.value;
  email.value = user.email || "";
  phone.value = user.phoneNumber || phone.value;
  timezone.value = user.timezone || timezone.value;
  if (user.notificationPreferences) {
    try {
      Object.assign(preferences, JSON.parse(user.notificationPreferences));
    } catch {
      /* keep defaults */
    }
  }
}

onMounted(async () => {
  try {
    applyUser(await authApi.me());
  } catch {
    notify("个人信息加载失败");
  }
});

const passwordStrength = computed(() => {
  if (!passwordForm.next) return "未设置";
  const classes = [
    /[A-Z]/.test(passwordForm.next),
    /[a-z]/.test(passwordForm.next),
    /\d/.test(passwordForm.next),
    /[^A-Za-z0-9]/.test(passwordForm.next),
  ].filter(Boolean).length;
  if (passwordForm.next.length >= 12 && classes >= 3) return "强度良好";
  if (passwordForm.next.length >= 12) return "复杂度不足";
  return "至少需要 12 位";
});

async function saveProfile() {
  if (!displayName.value.trim() || !phone.value.trim()) {
    notify("请填写显示名称和手机号");
    return;
  }
  savingProfile.value = true;
  try {
    applyUser(
      await authApi.updateProfile({
        userName: displayName.value.trim(),
        email: email.value.trim() || undefined,
        timezone: timezone.value,
      }),
    );
  } catch (error) {
    notify(error instanceof Error ? error.message : "个人信息保存失败");
    return;
  } finally {
    savingProfile.value = false;
  }
  savedAt.value = "刚刚保存";
  notify("个人信息已保存");
}

async function savePreferences() {
  savingPreferences.value = true;
  try {
    applyUser(
      await authApi.updatePreferences({
        activity: preferences.activity,
        weeklyDigest: preferences.weeklyDigest,
      }),
    );
  } catch (error) {
    notify(error instanceof Error ? error.message : "通知偏好保存失败");
    return;
  } finally {
    savingPreferences.value = false;
  }
  notify("通知偏好已更新");
}

async function changePassword() {
  if (!passwordForm.current.trim()) {
    notify("请输入当前密码");
    return;
  }
  if (
    passwordForm.next.length < 12 ||
    passwordForm.next !== passwordForm.confirm
  ) {
    notify("请确认新密码至少 12 位且两次输入一致");
    return;
  }
  if (!passwordCodeId.value) {
    notify(
      passwordCodeExpired.value
        ? "验证码已过期，请重新获取"
        : "请先获取当前手机号验证码",
    );
    return;
  }
  if (!isCode(passwordForm.code)) {
    notify("请输入 6 位短信验证码");
    return;
  }
  try {
    await authApi.updatePassword({
      currentPassword: passwordForm.current,
      newPassword: passwordForm.next,
      verifyCodeId: passwordCodeId.value,
      verifyCode: passwordForm.code,
    });
  } catch (error) {
    if (error instanceof ApiError && error.code === "SMS_CODE_INVALID") {
      markPasswordCodeExpired();
      passwordForm.code = "";
    }
    notify(error instanceof Error ? error.message : "密码修改失败");
    return;
  }
  passwordOpen.value = false;
  Object.assign(passwordForm, { current: "", next: "", confirm: "", code: "" });
  clearPasswordCode();
  notify("登录密码已更新");
}

async function sendPasswordCode() {
  if (sendingPasswordCode.value || passwordCodeCountdown.value > 0) return;
  sendingPasswordCode.value = true;
  try {
    const response = await authApi.sms({
      phoneNumber: phone.value,
      purpose: "PASSWORD_CHANGE",
    });
    passwordForm.code = "";
    startPasswordCode(response.smsId);
    notify("验证码已发送到当前手机号");
  } catch (error) {
    notify(getApiErrorMessage(error, "验证码发送失败，请稍后重试"));
  } finally {
    sendingPasswordCode.value = false;
  }
}

async function sendPhoneCode() {
  if (sendingPhoneCode.value || phoneCodeCountdown.value > 0) return;
  if (!isPhone(phoneForm.newPhone)) {
    notify("请输入正确的 11 位新手机号");
    return;
  }
  sendingPhoneCode.value = true;
  try {
    const response = await authApi.sms({
      phoneNumber: phoneForm.newPhone.trim(),
      purpose: "PHONE_CHANGE",
    });
    phoneForm.code = "";
    startPhoneCode(response.smsId);
    notify("验证码已发送到新手机号");
  } catch (error) {
    notify(getApiErrorMessage(error, "验证码发送失败，请稍后重试"));
  } finally {
    sendingPhoneCode.value = false;
  }
}

async function changePhone() {
  if (!isPhone(phoneForm.newPhone)) {
    notify("请输入正确的 11 位新手机号");
    return;
  }
  if (!phoneForm.currentPassword.trim()) {
    notify("请输入当前密码");
    return;
  }
  if (!phoneCodeId.value || !isCode(phoneForm.code)) {
    notify(
      phoneCodeExpired.value
        ? "验证码已过期，请重新获取"
        : "请输入 6 位短信验证码",
    );
    return;
  }
  try {
    applyUser(
      await authApi.updatePhone({
        newPhoneNumber: phoneForm.newPhone.trim(),
        currentPassword: phoneForm.currentPassword,
        verifyCodeId: phoneCodeId.value,
        verifyCode: phoneForm.code,
      }),
    );
  } catch (error) {
    if (error instanceof ApiError && error.code === "SMS_CODE_INVALID") {
      markPhoneCodeExpired();
      phoneForm.code = "";
    }
    notify(getApiErrorMessage(error, "手机号修改失败，请稍后重试"));
    return;
  }
  phoneOpen.value = false;
  Object.assign(phoneForm, { newPhone: "", currentPassword: "", code: "" });
  clearPhoneCode();
  notify("手机号已更新，请使用新手机号登录");
}

async function handleLogout() {
  if (loggingOut.value) return;
  loggingOut.value = true;
  try {
    await authApi.logout();
  } catch {
    // If the API rejects the session, return to the authenticated entry point.
  } finally {
    loggingOut.value = false;
    notify("已退出登录");
    router.push({ name: "login" });
  }
}
</script>

<template>
  <Layout
    eyebrow="ACCOUNT / SETTINGS"
    title="个人信息设置"
    subtitle="管理你的个人资料、联系方式和账号安全"
  >
    <div class="settings-section profile-section">
      <div class="section-intro">
        <div>
          <h2>个人资料</h2>
          <p>这些信息会显示在工作区成员列表和调研记录中。</p>
        </div>
        <span class="save-state" v-if="savedAt"
          ><CheckCircle2 :size="14" />{{ savedAt }}</span
        >
      </div>
      <div class="profile-heading">
        <div>
          <strong>{{ displayName || "未命名成员" }}</strong
          ><span>{{ phone }}</span>
        </div>
      </div>
      <div class="form-grid">
        <label class="field-label"
          >显示名称<input v-model="displayName" maxlength="30"
        /></label>
        <label class="field-label"
          >时区<select v-model="timezone">
            <option
              v-for="option in timezoneOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select></label
        >
        <label class="field-label"
          >手机号（登录账号）<input :value="phone" disabled autocomplete="tel"
        /></label>
        <label class="field-label"
          >邮箱（可选）<input v-model="email" type="email" autocomplete="email"
        /></label>
      </div>
      <div class="profile-actions">
        <button
          class="button button-primary"
          type="button"
          @click="saveProfile"
        >
          保存个人信息
        </button>
        <button
          class="button button-secondary"
          type="button"
          @click="phoneOpen = true"
        >
          修改手机号
        </button>
      </div>
    </div>

    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>通知偏好</h2>
          <p>选择哪些工作区动态需要通过应用提醒你。</p>
        </div>
        <Bell :size="18" class="section-icon" />
      </div>
      <div class="preference-list">
        <label class="preference-row"
          ><span
            ><strong>调研运行和任务状态</strong
            ><small>运行完成、失败或需要你确认时提醒</small></span
          ><input
            v-model="preferences.activity"
            type="checkbox"
            class="switch-input" /><span class="switch-ui"
        /></label>
        <label class="preference-row"
          ><span
            ><strong>每周工作摘要</strong
            ><small>每周一发送工作区活动和待办摘要</small></span
          ><input
            v-model="preferences.weeklyDigest"
            type="checkbox"
            class="switch-input" /><span class="switch-ui"
        /></label>
      </div>
      <button
        class="button button-secondary button-sm"
        type="button"
        @click="savePreferences"
      >
        保存通知偏好
      </button>
    </div>

    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>账号安全</h2>
          <p>定期更新密码可以降低账号被盗用的风险。</p>
        </div>
        <ShieldCheck :size="18" class="section-icon" />
      </div>
      <div class="security-setting-row">
        <div class="security-icon"><KeyRound :size="16" /></div>
        <div>
          <strong>登录密码</strong
          ><small>修改密码需要当前密码和当前手机号短信验证码</small>
        </div>
        <button
          class="button button-secondary button-sm"
          type="button"
          @click="passwordOpen = true"
        >
          修改密码
        </button>
      </div>
      <div class="security-setting-row logout-row">
        <div class="security-icon logout-icon"><LogOut :size="16" /></div>
        <div>
          <strong>退出当前账号</strong
          ><small>退出后需要重新使用手机号和密码或短信验证码登录。</small>
        </div>
        <button
          class="button button-danger button-sm"
          type="button"
          :disabled="loggingOut"
          @click="handleLogout"
        >
          {{ loggingOut ? "正在退出…" : "退出登录" }}
        </button>
      </div>
    </div>

    <Dialog v-model:open="passwordOpen"
      ><DialogContent class="password-dialog sm:max-w-md"
        ><DialogHeader
          ><DialogTitle>修改登录密码</DialogTitle
          ><DialogDescription
            >新密码只会保存在当前会话中，不会上传到外部服务。</DialogDescription
          ></DialogHeader
        >
        <div class="password-form">
          <label class="field-label"
            >当前密码<input
              v-model="passwordForm.current"
              type="password"
              autocomplete="current-password" /></label
          ><label class="field-label"
            >新密码<input
              v-model="passwordForm.next"
              type="password"
              autocomplete="new-password"
            /><small class="password-hint"
              >{{ passwordStrength }} · 至少 12 位</small
            ></label
          ><label class="field-label"
            >确认新密码<input
              v-model="passwordForm.confirm"
              type="password"
              autocomplete="new-password"
          /></label>
          <label class="field-label"
            >短信验证码
            <div class="verification-row">
              <input
                v-model="passwordForm.code"
                inputmode="numeric"
                maxlength="6"
                autocomplete="one-time-code"
                placeholder="请输入 6 位验证码"
              />
              <button
                class="button button-secondary button-sm"
                type="button"
                :disabled="sendingPasswordCode || passwordCodeCountdown > 0"
                @click="sendPasswordCode"
              >
                {{
                  sendingPasswordCode
                    ? "发送中…"
                    : passwordCodeCountdown > 0
                      ? `${passwordCodeCountdown}s 后重发`
                      : "获取验证码"
                }}
              </button>
            </div>
            <small class="password-hint"
              >验证码将发送到当前手机号，有效期 5 分钟</small
            >
          </label>
        </div>
        <DialogFooter
          ><button
            class="button button-secondary"
            type="button"
            @click="passwordOpen = false"
          >
            取消</button
          ><button
            class="button button-primary"
            type="button"
            @click="changePassword"
          >
            更新密码
          </button></DialogFooter
        ></DialogContent
      ></Dialog
    >

    <Dialog v-model:open="phoneOpen">
      <DialogContent class="password-dialog sm:max-w-md">
        <DialogHeader>
          <DialogTitle>修改手机号</DialogTitle>
          <DialogDescription>
            修改后需要使用新手机号登录。请验证当前密码，并完成新手机号短信验证。
          </DialogDescription>
        </DialogHeader>
        <div class="password-form">
          <label class="field-label"
            >新手机号<input
              v-model="phoneForm.newPhone"
              type="tel"
              inputmode="tel"
              autocomplete="tel"
              placeholder="请输入 11 位手机号"
          /></label>
          <label class="field-label"
            >当前密码<input
              v-model="phoneForm.currentPassword"
              type="password"
              autocomplete="current-password"
          /></label>
          <label class="field-label"
            >新手机号验证码
            <div class="verification-row">
              <input
                v-model="phoneForm.code"
                inputmode="numeric"
                maxlength="6"
                autocomplete="one-time-code"
                placeholder="请输入 6 位验证码"
              />
              <button
                class="button button-secondary button-sm"
                type="button"
                :disabled="sendingPhoneCode || phoneCodeCountdown > 0"
                @click="sendPhoneCode"
              >
                {{
                  sendingPhoneCode
                    ? "发送中…"
                    : phoneCodeCountdown > 0
                      ? `${phoneCodeCountdown}s 后重发`
                      : "获取验证码"
                }}
              </button>
            </div>
            <small class="password-hint"
              >验证码将发送到新手机号，有效期 5 分钟</small
            >
          </label>
        </div>
        <DialogFooter>
          <button
            class="button button-secondary"
            type="button"
            @click="phoneOpen = false"
          >
            取消
          </button>
          <button
            class="button button-primary"
            type="button"
            @click="changePhone"
          >
            确认修改
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </Layout>
</template>

<style scoped>
.section-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.section-icon {
  color: var(--teal-dark);
}
.save-state {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
}
.profile-heading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0 0 1.125rem;
}
.profile-avatar {
  display: grid;
  place-items: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 50%;
  background: #f7e1cf;
  color: #a7642e;
  font-size: 1.0625rem;
  font-weight: 700;
}
.profile-heading strong,
.profile-heading span {
  display: block;
}
.profile-heading strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.profile-heading span {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.preference-list {
  display: grid;
  max-width: 48.75rem;
  margin-bottom: 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  overflow: hidden;
}
.preference-row {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  cursor: pointer;
}
.preference-row:last-child {
  border-bottom: 0;
}
.preference-row strong,
.preference-row small {
  display: block;
}
.preference-row strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.preference-row small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.switch-input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.switch-ui {
  width: 2.125rem;
  height: 1.1875rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #d8e2e2;
  transition: background 0.16s;
}
.switch-ui::after {
  display: block;
  width: 0.875rem;
  height: 0.875rem;
  margin: 0.15625rem;
  border-radius: 50%;
  background: white;
  content: "";
  box-shadow: 0 0.0625rem 0.125rem rgba(0, 0, 0, 0.12);
  transition: transform 0.16s;
}
.switch-input:checked + .switch-ui {
  background: var(--teal);
}
.switch-input:checked + .switch-ui::after {
  transform: translateX(0.9375rem);
}
.security-setting-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  max-width: 48.75rem;
  padding: 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
}
.security-setting-row > div:nth-child(2) {
  flex: 1;
}
.security-icon {
  display: grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.5rem;
  background: #edf7f5;
  color: var(--teal-dark);
}
.security-setting-row strong,
.security-setting-row small {
  display: block;
}
.security-setting-row strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}
.security-setting-row small {
  margin-top: 0.3125rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.password-dialog {
  max-width: 34rem !important;
}
.password-form {
  display: grid;
  gap: 0.875rem;
}
.profile-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}
.verification-row {
  display: flex;
  gap: 0.5rem;
}
.verification-row input {
  min-width: 0;
  flex: 1;
}
.verification-row .button {
  flex: 0 0 auto;
  white-space: nowrap;
}
.password-hint {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}
.logout-row {
  margin-top: 0.625rem;
}
.logout-icon {
  color: #b85757;
  background: #fff1f1;
}
.logout-row .button-danger:disabled {
  cursor: wait;
  opacity: 0.6;
}
@media (max-width: 47.5rem) {
  .security-setting-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .security-setting-row .button {
    margin-left: 2.75rem;
  }
  .profile-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .profile-actions .button {
    width: 100%;
  }
  .section-intro {
    gap: 0.5rem;
  }
}
</style>
