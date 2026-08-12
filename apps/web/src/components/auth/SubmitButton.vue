<script setup lang="ts">
import { ArrowRightIcon, LoaderCircleIcon } from "@lucide/vue";
import { Button } from "@/components/ui/button";
defineProps<{ loading: boolean }>();
</script>

<template>
  <Button
    type="submit"
    :disabled="loading"
    class="h-11 w-full bg-brand text-brand-foreground shadow-lg shadow-brand/20 hover:bg-brand/90"
    ><LoaderCircleIcon
      v-if="loading"
      class="animate-spin"
      data-icon="inline-start" /><ArrowRightIcon
      v-else
      data-icon="inline-end" /><span><slot /></span
  ></Button>
</template>
