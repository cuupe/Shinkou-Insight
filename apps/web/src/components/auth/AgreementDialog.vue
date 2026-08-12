<script setup lang="ts">
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
defineProps<{ open: boolean; type: "terms" | "privacy" }>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)"
    ><DialogContent class="sm:max-w-lg"
      ><DialogHeader
        ><DialogTitle>{{
          type === "privacy" ? "隐私政策" : "用户协议"
        }}</DialogTitle
        ><DialogDescription
          >请阅读并了解 Shinkou Insight 的服务约定。</DialogDescription
        ></DialogHeader
      >
      <div
        class="max-h-72 overflow-y-auto rounded-xl bg-muted/50 p-4 text-sm leading-7 text-muted-foreground"
      >
        <p v-if="type === 'privacy'">
          我们只会收集提供服务所必需的信息，并使用行业标准的技术保护你的账号与工作数据。
        </p>
        <p v-else>
          使用 Shinkou Insight
          即表示你同意遵守适用法律法规，并对自己创建、上传和分享的内容负责。
        </p>
      </div>
      <DialogFooter
        ><Button
          type="button"
          class="bg-brand text-brand-foreground hover:bg-brand/90"
          @click="emit('update:open', false)"
          >我已了解</Button
        ></DialogFooter
      ></DialogContent
    ></Dialog
  >
</template>
