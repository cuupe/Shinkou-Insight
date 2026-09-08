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

<style>
.settings-layout {
  display: grid;
  min-width: 0;
  grid-template-columns: 13.125rem minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.settings-nav {
  display: grid;
  gap: 0.1875rem;
}
.settings-nav a {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  min-height: 2.25rem;
  padding: 0.5rem 0.75rem;
  color: #829196;
  font-size: 0.75rem;
  text-decoration: none;
  border-radius: 0.5rem;
}
.settings-nav a svg:last-child {
  margin-left: auto;
  opacity: 0;
}
.settings-nav a.active,
.settings-nav a:hover {
  color: var(--teal-dark);
  background: #e9f5f3;
}
.settings-nav a.active svg:last-child {
  opacity: 1;
}
.settings-panel {
  width: 100%;
  min-width: 0;
  min-height: 0;
  overflow: visible;
}
.settings-section {
  min-width: 0;
  padding: 1.125rem 1.25rem;
  border-bottom: 0.0625rem solid #edf1f1;
}
.settings-section:last-child {
  border-bottom: 0;
}
.settings-section > div:first-child h2 {
  color: #293a40;
  font-size: 1rem;
  margin: 0;
}
.settings-section > div:first-child p {
  color: #93a0a4;
  max-width: 60rem;
  font-size: 0.75rem;
  line-height: 1.55;
  margin: 0.375rem 0 1rem;
}
.form-grid {
  display: grid;
  min-width: 0;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  max-width: 43.75rem;
}
.field-label {
  display: grid;
  gap: 0.375rem;
  min-width: 0;
  color: #718187;
  font-size: 0.75rem;
  font-weight: 650;
}
.field-label input,
.field-label textarea,
.field-label select {
  width: 100%;
  border: 0.0625rem solid #dfe9e8;
  border-radius: 0.4375rem;
  background: #fff;
  color: #3b4d53;
  padding: 0.5rem 0.625rem;
  outline: 0;
  font: inherit;
  font-size: 0.8125rem;
  resize: vertical;
}
.field-label input:focus,
.field-label textarea:focus,
.field-label select:focus {
  border-color: #71c9bd;
  box-shadow: 0 0 0 0.1875rem rgba(20, 184, 166, 0.08);
}
.field-wide {
  grid-column: 1 / -1;
}
.danger-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
}
.config-list {
  border: 0.0625rem solid #e7eeee;
  border-radius: 0.5rem;
  max-width: 48.75rem;
}
.config-list > .empty-state {
  box-sizing: border-box;
  min-height: 7.5rem;
  padding: 1.25rem 1rem 1.375rem;
}
.config-row,
.prompt-row {
  min-height: 3.25rem;
  padding: 0.5rem 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  border-bottom: 0.0625rem solid #edf1f1;
}
.config-row:last-child,
.prompt-row:last-child {
  border-bottom: 0;
}
.config-row > span:nth-child(2) {
  flex: 1;
  min-width: 0;
}
.config-row strong,
.config-row small {
  display: block;
}
.config-row strong {
  color: #3d4f55;
  font-size: 0.75rem;
}
.config-row small {
  color: #9aa7aa;
  font-size: 0.6875rem;
  margin-top: 0.25rem;
}
.config-icon {
  background: #edf7f5;
  color: var(--teal-dark);
}
.prompt-list {
  border: 0.0625rem solid #e7eeee;
  border-radius: 0.5rem;
  max-width: 48.75rem;
  margin-bottom: 1.125rem;
}
.prompt-row code {
  flex: 1;
  color: #4e5ece;
  font-size: 0.6875rem;
}
.prompt-row span {
  color: #63777d;
  font-size: 0.6875rem;
}
.prompt-row small {
  color: #a0adaf;
  font-size: 0.6875rem;
}

.project-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 1.5625rem;
}
.project-title-line {
  gap: 0.5625rem;
}
.project-title-line .eyebrow {
  margin: 0;
}
.project-hero h1 {
  margin-top: 0.75rem;
}
.project-hero > div > p:not(.eyebrow) {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  margin: 0.5625rem 0 0.9375rem;
}
.hero-meta {
  flex-wrap: wrap;
  gap: 1rem;
  color: var(--workspace-muted);
  font-size: 0.625rem;
}
.hero-meta span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
}
.quick-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.8125rem;
  margin-bottom: 1.125rem;
}
.quick-actions button {
  border: 0.0625rem solid var(--workspace-border);
  background: var(--surface);
  border-radius: 0.6875rem;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.875rem;
  text-align: left;
  cursor: pointer;
}
.quick-actions button:hover {
  border-color: #b9d9d5;
  transform: translateY(-0.0625rem);
}
.quick-actions button > span:nth-child(2) {
  flex: 1;
  min-width: 0;
}
.quick-actions strong,
.quick-actions small {
  display: block;
}
.quick-actions strong {
  color: var(--workspace-text);
  font-size: 0.6875rem;
}
.quick-actions small {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  margin-top: 0.25rem;
}
.quick-icon {
  width: 2.125rem;
  height: 2.125rem;
  border-radius: 0.5625rem;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
}

.settings-section > .button {
  margin-top: 1rem;
}

.settings-layout .section-intro,
.settings-layout .section-actions,
.settings-layout .policy-actions {
  flex-wrap: wrap;
}

.settings-layout .section-intro > .button,
.settings-layout .section-actions {
  margin-left: auto;
}

.settings-layout .model-overview,
.settings-layout .connector-overview,
.settings-layout .overview-copy,
.settings-layout .model-row,
.settings-layout .tool-row,
.settings-layout .prompt-row,
.settings-layout .security-setting-row,
.settings-layout .preference-row {
  min-width: 0;
}

.settings-layout .model-copy small,
.settings-layout .tool-copy small,
.settings-layout .prompt-copy small {
  overflow: visible;
  font-size: 0.6875rem;
  line-height: 1.45;
  text-overflow: clip;
  white-space: normal;
}

.settings-layout .permission-note,
.settings-layout .policy-actions > span {
  font-size: 0.625rem;
  line-height: 1.5;
}

.settings-layout .section-actions,
.settings-layout .policy-actions {
  gap: 0.75rem;
}

@media (max-width: 47.5rem) {
  .quick-actions {
    grid-template-columns: 1fr;
  }

  .settings-layout {
    grid-template-columns: 1fr;
    gap: 0.875rem;
  }

  .settings-section {
    padding: 1rem;
  }

  .settings-layout .section-intro > .button,
  .settings-layout .section-actions {
    width: 100%;
    margin-left: 0;
  }

  .settings-layout .policy-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .settings-nav {
    display: flex;
    overflow-x: auto;
    padding-bottom: 0.1875rem;
  }

  .settings-nav a {
    white-space: nowrap;
  }

  .settings-nav a svg:last-child {
    display: none;
  }
}
</style>
