<script setup lang="ts">
import PageHeader from "@/components/common/PageHeader.vue";
import Navigation from "@/components/settings/Navigation.vue";
defineProps<{ eyebrow: string; title: string; subtitle: string }>();
</script>

<template>
  <PageHeader :eyebrow="eyebrow" :title="title" :subtitle="subtitle" />
  <div class="settings-layout">
    <Navigation />
    <section class="panel settings-panel"><slot /></section>
  </div>
</template>
