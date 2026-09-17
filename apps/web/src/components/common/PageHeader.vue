<script setup lang="ts">
defineProps<{ eyebrow: string; title: string; subtitle: string }>();
</script>

<template>
  <Teleport defer to="#topbar-page-context">
    <div class="topbar-page-context">
      <div class="topbar-page-copy">
        <p class="topbar-page-eyebrow">{{ eyebrow }}</p>
        <h1>{{ title }}</h1>
        <p class="topbar-page-subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.action" class="topbar-page-action">
        <slot name="action" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.page-heading {
  margin-bottom: 1.5625rem;
}

.heading-with-action {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.375rem;
}

.eyebrow {
  margin: 0 0 0.6875rem;
  color: var(--teal-dark, #0b8276);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: var(--workspace-text, #18242c);
  font-size: clamp(1.5rem, 2vw, 1.75rem);
  font-weight: 680;
  letter-spacing: -0.045em;
  line-height: 1.13;
}

.page-subtitle {
  margin: 0.5625rem 0 0;
  color: var(--workspace-subtle, #89979e);
  font-size: 0.75rem;
  line-height: 1.6;
}

.heading-action {
  flex: 0 0 auto;
}

@media (max-width: 47.5rem) {
  .heading-with-action {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-action {
    width: 100%;
  }
}
</style>

<style>
.topbar-page-context {
  display: flex;
  min-width: 0;
  height: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;

  /*
   * The parent slot is intentionally transparent to pointer events so it
   * cannot cover the neighbouring Topbar controls. Re-enable events for the
   * teleported page context itself, otherwise its action button inherits
   * `pointer-events: none` and remains visible but unclickable.
   */
  pointer-events: auto;
}

.topbar-page-copy {
  min-width: 0;
}

.topbar-page-eyebrow {
  margin: 0 0 0.2rem;
  color: var(--teal-dark, #0b8276);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.13em;
  line-height: 1;
  text-transform: uppercase;
}

.topbar-page-copy h1 {
  overflow: hidden;
  margin: 0;
  color: var(--workspace-text, #18242c);
  font-size: clamp(0.9rem, 1.25vw, 1.05rem);
  font-weight: 680;
  letter-spacing: -0.035em;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-page-subtitle {
  overflow: hidden;
  max-width: min(34rem, 34vw);
  margin: 0.2rem 0 0;
  color: var(--workspace-subtle, #89979e);
  font-size: 0.75rem;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-page-action {
  flex: 0 0 auto;
}

.topbar-page-action .button {
  white-space: nowrap;
}

.dark .topbar-page-copy h1 {
  color: var(--workspace-text);
}

.dark .topbar-page-subtitle {
  color: var(--workspace-muted);
}

@media (max-width: 68.75rem) {
  .topbar-page-subtitle {
    max-width: 22vw;
  }
}

@media (max-width: 47.5rem) {
  .topbar-page-context {
    gap: 0.5rem;
  }

  .topbar-page-eyebrow {
    font-size: 0.75rem;
  }

  .topbar-page-copy h1 {
    font-size: 0.8125rem;
  }

  .topbar-page-subtitle {
    display: none;
  }

  .topbar-page-action .button {
    padding-inline: 0.625rem;
    font-size: 0.75rem;
  }
}
</style>
