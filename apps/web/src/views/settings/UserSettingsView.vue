<script setup lang="ts">
import { ref } from "vue";
import Layout from "@/components/settings/Layout.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { timezoneOptions, userProfile } from "@/data/mock";

const { notify } = useWorkspace();
const displayName = ref(userProfile.name);
const email = ref(userProfile.email);
const phone = ref(userProfile.phone);
const timezone = ref(userProfile.timezone);

function saveProfile() {
  notify("个人信息已保存");
}

function changePassword() {
  notify("请通过登录页的密码找回流程修改密码");
}
</script>

<template>
  <Layout
    eyebrow="ACCOUNT / SETTINGS"
    title="个人信息设置"
    subtitle="管理你的个人资料、联系方式和账号安全"
  >
    <div class="settings-section profile-section">
      <div class="profile-heading">
        <span class="profile-avatar">{{ displayName.slice(0, 1) }}</span>
        <div>
          <h2>个人资料</h2>
          <p>这些信息会显示在工作区成员列表和调研记录中。</p>
        </div>
      </div>
      <div class="form-grid">
        <label class="field-label">
          显示名称
          <input v-model="displayName" maxlength="30" />
        </label>
        <label class="field-label">
          时区
          <select v-model="timezone">
            <option v-for="option in timezoneOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="field-label">
          邮箱
          <input v-model="email" type="email" />
        </label>
        <label class="field-label">
          手机号
          <input v-model="phone" autocomplete="tel" />
        </label>
      </div>
      <button class="button button-primary" type="button" @click="saveProfile">
        保存个人信息
      </button>
    </div>
    <div class="settings-section">
      <div>
        <h2>账号安全</h2>
        <p>定期更新密码可以降低账号被盗用的风险。</p>
      </div>
      <div class="security-setting-row">
        <div>
          <strong>登录密码</strong>
          <small>建议使用包含大小写字母、数字和符号的密码</small>
        </div>
        <button class="button button-secondary button-sm" type="button" @click="changePassword">
          修改密码
        </button>
      </div>
    </div>
  </Layout>
</template>
