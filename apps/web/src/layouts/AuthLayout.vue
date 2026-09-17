<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CircleAlertIcon, SparklesIcon } from "@lucide/vue";
import BrandPanel from "@/components/auth/BrandPanel.vue";
import ThemeToggle from "@/components/common/ThemeToggle.vue";
const route = useRoute();
const isRegister = computed(() => route.name === "register");
const authNotice = computed(() => {
  const reason = Array.isArray(route.query.reason)
    ? route.query.reason[0]
    : route.query.reason;

  if (reason === "unauthorized") {
    return {
      title: "登录状态已失效",
      message: "为了保护账号安全，当前会话已退出，请重新登录后继续使用。",
    };
  }

  if (reason === "backend-unavailable") {
    return {
      title: "后端服务暂时不可用",
      message: "当前会话已中断，可能是后端重启或网络异常。请确认服务已启动，稍后重新登录。",
    };
  }

  return null;
});
</script>

<template>
  <main class="auth-page auth-layout">
    <div class="auth-orb auth-orb-one" />
    <div class="auth-orb auth-orb-two" />

    <div class="auth-layout-shell">
      <BrandPanel />

      <section class="auth-panel">
        <div class="auth-desktop-theme-toggle">
          <ThemeToggle />
        </div>
        <div class="auth-panel-inner">
          <div class="mb-8 flex items-center justify-between lg:hidden">
            <div class="flex items-center gap-3">
              <div
                class="grid size-10 place-items-center rounded-2xl bg-brand text-brand-foreground"
              >
                <SparklesIcon />
              </div>
              <span class="font-semibold">Shinkou Insight</span>
            </div>
            <div class="auth-header-actions">
              <ThemeToggle />
              <Badge variant="secondary">安全登录</Badge>
            </div>
          </div>

          <div class="auth-intro mb-8">
            <p class="mb-3 text-sm font-medium text-brand">
              {{ isRegister ? "欢迎加入" : "欢迎回来" }}
            </p>
            <h2
              class="auth-title text-3xl font-semibold tracking-[-0.04em] sm:text-4xl"
            >
              {{ isRegister ? "创建你的账号" : "进入你的工作台" }}
            </h2>
            <p class="mt-3 text-sm leading-6 text-muted-foreground">
              {{
                isRegister
                  ? "加入团队，开始沉淀有价值的洞察。"
                  : "登录后继续查看团队的最新洞察与知识沉淀。"
              }}
            </p>
          </div>

          <nav
            class="auth-tabs mb-7 grid h-11 w-full grid-cols-2 rounded-lg bg-muted/70 p-1"
          >
            <RouterLink
              class="grid place-items-center rounded-md text-sm text-muted-foreground"
              :class="{
                'bg-background text-foreground shadow-sm': !isRegister,
              }"
              :to="{ name: 'login' }"
            >
              登录
            </RouterLink>
            <RouterLink
              class="grid place-items-center rounded-md text-sm text-muted-foreground"
              :class="{ 'bg-background text-foreground shadow-sm': isRegister }"
              :to="{ name: 'register' }"
            >
              注册账号
            </RouterLink>
          </nav>

          <Alert
            v-if="authNotice"
            class="mb-5"
            variant="destructive"
            role="alert"
            aria-live="polite"
          >
            <CircleAlertIcon />
            <AlertTitle>{{ authNotice.title }}</AlertTitle>
            <AlertDescription>{{ authNotice.message }}</AlertDescription>
          </Alert>

          <div class="auth-route">
            <RouterView />
          </div>

          <p class="auth-footer mt-8 text-center text-xs text-muted-foreground">
            © 2026 Shinkou Insight · 为团队打造的智能知识空间
          </p>
        </div>
      </section>
    </div>
  </main>
</template>
<style>
@layer components {
  .auth-page {
    isolation: isolate;
    box-sizing: border-box;
    min-height: 100vh;
    max-height: none;
    background:
      radial-gradient(
        circle at 12% 12%,
        color-mix(in oklab, var(--brand) 13%, transparent),
        transparent 28rem
      ),
      radial-gradient(
        circle at 85% 82%,
        color-mix(in oklab, var(--brand) 10%, transparent),
        transparent 25rem
      ),
      var(--background);
  }

  .auth-grid-pattern {
    background-image:
      linear-gradient(
        color-mix(in oklab, var(--background) 8%, transparent) 1px,
        transparent 1px
      ),
      linear-gradient(
        90deg,
        color-mix(in oklab, var(--background) 8%, transparent) 1px,
        transparent 1px
      );
    background-size: 2.625rem 2.625rem;
    mask-image: linear-gradient(to bottom, black, transparent 88%);
  }

  .auth-orb {
    position: fixed;
    pointer-events: none;
    z-index: -1;
    border-radius: 9999px;
    filter: blur(1px);
  }

  .auth-orb-one {
    top: 8%;
    left: 3%;
    width: 12rem;
    height: 12rem;
    background: color-mix(in oklab, var(--brand) 8%, transparent);
  }

  .auth-orb-two {
    right: 4%;
    bottom: 3%;
    width: 18rem;
    height: 18rem;
    background: color-mix(in oklab, var(--brand) 7%, transparent);
  }

  /* Mobile owns the page scroll. Wide screens switch to a bounded workspace
     so the authentication surface never creates a second scrollbar. */
  .auth-layout {
    display: block;
    overflow-x: clip;
    overflow-y: auto;
    padding: clamp(0.75rem, 2vw, 1.5rem);
  }

  .auth-layout-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.02fr) minmax(30rem, 0.98fr);
    width: min(100%, 80rem);
    min-height: calc(100vh - 3rem);
    margin: 0 auto;
    overflow: hidden;
    border: 1px solid color-mix(in oklab, var(--border) 70%, transparent);
    border-radius: 2rem;
    background: color-mix(in oklab, var(--background) 80%, transparent);
    box-shadow: 0 1.5rem 4rem color-mix(in oklab, var(--brand) 10%, transparent);
    backdrop-filter: blur(1.25rem);
  }

  .auth-panel {
    display: flex;
    min-width: 0;
    align-items: stretch;
    justify-content: center;
    background: color-mix(in oklab, var(--background) 88%, transparent);
  }

  .auth-panel-inner {
    width: min(100%, 28rem);
    min-width: 0;
    margin: auto;
    padding: clamp(1rem, 4vh, 3rem) 0;
  }

  .auth-route {
    min-width: 0;
  }

  .auth-footer {
    line-height: 1.4;
  }

  .captcha-tile {
    background: repeating-linear-gradient(
      125deg,
      color-mix(in oklab, var(--brand) 8%, var(--background)) 0 3px,
      color-mix(in oklab, var(--brand) 16%, var(--background)) 3px 6px
    );
    font-family:
      ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-weight: 700;
  }

  .image-captcha-field {
    gap: 0.45rem;
  }

  .image-captcha-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .image-captcha-hint {
    color: var(--muted-foreground);
    font-size: 0.8125rem;
  }

  .image-captcha-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 7rem;
    align-items: stretch;
    gap: 0.6rem;
  }

  .image-captcha-box {
    min-width: 0;
    height: 2.25rem;
    padding: 0.25rem;
    overflow: hidden;
    border-style: dashed;
    background: repeating-linear-gradient(
      135deg,
      color-mix(in oklab, var(--brand) 4%, var(--background)) 0 5px,
      color-mix(in oklab, var(--brand) 9%, var(--background)) 5px 10px
    );
  }

  .image-captcha-box img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 0.3rem;
  }

  .captcha-placeholder {
    color: var(--muted-foreground);
    font-size: 0.8125rem;
  }

  .image-captcha-box small {
    display: block;
    color: color-mix(in oklab, var(--muted-foreground) 75%, transparent);
    font-size: 0.75rem;
    margin-top: 0.1rem;
  }

  .auth-page [data-slot="card"],
  .auth-page [data-slot="tabs"],
  .auth-page form,
  .auth-page [data-slot="field-group"] {
    min-width: 0;
  }

  .auth-page [data-slot="field-error"] {
    min-width: 0;
    max-width: 100%;
    overflow-wrap: anywhere;
    word-break: break-word;
    line-height: 1.35;
  }

  .auth-page .grid-cols-\[1fr_auto\] {
    grid-template-columns: minmax(0, 1fr) auto;
    min-width: 0;
  }

}

@media (max-width: 40rem) {
  .auth-page {
    padding: 0.5rem;
  }

  .auth-layout-shell {
    grid-template-columns: minmax(0, 1fr);
    min-height: calc(100vh - 1rem);
    border-radius: 1rem;
  }

  .auth-panel-inner {
    width: min(100%, 32rem);
    padding: 0.5rem 0;
  }

  .auth-page .mb-8 {
    margin-bottom: 0.5rem;
  }

  .auth-page .mb-7 {
    margin-bottom: 0.5rem;
  }

  .auth-page .mb-6 {
    margin-bottom: 0.75rem;
  }

  .auth-page form {
    gap: 0.5rem;
  }

  .auth-page [data-slot="field-group"] {
    gap: 0.5rem;
  }

  .auth-page [data-slot="field"] {
    gap: 0.25rem;
  }

  .auth-page [data-slot="card-header"] {
    padding-top: 0.75rem;
    padding-bottom: 0.5rem;
  }

  .auth-page [data-slot="card-content"] {
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
  }

  .auth-page [data-slot="input"] {
    height: 2rem;
  }

  .auth-page [data-slot="card-footer"] {
    display: none;
  }

  .auth-footer {
    margin-top: 0.25rem;
  }

  .auth-page .grid-cols-\[1fr_auto\] > * {
    min-width: 0;
  }

  .auth-page .grid-cols-\[1fr_auto\] .captcha-tile {
    width: 6rem;
    min-width: 6rem;
    padding-inline: 0.5rem;
  }

  .auth-page .login-code-row {
    flex-direction: column;
  }

  .auth-page .login-code-row > [data-slot="input-otp"],
  .auth-page .login-code-row > button {
    width: 100%;
  }

  .auth-page [data-slot="input-otp-group"] {
    justify-content: space-between;
    gap: 0.25rem;
  }

  .auth-title {
    font-size: 1.75rem !important;
    line-height: 1.2 !important;
  }

  .auth-intro {
    margin-bottom: 1rem !important;
  }

  .auth-intro > p:last-child {
    margin-top: 0.5rem;
    line-height: 1.5;
  }

  .agreement-field {
    display: grid !important;
    grid-template-columns: 1rem minmax(0, 1fr);
    align-items: start !important;
    column-gap: 0.5rem;
    row-gap: 0.25rem;
  }

  .agreement-field [data-slot="checkbox"] {
    width: 1rem !important;
    height: 1rem !important;
    margin-top: 0.15rem;
  }

  .agreement-field [data-slot="field-content"] {
    width: auto !important;
    min-width: 0;
  }

  .agreement-field .agreement-label {
    display: block !important;
    width: auto !important;
    min-width: 0;
    line-height: 1.5;
  }

  .agreement-field .agreement-label [data-slot="button"] {
    display: inline-flex;
    width: auto !important;
    vertical-align: baseline;
  }
}

@media (max-width: 63.9375rem) {
  .auth-page {
    min-height: 100dvh;
  }

  .auth-layout {
    height: auto;
    min-height: 100dvh;
    max-height: none;
    overflow: visible;
    padding: 0.75rem;
  }

  .auth-layout-shell {
    grid-template-columns: minmax(0, 1fr);
    height: auto;
    min-height: 0;
    max-height: none;
    overflow: visible;
    border-radius: 1.5rem;
  }

  .auth-panel {
    display: block;
  }

  .auth-panel-inner {
    width: min(100%, 32rem);
    margin: 0 auto;
    padding: 1rem 1.25rem 1.25rem;
  }
}

@media (max-width: 40rem) {
  .auth-layout {
    padding: 0.5rem;
  }

  .auth-layout-shell {
    border-radius: 1rem;
  }

  .auth-panel-inner {
    padding: 0.75rem 1rem 1rem;
  }
}

@media (max-height: 56.25rem) and (min-width: 64rem) {
  .auth-panel-inner {
    padding-top: 1rem;
    padding-bottom: 1rem;
  }
}

@media (min-width: 64rem) {
  .auth-layout {
    height: auto;
    min-height: 100vh;
    max-height: none;
    overflow-y: auto;
  }

  .auth-layout-shell {
    height: auto;
    min-height: calc(100vh - 3rem);
    max-height: none;
    overflow: visible;
  }

  .auth-panel-inner {
    padding: 1rem 0;
  }

  .auth-panel-inner > .auth-intro {
    margin-bottom: 1rem;
  }

  .auth-panel-inner > .auth-tabs {
    margin-bottom: 1rem;
  }

  .auth-panel-inner > .auth-footer {
    margin-top: 1rem;
  }

  .auth-route [data-slot="card-header"] {
    padding-top: 1rem !important;
    padding-bottom: 0.75rem !important;
  }

  .auth-route [data-slot="card-content"] {
    padding-bottom: 1rem !important;
  }

  .auth-route [data-slot="card-footer"] {
    display: none;
  }

  .auth-route form {
    gap: 0.75rem;
  }

  .auth-route [data-slot="field-group"] {
    gap: 0.75rem;
  }

  .auth-route [data-slot="field"] {
    gap: 0.375rem;
  }

  .auth-route [data-slot="tabs-list"] {
    margin-bottom: 1rem !important;
  }
}

@media (min-width: 64rem) and (max-height: 50rem) {
  .auth-layout-shell {
    border-radius: 1.5rem;
  }

  .auth-panel-inner {
    padding: 0.5rem 0;
  }

  .auth-panel-inner > .auth-intro {
    margin-bottom: 0.5rem;
  }

  .auth-panel-inner > .auth-intro h2 {
    font-size: 2rem;
  }

  .auth-panel-inner > .auth-intro p {
    margin-top: 0.5rem;
    line-height: 1.4;
  }

  .auth-panel-inner > .auth-tabs {
    height: 2.5rem;
    margin-bottom: 0.5rem;
  }

  .auth-panel-inner > .auth-footer {
    margin-top: 0.5rem;
  }

  .auth-route [data-slot="card-header"] {
    padding-top: 0.75rem !important;
    padding-bottom: 0.5rem !important;
  }

  .auth-route [data-slot="card-content"] {
    padding-bottom: 0.75rem !important;
  }

  .auth-route [data-slot="input"] {
    height: 2.25rem;
  }

  .auth-route form,
  .auth-route [data-slot="field-group"] {
    gap: 0.5rem;
  }

  .auth-route [data-slot="field"] {
    gap: 0.25rem;
  }
}

.auth-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.auth-panel {
  position: relative;
}

.auth-desktop-theme-toggle {
  position: absolute;
  top: 1.5rem;
  right: 1.5rem;
  z-index: 2;
}

/* The mobile header already contains the control. */
@media (max-width: 63.9375rem) {
  .auth-desktop-theme-toggle {
    display: none;
  }
}

/* Auth dark theme ------------------------------------------------------- */
.dark .auth-page .auth-layout-shell {
  border-color: color-mix(in oklab, var(--border) 85%, transparent);
  background: color-mix(in oklab, var(--background) 88%, transparent);
  box-shadow: 0 1.5rem 4rem rgba(0, 0, 0, 0.3);
}

.dark .auth-page .auth-panel {
  background: color-mix(in oklab, var(--background) 94%, transparent);
}

.dark .auth-page .auth-layout-shell > section:first-child {
  background: #0d181d;
  color: #e7f2f1 !important;
}

.dark .auth-page .auth-layout-shell > section:first-child .text-background,
.dark .auth-page .auth-layout-shell > section:first-child [class*="text-background/"] {
  color: #e7f2f1 !important;
}

.dark .auth-page .auth-layout-shell > section:first-child [class*="text-background/60"] {
  color: rgb(231 242 241 / 0.72) !important;
}

.dark .auth-page .auth-layout-shell > section:first-child [class*="text-background/50"] {
  color: rgb(231 242 241 / 0.64) !important;
}

.dark .auth-page .auth-layout-shell > section:first-child [class*="text-background/45"] {
  color: rgb(231 242 241 / 0.56) !important;
}

.dark .auth-page .auth-layout-shell > section:first-child [class*="text-background/80"] {
  color: rgb(231 242 241 / 0.9) !important;
}

.dark .auth-page [data-slot="input"],
.dark .auth-page [data-slot="input-otp-slot"] {
  color: var(--foreground);
}

.dark .auth-page [data-slot="input"]::placeholder {
  color: var(--muted-foreground);
}

.dark .auth-page .auth-grid-pattern {
  opacity: 0.2;
}
</style>
