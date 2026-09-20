<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import type { SelectItemProps } from "reka-ui";
import { Check } from "@lucide/vue";
import { reactiveOmit } from "@vueuse/core";
import {
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  useForwardProps,
} from "reka-ui";
import { cn } from "@/lib/utils";

const props = defineProps<
  SelectItemProps & { class?: HTMLAttributes["class"] }
>();
const delegatedProps = reactiveOmit(props, "class");
const forwarded = useForwardProps(delegatedProps);
</script>

<template>
  <SelectItem
    data-slot="select-item"
    v-bind="{ ...$attrs, ...forwarded }"
    :class="
      cn(
        'focus:bg-muted focus:text-foreground relative flex w-full cursor-default select-none items-center rounded-md py-1.5 pl-7 pr-2 text-xs outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        props.class,
      )
    "
  >
    <span class="absolute left-2 flex size-3.5 items-center justify-center">
      <SelectItemIndicator><Check class="size-3.5" /></SelectItemIndicator>
    </span>
    <SelectItemText><slot /></SelectItemText>
  </SelectItem>
</template>
