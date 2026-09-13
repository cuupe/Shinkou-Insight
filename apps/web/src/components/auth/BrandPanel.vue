<script setup lang="ts">
import {
  ArrowRightIcon,
  CheckCircle2Icon,
  FingerprintIcon,
  MessageCircleMoreIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "@lucide/vue";
</script>

<template>
  <section
    class="relative hidden min-h-0 overflow-hidden bg-foreground px-10 py-10 text-background lg:flex lg:flex-col lg:justify-between xl:px-14"
  >
    <div
      class="auth-grid-pattern pointer-events-none absolute inset-0 opacity-30"
    />
    <div
      class="pointer-events-none absolute -right-28 top-1/3 size-72 rounded-full bg-brand/10 blur-3xl"
    />
    <div
      class="pointer-events-none absolute -bottom-32 -left-24 size-80 rounded-full bg-brand/10 blur-3xl"
    />

    <div class="relative">
      <div class="flex items-center gap-3">
        <div
          class="grid size-10 place-items-center rounded-2xl bg-brand text-brand-foreground shadow-[0_0_2rem_color-mix(in_oklab,var(--brand)_30%,transparent)]"
        >
          <SparklesIcon />
        </div>
        <span class="text-lg font-semibold tracking-[-0.02em]"
          >Shinkou Insight</span
        >
      </div>

      <div class="mt-24 max-w-lg xl:mt-28">
        <div
          class="mb-6 flex items-center gap-2 text-xs font-medium tracking-[0.16em] text-background/55"
        >
          <span class="size-1.5 rounded-full bg-brand shadow-[0_0_0_4px_color-mix(in_oklab,var(--brand)_12%,transparent)]" />
          团队知识工作台
        </div>
        <h1
          class="text-5xl font-semibold leading-[1.08] tracking-[-0.05em] xl:text-6xl"
        >
          让每一个<br /><span class="text-brand">洞察</span> 都有回响。
        </h1>
        <p class="mt-6 max-w-md text-base leading-7 text-background/60">
          汇聚项目资料、团队知识与协作上下文，把复杂问题整理成清晰、可追溯的下一步。
        </p>
      </div>
    </div>

    <div class="relative mt-12">
      <div class="mb-4 flex items-center justify-between gap-4">
        <p class="text-sm font-medium text-background/80">从问题，到行动</p>
        <span
          class="rounded-full border border-background/10 bg-background/[0.06] px-2.5 py-1 text-[0.65rem] text-background/45"
          >清晰的工作流</span
        >
      </div>

      <div class="relative grid gap-2 sm:grid-cols-3 sm:gap-3">
        <div
          class="pointer-events-none absolute left-[16%] right-[16%] top-7 hidden h-px bg-gradient-to-r from-brand/0 via-brand/45 to-brand/0 sm:block"
        />

        <article
          class="relative rounded-2xl border border-background/10 bg-background/[0.06] p-4 backdrop-blur-sm"
        >
          <div
            class="grid size-8 place-items-center rounded-xl bg-brand/15 text-brand"
          >
            <MessageCircleMoreIcon :size="16" />
          </div>
          <p class="mt-4 text-sm font-medium text-background/90">提出问题</p>
          <p class="mt-1 text-xs leading-5 text-background/45">
            从一个待解决的任务开始
          </p>
        </article>

        <article
          class="relative rounded-2xl border border-background/10 bg-background/[0.06] p-4 backdrop-blur-sm"
        >
          <div
            class="grid size-8 place-items-center rounded-xl bg-background/10 text-background/75"
          >
            <FingerprintIcon :size="16" />
          </div>
          <p class="mt-4 text-sm font-medium text-background/90">汇聚上下文</p>
          <p class="mt-1 text-xs leading-5 text-background/45">
            连接资料、知识与团队协作
          </p>
        </article>

        <article
          class="relative rounded-2xl border border-background/10 bg-background/[0.06] p-4 backdrop-blur-sm"
        >
          <div
            class="grid size-8 place-items-center rounded-xl bg-background/10 text-background/75"
          >
            <ArrowRightIcon :size="16" />
          </div>
          <p class="mt-4 text-sm font-medium text-background/90">明确下一步</p>
          <p class="mt-1 text-xs leading-5 text-background/45">
            留下依据，推动事情继续向前
          </p>
        </article>
      </div>

      <div class="mt-4 flex flex-wrap gap-2">
        <span
          class="inline-flex items-center gap-1.5 rounded-full border border-brand/20 bg-brand/[0.08] px-3 py-1.5 text-xs text-brand/90"
        >
          <ShieldCheckIcon :size="13" />
          来源可追溯
        </span>
        <span
          class="inline-flex items-center gap-1.5 rounded-full border border-background/10 bg-background/[0.05] px-3 py-1.5 text-xs text-background/55"
        >
          <CheckCircle2Icon :size="13" />
          团队共同沉淀
        </span>
      </div>
    </div>
  </section>
</template>
