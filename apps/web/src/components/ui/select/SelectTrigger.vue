<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import type { SelectTriggerProps } from "reka-ui";
import { ChevronDown } from "@lucide/vue";
import { reactiveOmit } from "@vueuse/core";
import { SelectTrigger, useForwardProps } from "reka-ui";
import { cn } from "@/lib/utils";

const props = defineProps<
  SelectTriggerProps & { class?: HTMLAttributes["class"] }
>();
const delegatedProps = reactiveOmit(props, "class");
const forwarded = useForwardProps(delegatedProps);
</script>

<template>
  <SelectTrigger
    data-slot="select-trigger"
    v-bind="{ ...$attrs, ...forwarded }"
    :class="
      cn(
        'border-input bg-background text-foreground ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-8 w-full items-center justify-between gap-2 rounded-lg border px-2.5 text-xs outline-none transition-colors focus:ring-2 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1 [&_svg]:size-3.5 [&_svg]:shrink-0',
        props.class,
      )
    "
  >
    <slot />
    <ChevronDown class="text-muted-foreground" />
  </SelectTrigger>
</template>
