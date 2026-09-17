<script setup lang="ts">
import { Search } from "@lucide/vue";
import type { HTMLAttributes } from "vue";

withDefaults(
  defineProps<{
    modelValue: string;
    placeholder?: string;
    ariaLabel?: string;
    shortcut?: string;
    variant?: "topbar" | "page";
    class?: HTMLAttributes["class"];
  }>(),
  {
    placeholder: "搜索…",
    ariaLabel: "搜索",
    shortcut: "",
    variant: "page",
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: string];
  submit: [];
}>();

function handleInput(event: Event) {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}
</script>

<template>
  <label :class="['search-field', `search-field-${variant}`, $props.class]">
    <Search :size="16" aria-hidden="true" />
    <input
      :value="modelValue"
      :placeholder="placeholder"
      :aria-label="ariaLabel"
      type="search"
      autocomplete="off"
      @input="handleInput"
      @keydown.enter.prevent="emit('submit')"
    />
    <kbd v-if="shortcut">{{ shortcut }}</kbd>
  </label>
</template>

<style scoped>
.search-field {
  display: flex;
  height: 2.25rem;
  width: 100%;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.6875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-soft);
  color: var(--workspace-muted);
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.search-field:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 18%, transparent);
}

.search-field-topbar {
  width: 17.5rem;
}

.search-field-page {
  width: min(16rem, 30vw);
}

.search-field input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.8125rem;
}

.search-field input::placeholder {
  color: var(--workspace-subtle);
}

.search-field input::-webkit-search-cancel-button {
  appearance: none;
}

.search-field kbd {
  flex: 0 0 auto;
  padding: 0.125rem 0.25rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.2;
}

@media (max-width: 47.5rem) {
  .search-field-topbar {
    display: none;
  }

  .search-field-page {
    width: 100%;
  }
}
</style>
