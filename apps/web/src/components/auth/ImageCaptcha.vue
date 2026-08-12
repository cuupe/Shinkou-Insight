<script setup lang="ts">
import { onMounted, watch } from "vue";
import { LoaderCircleIcon, RefreshCwIcon } from "@lucide/vue";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useCaptcha } from "@/composables/useCaptcha";

const props = defineProps<{
  id: string;
  modelValue: string;
  captchaId?: string;
  imageUrl?: string;
  error?: string;
}>();
const emit = defineEmits<{
  "update:modelValue": [value: string];
  "update:captchaId": [value: string];
  refresh: [];
}>();
const {
  imageUrl,
  captchaId,
  loading,
  error: loadError,
  refresh: loadCaptcha,
} = useCaptcha();

async function refreshCaptcha() {
  emit("update:modelValue", "");
  emit("refresh");
  await loadCaptcha();
  emit("update:captchaId", captchaId.value);
}

onMounted(refreshCaptcha);
watch(captchaId, (value) => emit("update:captchaId", value));
</script>

<template>
  <Field class="image-captcha-field" :data-invalid="!!props.error">
    <div class="image-captcha-label-row">
      <FieldLabel :for="props.id">图片验证码</FieldLabel
      ><span class="image-captcha-hint">点击图片刷新</span>
    </div>
    <div class="image-captcha-row">
      <Input
        :id="props.id"
        :model-value="props.modelValue"
        maxlength="6"
        placeholder="请输入图片验证码"
        @update:model-value="emit('update:modelValue', String($event))"
      />
      <Button
        type="button"
        variant="outline"
        class="image-captcha-box"
        :disabled="loading"
        @click="refreshCaptcha"
      >
        <img
          v-if="props.imageUrl || imageUrl"
          :src="props.imageUrl || imageUrl"
          alt="图片验证码"
        />
        <template v-else
          ><small>{{ loadError }}</small
          ><LoaderCircleIcon
            v-if="loading"
            class="animate-spin"
            :size="13" /><RefreshCwIcon v-else :size="13"
        /></template>
      </Button>
    </div>
    <FieldError v-if="props.error">{{ props.error }}</FieldError>
  </Field>
</template>
