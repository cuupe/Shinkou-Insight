<script setup lang="ts">
import { FingerprintIcon, Globe2Icon, SparklesIcon } from "@lucide/vue";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
</script>

<template>
  <section
    class="relative hidden min-h-0 overflow-hidden bg-foreground px-10 py-10 text-background lg:flex lg:flex-col lg:justify-between xl:px-14"
  >
    <div
      class="auth-grid-pattern pointer-events-none absolute inset-0 opacity-30"
    />
    <div class="relative">
      <div class="flex items-center gap-3">
        <div
          class="grid size-10 place-items-center rounded-2xl bg-brand text-brand-foreground"
        >
          <SparklesIcon />
        </div>
        <span class="text-lg font-semibold">Shinkou Insight</span>
      </div>
      <div class="mt-24 max-w-lg">
        <Badge
          variant="outline"
          class="border-background/20 bg-background/10 text-background/80"
          >智能洞察工作台</Badge
        >
        <h1
          class="mt-6 text-5xl font-semibold leading-[1.08] tracking-[-0.05em] xl:text-6xl"
        >
          让每一个<br /><span class="text-brand">洞察</span> 都有回响。
        </h1>
        <p class="mt-6 max-w-md text-base leading-7 text-background/60">
          汇聚你的数据、知识和团队协作，在一个清晰的空间里，把复杂问题变成可执行的下一步。
        </p>
      </div>
    </div>
    <div class="relative grid gap-4 sm:grid-cols-2">
      <Card
        class="border-background/10 bg-background/[0.07] text-background shadow-none"
        ><CardContent class="p-5"
          ><FingerprintIcon class="text-brand" />
          <p class="mt-7 text-3xl font-semibold">
            84.6<span class="ml-1 text-sm font-normal text-background/45"
              >分</span
            >
          </p>
          <p class="mt-1 text-sm text-background/50">
            本周洞察质量
          </p></CardContent
        ></Card
      ><Card
        class="border-background/10 bg-background/[0.07] text-background shadow-none"
        ><CardContent class="p-5"
          ><Globe2Icon class="text-background/75" />
          <p class="mt-7 text-3xl font-semibold">
            12.8k<span class="ml-1 text-sm font-normal text-background/45"
              >条</span
            >
          </p>
          <p class="mt-1 text-sm text-background/50">已沉淀知识</p></CardContent
        ></Card
      >
    </div>
  </section>
</template>
