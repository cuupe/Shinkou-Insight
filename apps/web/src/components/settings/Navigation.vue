<script setup lang="ts">
import { ArrowRight } from "@lucide/vue";
import { RouterLink } from "vue-router";
import { useWorkspace } from "@/composables/useWorkspace";
const { currentName, settingsNav, routeTo } = useWorkspace();
</script>

<template>
  <aside class="settings-nav">
    <RouterLink
      v-for="item in settingsNav"
      :key="item.name"
      :to="routeTo(item.name)"
      :class="{ active: currentName === item.name }"
      ><component :is="item.icon" :size="16" />{{ item.label
      }}<ArrowRight :size="14"
    /></RouterLink>
  </aside>
</template>
