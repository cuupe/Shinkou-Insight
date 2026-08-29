<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import type { SelectContentProps } from "reka-ui";
import { reactiveOmit } from "@vueuse/core";
import { SelectContent, SelectPortal, SelectViewport } from "reka-ui";
import { cn } from "@/lib/utils";

const props = withDefaults(
  defineProps<SelectContentProps & { class?: HTMLAttributes["class"] }>(),
  { position: "popper" },
);
const delegatedProps = reactiveOmit(props, "class");
</script>

<template>
  <SelectPortal>
    <SelectContent
      data-slot="select-content"
      v-bind="{ ...$attrs, ...delegatedProps }"
      :class="cn(
        'bg-popover text-popover-foreground data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 relative z-50 max-h-72 min-w-[8rem] overflow-hidden rounded-lg border p-1 shadow-lg outline-none',
        props.class,
      )"
    >
      <SelectViewport class="p-0.5"><slot /></SelectViewport>
    </SelectContent>
  </SelectPortal>
</template>
