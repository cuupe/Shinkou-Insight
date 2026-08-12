<script setup lang="ts">
import { Moon, Sun } from "@lucide/vue";
import { useTheme } from "@/composables/useTheme";

const { isDark, toggleTheme } = useTheme();
</script>

<template>
  <button
    class="theme-toggle"
    type="button"
    :aria-label="isDark ? '切换到白天模式' : '切换到黑夜模式'"
    :title="isDark ? '切换到白天模式' : '切换到黑夜模式'"
    @click="toggleTheme"
  >
    <Sun v-if="isDark" :size="16" />
    <Moon v-else :size="16" />
  </button>
</template>
