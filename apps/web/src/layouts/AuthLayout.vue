<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { Badge } from "@/components/ui/badge";
import { SparklesIcon } from "@lucide/vue";
import BrandPanel from "@/components/auth/BrandPanel.vue";
import ThemeToggle from "@/components/common/ThemeToggle.vue";
const route = useRoute();
const isRegister = computed(() => route.name === "register");
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
