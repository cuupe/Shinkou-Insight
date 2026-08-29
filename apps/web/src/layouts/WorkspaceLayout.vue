<script setup lang="ts">
import { RouterView } from "vue-router";
import Sidebar from "@/components/navigation/Sidebar.vue";
import Topbar from "@/components/navigation/Topbar.vue";
import { useWorkspace } from "@/composables/useWorkspace";

const { mobileOpen } = useWorkspace();
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': !mobileOpen }">
    <div class="sidebar-slot">
      <Sidebar />
    </div>

    <section class="app-content">
      <Topbar />

      <main class="page-content">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell {
  --sidebar-width: 15.5rem;

  --sidebar-bg: #111b24;
  --sidebar-muted: #8e9ba7;
  --sidebar-text: #e8f0f3;
  --workspace-bg: #f5f8f8;
  --surface: #ffffff;
  --surface-raised: #fbfcfc;
  --surface-soft: #f1f5f5;
  --workspace-text: #18242c;
  --workspace-muted: #64757b;
  --workspace-subtle: #89979e;
  --workspace-border: #e3ebeb;
  --workspace-divider: #edf1f1;
  --workspace-chart-grid: #edf1f1;
  --workspace-chart-axis: #89979e;
  --workspace-chart-line: #16b8a6;
  --workspace-chart-fill: #16b8a6;
  --teal: #14b8a6;
  --teal-dark: #0b8276;
  --violet: #8175e8;
  --amber: #d99022;
  --red: #d76363;

  height: 100dvh;
  min-height: 0;

  display: flex;

  overflow: hidden;

  background: var(--workspace-bg);
  color: var(--workspace-text);

  font-family: "Geist", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.sidebar-slot {
  position: relative;

  flex: 0 0 var(--sidebar-width);

  width: var(--sidebar-width);
  min-width: 0;

  height: 100dvh;

  transition:
    flex-basis 0.25s ease,
    width 0.25s ease;
}

.app-shell.sidebar-collapsed .sidebar-slot {
  flex-basis: 0;
  width: 0;
}
.app-content {
  height: 100%;
  min-height: 0;
  min-width: 0;
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overscroll-behavior: contain;
}

.page-content {
  flex: 1 1 auto;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  padding: 2.375rem clamp(1.25rem, 3vw, 2.625rem) 4.375rem;
}

@media (max-width: 47.5rem) {
  .app-shell {
    height: 100dvh;
    display: flex;
    overflow: hidden;
  }

  .app-content {
    height: 100%;
    overflow: hidden;
  }

  .page-content {
    height: 100%;
    overflow: hidden;
    padding: 1.5625rem 1rem 2.8125rem;
  }
}
</style>
<style>
@media (max-width: 68.75rem) {
  .app-sidebar {
    width: 13.75rem;
    min-width: 13.75rem;
  }
  .app-topbar {
    padding: 0 1.4375rem;
  }
  .page-content {
    padding: 1.875rem 1.5625rem 3.4375rem;
  }
  .research-workspace {
    grid-template-columns: 1fr 1fr;
  }
  .evidence-panel {
    grid-column: 1 / -1;
    min-height: auto;
  }
  .dashboard-grid,
  .two-column-grid {
    grid-template-columns: 1fr;
  }
  .project-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .project-card {
    padding: 1.375rem;
  }
  .run-create-layout {
    grid-template-columns: 1fr;
  }
  .run-preview-panel {
    max-width: none;
  }
  .reports-layout {
    grid-template-columns: 16.25rem minmax(0, 1fr);
  }
}
.page-heading h1,
.project-hero h1,
.detail-heading h1,
.run-detail-top h1 {
  font-size: 1.5rem;
}
.stat-grid,
.quick-actions,
.project-grid,
.evaluation-metrics {
  grid-template-columns: repeat(2, 1fr);
}
.stat-card {
  padding: 1rem;
}
.stat-card > strong {
  font-size: 1.375rem;
}
.two-column-grid,
.overview-grid,
.asset-detail-grid,
.playground-layout,
.settings-layout,
.reports-layout,
.research-workspace,
.kanban-board {
  grid-template-columns: 1fr;
}
.overview-grid .overview-report {
  grid-column: auto;
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
.project-hero,
.detail-heading,
.run-detail-top,
.heading-with-action {
  align-items: flex-start;
  flex-direction: column;
}
.heading-actions {
  width: 100%;
}
.heading-actions .button {
  flex: 1;
}
.asset-toolbar {
  align-items: flex-start;
  flex-direction: column;
  padding-inline: 1.125rem;
}
.asset-table-panel {
  overflow-x: auto;
}
.asset-table-panel .data-table {
  min-width: 47.5rem;
}
.asset-error {
  position: static;
  grid-column: 1 / -1;
  transform: none;
  padding: 0 0 0.5rem;
}
.run-summary-row,
.action-summary {
  overflow-x: auto;
  gap: 1.5rem;
}
.run-summary-row .select-button {
  margin-left: auto;
}
.run-table {
  min-width: 46.875rem;
}
.run-table + * {
  min-width: 0;
}
.run-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
}
.run-metrics div {
  min-width: 0;
  border-bottom: 0.0625rem solid #edf1f1;
}
.run-metrics div:nth-child(2) {
  border-right: 0;
}
.run-metrics div:nth-child(3),
.run-metrics div:nth-child(4) {
  border-bottom: 0;
}
.timeline-panel,
.event-panel,
.evidence-panel {
  min-height: auto;
}
.markdown-body {
  padding: 1.5625rem 1.4375rem 2.5rem;
}
.quality-bars {
  padding-inline: 1.125rem;
}
.form-grid,
.two-inputs {
  grid-template-columns: 1fr;
}
.field-wide {
  grid-column: auto;
}
.danger-section {
  align-items: flex-start;
  flex-direction: column;
}
.upload-zone {
  align-items: flex-start;
  flex-wrap: wrap;
}
.upload-zone .button {
  margin-left: 3.25rem;
}
.evidence-drawer {
  right: 0.75rem;
  bottom: 0.75rem;
  width: calc(100vw - 1.5rem);
}
.score-row {
  gap: 0.5rem;
  flex-wrap: wrap;
}
.score-row span:last-child {
  margin-left: 0;
}

@media (max-width: 30rem) {
  .stat-grid,
  .quick-actions,
  .project-grid,
  .evaluation-metrics {
    grid-template-columns: 1fr;
  }
  .stat-card {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
  }
  .stat-card > strong {
    margin: 0.5rem 0 0;
    grid-row: 2;
  }
  .stat-trend {
    grid-column: 2;
    grid-row: 2;
  }
  .chart-summary {
    gap: 1.125rem;
  }
  .chart-summary strong {
    font-size: 0.875rem;
  }
  .page-heading .button {
    width: 100%;
  }
  .asset-title {
    align-items: flex-start;
  }
  .run-detail-top .heading-actions {
    flex-wrap: wrap;
  }
  .run-detail-top .heading-actions .button {
    min-width: 0;
  }
  .quality-bars {
    padding-inline: 0.3125rem;
  }
  .bar {
    width: 0.6875rem;
  }
  .panel-heading {
    padding-inline: 1.125rem;
  }
  .focus-list,
  .mini-run-list,
  .report-list {
    padding-inline: 1.125rem;
  }
  .asset-detail-grid > .panel {
    padding: 1.375rem;
  }
  .detail-facts {
    grid-template-columns: 1fr;
  }
}

/* Workspace dark theme -------------------------------------------------- */
.dark .app-shell {
  --sidebar-bg: #0b1419;
  --sidebar-muted: #93a6ab;
  --sidebar-text: #e3f0ef;
  --workspace-bg: #0d171b;
  --surface: #142329;
  --surface-raised: #192b31;
  --surface-soft: #1c3036;
  --workspace-text: #e7f1f0;
  --workspace-muted: #9cafb2;
  --workspace-border: #2c4147;
  --workspace-divider: #294047;
  --workspace-chart-grid: #294047;
  --workspace-chart-axis: #9cafb2;
  --workspace-chart-line: #45d6c3;
  --workspace-chart-fill: #45d6c3;
  color: var(--workspace-text);
}

.dark .app-shell .app-content,
.dark .app-shell .page-content {
  color: var(--workspace-text);
  background: var(--workspace-bg);
}

.dark .app-shell .app-topbar {
  border-color: var(--workspace-border);
  background: color-mix(in oklab, var(--surface) 92%, transparent);
}

.dark .app-shell .breadcrumbs,
.dark .app-shell .page-subtitle,
.dark .app-shell .panel-heading p,
.dark .app-shell .stat-top,
.dark .app-shell .chart-legend,
.dark .app-shell .chart-y,
.dark .app-shell .chart-x,
.dark .app-shell .focus-number,
.dark .app-shell .focus-item p,
.dark .app-shell .run-title small,
.dark .app-shell .member-cell small,
.dark .app-shell .asset-name-cell small,
.dark .app-shell .muted-cell {
  color: var(--workspace-muted);
}

.dark .app-shell .breadcrumbs strong,
.dark .app-shell .page-heading h1,
.dark .app-shell .project-hero h1,
.dark .app-shell .detail-heading h1,
.dark .app-shell .run-detail-top h1,
.dark .app-shell .panel-heading h2,
.dark .app-shell .stat-card > strong,
.dark .app-shell .chart-summary strong,
.dark .app-shell .evaluation-metrics strong,
.dark .app-shell .focus-item strong,
.dark .app-shell .run-title strong,
.dark .app-shell .member-cell strong,
.dark .app-shell .asset-name-cell strong {
  color: var(--workspace-text);
}

.dark .app-shell .evaluation-metrics > div {
  border-color: var(--workspace-border);
  background: var(--surface);
  color: var(--workspace-text);
}

.dark .app-shell .evaluation-metrics span,
.dark .app-shell .evaluation-metrics small,
.dark .app-shell .metric-card span,
.dark .app-shell .metric-card small,
.dark .app-shell .quality-bar-group > span,
.dark .app-shell .case-query,
.dark .app-shell .result-text,
.dark .app-shell .score-row,
.dark .app-shell .score-row span:last-child,
.dark .app-shell .score-total small {
  color: var(--workspace-muted);
}

.dark .app-shell .evaluation-metrics strong,
.dark .app-shell .metric-card strong,
.dark .app-shell .score-row strong {
  color: var(--workspace-text);
}

.dark .app-shell .select-button,
.dark .app-shell .button-secondary,
.dark .app-shell .mini-button,
.dark .app-shell .filter-box,
.dark .app-shell .number-input,
.dark .app-shell .upload-zone {
  border-color: var(--workspace-border);
  background: var(--surface-raised);
  color: var(--workspace-text);
}

.dark .app-shell .select-button,
.dark .app-shell .button-secondary {
  color: var(--workspace-text);
}

.dark .app-shell .icon-button,
.dark .app-shell .mobile-menu,
.dark .app-shell .user-menu {
  color: var(--workspace-muted);
}

.dark .app-shell .icon-button:hover,
.dark .app-shell .mobile-menu:hover,
.dark .app-shell .button-secondary:hover,
.dark .app-shell .mini-button:hover {
  background: var(--surface-soft);
  color: var(--workspace-text);
}

.dark .app-shell .panel,
.dark .app-shell .stat-card,
.dark .app-shell .metric-card,
.dark .app-shell .action-card,
.dark .app-shell .run-metrics,
.dark .app-shell .run-summary-row,
.dark .app-shell .action-summary,
.dark .app-shell [class*="-panel"] {
  border-color: var(--workspace-border);
  background: var(--surface);
  color: var(--workspace-text);
  box-shadow: 0 0.4375rem 1.4375rem rgba(0, 0, 0, 0.18);
}

.dark .app-shell .table-row,
.dark .app-shell .chart-summary,
.dark .app-shell .focus-item,
.dark .app-shell .form-step,
.dark .app-shell .run-metrics div,
.dark .app-shell .reader-toolbar,
.dark .app-shell .settings-section {
  border-color: var(--workspace-border);
}

.dark .app-shell .table-row.table-header {
  background: var(--surface-raised);
  color: var(--workspace-muted);
}

.dark .app-shell .kanban-column,
.dark .app-shell .playground-controls,
.dark .app-shell .filter-panel,
.dark .app-shell .asset-toolbar {
  border-color: var(--workspace-border);
  background: var(--surface-raised);
  color: var(--workspace-text);
}

.dark .app-shell .button-primary {
  background: #1a6861;
  color: #eafffb;
}

.dark .app-shell .button-danger {
  border-color: #633b40;
  background: #321f24;
  color: #ffaaa8;
}

.dark .app-shell .form-grid input,
.dark .app-shell .form-grid textarea,
.dark .app-shell .field-label input,
.dark .app-shell .field-label textarea {
  border-color: var(--workspace-border);
  background: var(--surface-raised);
  color: var(--workspace-text);
}

.dark .app-shell .form-grid input::placeholder,
.dark .app-shell .form-grid textarea::placeholder,
.dark .app-shell .field-label input::placeholder,
.dark .app-shell .field-label textarea::placeholder {
  color: var(--workspace-muted);
}

.dark .app-shell .toast-message {
  background: #1b5b55;
  color: #eafffb;
}
</style>

<style>
/* The viewport belongs to the shell. Every page-level child owns its own
   overflow so a long table or reader cannot move the navigation with it. */
.app-shell,
.app-content,
.page-content {
  overscroll-behavior: none;
}

.app-topbar {
  flex: 0 0 auto;
}

.page-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.page-content:has(> .agent-page) {
  gap: 0;
  padding: 1rem clamp(0.75rem, 1.25vw, 1.125rem) 0.75rem;
}

.page-content > * {
  min-height: 0;
  overflow-y: auto;
}

.page-content > .back-button,
.page-content > .hero-meta,
.page-content > .quick-actions,
.page-content > .action-summary,
.page-content > .action-toolbar,
.page-content > .queue-summary,
.page-content > .report-metrics,
.page-content > .knowledge-health-grid,
.page-content > .asset-status-strip,
.page-content > .asset-error-banner,
.page-content > .run-metrics,
.page-content > .stat-grid,
.page-content > .evaluation-overview,
.page-content > .evaluation-metrics {
  flex: 0 0 auto;
  overflow: visible;
}

.page-content > .agent-workspace,
.page-content > .agent-page,
.page-content > .asset-detail-layout,
.page-content > .asset-table-panel,
.page-content > .dashboard-grid,
.page-content > .two-column-grid,
.page-content > .project-grid,
.page-content > .members-panel,
.page-content > .action-board,
.page-content > .evaluation-dashboard-grid,
.page-content > .run-create-layout,
.page-content > .playground-layout,
.page-content > .research-workspace,
.page-content > .reports-layout,
.page-content > .settings-layout,
.page-content > .queue-panel,
.page-content > .notifications-page {
  flex: 1 1 0;
}

/* 概览页：卡片按内容完整展示，不被视口压缩，整页滚动 */
.app-shell .page-content:has(> .dashboard-grid) {
  overflow-y: auto;
}

.app-shell .page-content:has(> .dashboard-grid) > * {
  flex: 0 0 auto;
  overflow: visible;
}

.page-content > .agent-workspace,
.page-content > .agent-page,
.page-content > .asset-table-panel,
.page-content > .playground-layout,
.page-content > .reports-layout,
.page-content > .settings-layout,
.page-content > .queue-panel {
  overflow: hidden;
}

.page-content > .asset-detail-layout,
.page-content > .dashboard-grid,
.page-content > .two-column-grid,
.page-content > .project-grid,
.page-content > .members-panel,
.page-content > .action-board,
.page-content > .evaluation-dashboard-grid,
.page-content > .run-create-layout,
.page-content > .research-workspace {
  overflow: auto;
}

/* 评估页按内容自然展开，由整页承载滚动，趋势卡片不再单独滚动 */
.app-shell .page-content:has(> .evaluation-dashboard-grid) {
  overflow-y: auto;
}

.app-shell .page-content:has(> .evaluation-dashboard-grid) > * {
  flex: 0 0 auto;
  overflow: visible;
}

.app-shell .page-content:has(> .evaluation-dashboard-grid) > .evaluation-dashboard-grid,
.app-shell .page-content:has(> .evaluation-dashboard-grid) .evaluation-dashboard-grid > .panel {
  overflow: visible;
}

/* 帮助中心按整页内容滚动，滚动条贴着工作区视口边缘 */
.app-shell .page-content:has(> .help-center) {
  overflow-y: auto;
}

.app-shell .page-content:has(> .help-center) > * {
  flex: 0 0 auto;
  overflow: visible;
}

/* 通知中心按整页内容滚动，避免通知列表被压缩在局部滚动容器中 */
.app-shell .page-content:has(> .notifications-page) {
  overflow-y: auto;
}

.app-shell .page-content:has(> .notifications-page) > * {
  flex: 0 0 auto;
  overflow: visible;
}

/* 设置页按整页滚动，避免表单和长说明被限制在 panel 内部 */
.app-shell .page-content:has(> .settings-layout) {
  overflow-y: auto;
}

.app-shell .page-content:has(> .settings-layout) > * {
  flex: 0 0 auto;
  overflow: visible;
}

.app-shell .page-content:has(> .settings-layout) .settings-panel {
  overflow: visible;
}

.asset-table-panel .data-table,
.members-panel .data-table,
.queue-table-wrap,
.reports-list-panel .full-list,
.report-reader,
.settings-panel,
.action-card-list,
.evaluation-dashboard-grid > .panel,
.playground-layout > .panel {
  min-height: 0;
  overflow: auto;
}

.asset-table-panel .data-table,
.queue-table-wrap,
.reports-list-panel .full-list {
  flex: 1 1 auto;
}

.asset-table-panel,
.queue-panel,
.reports-list-panel,
.report-reader,
.settings-layout,
.settings-panel {
  min-height: 0;
}

/* Theme contrast guardrails ---------------------------------------------
   A few older screens still carry light-theme utility colors in their
   local styles. Keep their layout-specific accents, but remap the surfaces
   and text that must remain legible when the workspace switches to dark. */
.dark .app-shell .settings-layout .settings-nav a {
  color: var(--workspace-muted);
}

.dark .app-shell .settings-layout .settings-nav a.active,
.dark .app-shell .settings-layout .settings-nav a:hover {
  color: var(--teal);
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
}

.dark .app-shell .settings-layout .settings-section {
  border-color: var(--workspace-border);
}

.dark .app-shell .settings-layout .settings-section > div:first-child h2,
.dark .app-shell .settings-layout .config-row strong,
.dark .app-shell .settings-layout .prompt-row span,
.dark .app-shell .settings-layout .field-label,
.dark .app-shell .settings-layout .project-title-line,
.dark .app-shell .settings-layout .project-hero h1 {
  color: var(--workspace-text);
}

.dark .app-shell .settings-layout .settings-section > div:first-child p,
.dark .app-shell .settings-layout .config-row small,
.dark .app-shell .settings-layout .prompt-row small,
.dark .app-shell .settings-layout .prompt-row span,
.dark .app-shell .settings-layout .field-label small {
  color: var(--workspace-muted);
}

.dark .app-shell .settings-layout .field-label input,
.dark .app-shell .settings-layout .field-label textarea,
.dark .app-shell .settings-layout .field-label select,
.dark .app-shell .settings-layout .config-list,
.dark .app-shell .settings-layout .prompt-list {
  border-color: var(--workspace-border);
  background: var(--surface-raised);
  color: var(--workspace-text);
}

.dark .app-shell .input-with-action {
  border-color: var(--workspace-border);
  background: var(--surface-raised);
}

.dark .app-shell .input-with-action input {
  background: transparent;
  color: var(--workspace-text);
}

.dark .app-shell .input-with-action button {
  color: var(--workspace-muted);
}

.dark .app-shell .settings-layout .config-row,
.dark .app-shell .settings-layout .prompt-row {
  border-color: var(--workspace-border);
}

.dark .app-shell .settings-layout .config-icon {
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
  color: var(--teal);
}

.dark .app-shell .settings-layout .prompt-row code {
  color: #aeb8ff;
}

.dark .app-shell .playground-layout .mode-switch {
  background: var(--surface-soft);
}

.dark .app-shell .playground-layout .mode-switch button {
  color: var(--workspace-muted);
}

.dark .app-shell .playground-layout .mode-switch button.active {
  background: var(--surface);
  color: var(--teal);
  box-shadow: 0 0.0625rem 0.1875rem rgb(0 0 0 / 24%);
}

.dark .app-shell .playground-layout .range-line strong,
.dark .app-shell .playground-layout .toggle-row strong,
.dark .app-shell .playground-layout .filter-box strong {
  color: var(--workspace-text);
}

.dark .app-shell .playground-layout .toggle-row small,
.dark .app-shell .playground-layout .filter-box span {
  color: var(--workspace-muted);
}

.dark .app-shell .playground-layout .toggle {
  background: var(--workspace-border);
}

.dark .app-shell .playground-layout .toggle i {
  background: var(--surface-raised);
}

.dark .app-shell .playground-layout .retrieval-card,
.dark .app-shell .playground-layout .retrieval-card h3,
.dark .app-shell .playground-layout .retrieval-card p,
.dark .app-shell .playground-layout .retrieval-source {
  color: var(--workspace-text);
}

.dark .app-shell .playground-layout .retrieval-card {
  border-color: var(--workspace-border);
  background: var(--surface);
}

.dark .app-shell .playground-layout .retrieval-card p,
.dark .app-shell .playground-layout .retrieval-source {
  color: var(--workspace-muted);
}

.dark .app-shell .playground-layout .retrieval-card.selected,
.dark .app-shell .playground-layout .retrieval-card:hover {
  border-color: color-mix(in oklab, var(--teal) 45%, var(--workspace-border));
  background: color-mix(in oklab, var(--teal) 8%, var(--surface));
}

.dark .app-shell .queue-summary-running > span,
.dark .app-shell .queue-status-running,
.dark .app-shell .queue-status-completed,
.dark .app-shell .queue-flow-icon {
  color: #68e1d0;
  background: color-mix(in oklab, var(--teal) 18%, var(--surface));
}

.dark .app-shell .queue-summary-queued > span,
.dark .app-shell .queue-status-queued,
.dark .app-shell .priority-normal {
  color: var(--workspace-muted);
  background: var(--surface-soft);
}

.dark .app-shell .queue-summary-paused > span,
.dark .app-shell .queue-status-paused {
  color: #f2bd69;
  background: #3b3021;
}

.dark .app-shell .queue-summary-completed > span,
.dark .app-shell .priority-low {
  color: #81d2a5;
  background: #203a30;
}

.dark .app-shell .queue-summary-failed > span,
.dark .app-shell .queue-status-failed,
.dark .app-shell .queue-status-cancelled,
.dark .app-shell .priority-high,
.dark .app-shell .status-failed {
  color: #ffaaa8;
  background: #321f24;
}

.dark .app-shell .priority-medium,
.dark .app-shell .status-review,
.dark .app-shell .status-running,
.dark .app-shell .status-indexing {
  color: #f2bd69;
  background: #3b3021;
}

.dark .app-shell .queue-status-running,
.dark .app-shell .queue-status-completed,
.dark .app-shell .queue-status-failed,
.dark .app-shell .queue-status-cancelled,
.dark .app-shell .queue-status-queued,
.dark .app-shell .queue-status-paused {
  border-radius: 0.3125rem;
  padding: 0.25rem 0.375rem;
}

.dark .app-shell .user-popover > .logout-menu-item:hover {
  color: #ffaaa8;
  background: #321f24;
}

.dark .app-shell .user-popover > .logout-menu-item {
  color: #ffaaa8;
}

.dark .app-shell .status-indexed,
.dark .app-shell .status-completed {
  color: #68e1d0;
}

.dark .app-shell .status-running,
.dark .app-shell .status-indexing {
  color: #f2bd69;
}

.dark .app-shell .status-failed {
  color: #ffaaa8;
}

.dark .app-shell .status-muted {
  color: var(--workspace-muted);
}

.dark .app-shell .switch-ui,
.dark .app-shell .switch-button {
  background: var(--workspace-border);
}

.dark .app-shell .switch-input:checked + .switch-ui,
.dark .app-shell .switch-button.active {
  background: var(--teal);
}

.dark .app-shell .model-form-section,
.dark .app-shell .connector-form-section {
  border-color: var(--workspace-border);
  background: var(--surface-raised);
}

.dark .app-shell .model-note,
.dark .app-shell .version-note,
.dark .app-shell .quality-note {
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
  color: #68e1d0;
}

.dark .app-shell .form-error,
.dark .app-shell .danger-confirm,
.dark .app-shell .delete-warning,
.dark .app-shell .asset-error-banner {
  border-color: #633b40;
  background: #321f24;
  color: #ffaaa8;
}

.dark .app-shell .asset-error-banner strong,
.dark .app-shell .danger-confirm strong {
  color: #ffaaa8;
}

.dark .app-shell .document-toolbar,
.dark .app-shell .metadata-panel dl div,
.dark .app-shell .chunk-row,
.dark .app-shell .prompt-list {
  border-color: var(--workspace-border);
}

.dark .app-shell .document-preview,
.dark .app-shell .document-preview h3,
.dark .app-shell .chunk-row strong,
.dark .app-shell .metadata-panel dd {
  color: var(--workspace-text);
}

.dark .app-shell .document-preview,
.dark .app-shell .chunk-row small,
.dark .app-shell .metadata-panel dt,
.dark .app-shell .preview-footnote,
.dark .app-shell .chunk-row > span {
  color: var(--workspace-muted);
}

.dark .app-shell .quote-highlight,
.dark .app-shell .selection-bar,
.dark .app-shell .filter-hint,
.dark .app-shell .empty-library-state > span {
  border-color: var(--workspace-border);
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
  color: #68e1d0;
}

.dark .app-shell .file-type,
.dark .app-shell .health-card-icon,
.dark .app-shell .metric-icon,
.dark .app-shell .report-file,
.dark .app-shell .prompt-icon,
.dark .app-shell .overview-icon,
.dark .app-shell .boundary-icon,
.dark .app-shell .security-icon,
.dark .app-shell .summary-icon {
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
  color: #68e1d0;
}

.dark .app-shell .file-type.pdf,
.dark .app-shell .attachment-pdf .attachment-icon,
.dark .app-shell .attachment-video .attachment-icon {
  background: #3b2727;
  color: #ffaaa8;
}

.dark .app-shell .file-type.markdown,
.dark .app-shell .attachment-file .attachment-icon,
.dark .app-shell .prompt-icon,
.dark .app-shell .metric-icon-blue,
.dark .app-shell .metric-icon-violet {
  background: #292a4a;
  color: #b4b8ff;
}

.dark .app-shell .file-type.text,
.dark .app-shell .attachment-spreadsheet .attachment-icon,
.dark .app-shell .health-card-icon.is-success {
  background: #203a30;
  color: #81d2a5;
}

.dark .app-shell .attachment-audio .attachment-icon,
.dark .app-shell .metric-icon-amber,
.dark .app-shell .health-card-icon.is-warning {
  background: #3b3021;
  color: #f2bd69;
}

.dark .app-shell .health-card-icon.is-danger,
.dark .app-shell .danger-icon,
.dark .app-shell .logout-icon {
  background: #321f24;
  color: #ffaaa8;
}

.dark .app-shell .segmented-tabs button,
.dark .app-shell .filter-tab {
  color: var(--workspace-muted);
}

.dark .app-shell .segmented-tabs button.active,
.dark .app-shell .filter-tab.active {
  background: color-mix(in oklab, var(--teal) 15%, var(--surface));
  color: #68e1d0;
}

.dark .app-shell .evaluation-overview {
  border-color: var(--workspace-border);
  background: linear-gradient(
    105deg,
    color-mix(in oklab, var(--teal) 11%, var(--surface)),
    var(--surface)
  );
}

.dark .app-shell .evaluation-overview-copy > strong,
.dark .app-shell .evaluation-overview-copy > p,
.dark .app-shell .overview-run {
  color: var(--workspace-text);
}

.dark .app-shell .overview-status,
.dark .app-shell .baseline-score,
.dark .app-shell .queue-live-note,
.dark .app-shell .queue-flow-steps {
  color: #68e1d0;
}

.dark .app-shell .table-row-button:hover,
.dark .app-shell .row-arrow:hover {
  background: color-mix(in oklab, var(--teal) 8%, var(--surface));
}

.dark .app-shell .chunk-row.active,
.dark .app-shell .chunk-row:hover {
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
}

@media (max-width: 47.5rem) {
  .page-content {
    gap: 0.75rem;
  }

  .page-content:has(> .agent-page) {
    gap: 0;
    padding: 0.625rem 0.625rem 0.5rem;
  }

  .page-content > .agent-workspace,
  .page-content > .asset-detail-layout,
  .page-content > .asset-table-panel,
  .page-content > .dashboard-grid,
  .page-content > .two-column-grid,
  .page-content > .project-grid,
  .page-content > .members-panel,
  .page-content > .action-board,
  .page-content > .evaluation-dashboard-grid,
  .page-content > .run-create-layout,
  .page-content > .playground-layout,
  .page-content > .research-workspace,
  .page-content > .reports-layout,
  .page-content > .settings-layout,
  .page-content > .queue-panel,
  .page-content > .notifications-page {
    flex-basis: 0;
  }
}
</style>
