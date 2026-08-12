<script setup lang="ts">
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldContent,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
const props = defineProps<{
  id: string;
  modelValue: boolean;
  error?: string;
}>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  open: [type: "terms" | "privacy"];
}>();
</script>

<template>
  <Field
    orientation="horizontal"
    class="agreement-field items-start gap-2"
    :data-invalid="!!props.error"
    ><Checkbox
      :id="props.id"
      :model-value="props.modelValue"
      class="mt-0.5"
      @update:model-value="emit('update:modelValue', $event === true)"
    /><FieldContent
      ><FieldLabel
        :for="props.id"
        class="agreement-label text-xs font-normal text-muted-foreground"
        >我已阅读并同意
        <Button
          type="button"
          variant="link"
          class="h-auto p-0 text-xs text-foreground underline underline-offset-4"
          @click="emit('open', 'terms')"
          >用户协议</Button
        >
        与
        <Button
          type="button"
          variant="link"
          class="h-auto p-0 text-xs text-foreground underline underline-offset-4"
          @click="emit('open', 'privacy')"
          >隐私政策</Button
        ></FieldLabel
      ><FieldError v-if="props.error">{{
        props.error
      }}</FieldError></FieldContent
    ></Field
  >
</template>
