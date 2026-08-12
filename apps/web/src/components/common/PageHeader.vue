<script setup lang="ts">
defineProps<{ eyebrow: string; title: string; subtitle: string }>();
</script>

<template>
  <div class="page-heading heading-with-action">
    <div>
      <p class="eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p class="page-subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.action" class="heading-action">
      <slot name="action" />
    </div>
  </div>
</template>
