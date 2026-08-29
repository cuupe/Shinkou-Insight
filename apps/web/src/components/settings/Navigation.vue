<script setup lang="ts">
import { ArrowRight } from "@lucide/vue";
import { RouterLink } from "vue-router";
import { useWorkspace } from "@/composables/useWorkspace";
const { currentName, settingsNav, routeTo } = useWorkspace();
</script>

<template>
  <aside class="settings-nav" aria-label="设置导航">
    <RouterLink
      v-for="item in settingsNav"
      :key="item.name"
      :to="routeTo(item.name)"
      :class="{ active: currentName === item.name }"
      :aria-current="currentName === item.name ? 'page' : undefined"
      ><component :is="item.icon" :size="16" />{{ item.label
      }}<ArrowRight :size="14"
    /></RouterLink>
  </aside>
</template>
