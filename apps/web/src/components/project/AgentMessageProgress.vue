<script setup lang="ts">
import { computed, ref } from "vue";
import { ChevronDown, GitBranch, LoaderCircle, Sparkles } from "@lucide/vue";
import type { AgentMessage, AgentEventStatus } from "@/api/types";
import {
  currentMessageActivity,
  elapsedMs,
  messageElapsed,
} from "@/utils/agentProgress";

const props = defineProps<{ message: AgentMessage; now: number }>();
const expanded = ref(false);
const tasks = computed(() => props.message.agentTasks || []);
const children = computed(() => tasks.value.filter((task) => task.parentId));
const live = computed(() => props.message.status === "streaming");
const visible = computed(
  () =>
    live.value ||
    props.message.thinkingStartedAt ||
    props.message.events?.length ||
    tasks.value.length,
);
const completedCount = computed(
  () => children.value.filter((task) => task.status === "completed").length,
);
const failedCount = computed(
  () => children.value.filter((task) => task.status === "failed").length,
);
const activity = computed(() =>
  live.value
    ? currentMessageActivity(props.message)
    : props.message.runStatus?.toLowerCase() === "cancelled"
      ? "已停止"
      : props.message.status === "failed"
        ? "执行失败"
        : "思考与执行记录",
);
const elapsed = computed(() => messageElapsed(props.message, props.now));
const reasoningElapsed = computed(
  () =>
    (props.message.thinkingDurationMs || 0) +
    (props.message.thinkingStartedAt &&
    !props.message.thinkingFinishedAt &&
    live.value
      ? elapsedMs(props.message.thinkingStartedAt, undefined, props.now) || 0
      : 0),
);
function duration(value: number | undefined) {
  if (value == null) return "";
  const seconds = Math.floor(value / 1000);
  return `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}
function status(value: AgentEventStatus) {
  return {
    pending: "等待",
    running: "执行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已停止",
  }[value];
}
</script>

<template>
  <section v-if="visible" class="answer-progress" aria-label="思考与执行过程">
    <button
      class="progress-toggle"
      type="button"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <LoaderCircle v-if="live" :size="14" class="progress-spinner" />
      <Sparkles v-else :size="14" />
      <span class="progress-activity">{{ activity }}</span>
      <span
        v-if="elapsed != null"
        class="progress-time"
        data-testid="message-elapsed"
        >{{ live ? "已用时" : "用时" }} {{ duration(elapsed) }}</span
      >
      <ChevronDown :size="14" :class="{ expanded }" />
    </button>
    <div v-if="tasks.length" class="delegation-summary">
      <GitBranch :size="13" />
      <span>主智能体 → {{ children.length }} 个子任务</span>
      <span>{{ completedCount }}/{{ children.length }} 完成</span>
      <span v-if="failedCount" class="failed">{{ failedCount }} 失败</span>
    </div>
    <p v-if="message.multiAgent?.fallback" class="fallback-note">
      {{ message.multiAgent.reason }}
    </p>
    <div v-show="expanded" class="progress-details">
      <div
        v-if="tasks.length"
        class="agent-task-tree"
        aria-label="主从智能体任务树"
      >
        <article
          v-for="task in tasks"
          :key="task.id"
          class="agent-task"
          :class="[task.status, { child: task.parentId }]"
          :data-task-id="task.id"
        >
          <div class="task-title">
            <i /><strong>{{ task.title }}</strong
            ><span>{{ status(task.status) }}</span>
            <time v-if="task.startedAt">{{
              duration(
                task.durationMs ??
                  elapsedMs(task.startedAt, task.completedAt, now),
              )
            }}</time>
          </div>
          <p class="task-objective">{{ task.objective }}</p>
          <p v-if="task.error" class="failed">{{ task.error }}</p>
          <p v-else-if="task.summary" class="task-result">{{ task.summary }}</p>
        </article>
      </div>
      <ol
        v-if="message.events?.length"
        class="execution-steps"
        aria-label="实际执行步骤"
      >
        <li
          v-for="event in message.events"
          :key="event.id"
          :class="event.status"
        >
          <span>{{ status(event.status) }}</span>
          <div>
            <strong>{{ event.title }}</strong>
            <p v-if="event.detail">{{ event.detail }}</p>
          </div>
        </li>
      </ol>
      <details v-if="message.thinkingStartedAt" class="provider-thinking">
        <summary>
          模型思考
          <span v-if="reasoningElapsed">{{ duration(reasoningElapsed) }}</span>
        </summary>
        <div>{{ message.thinkingFinishedAt ? "模型思考阶段已结束。" : "模型仍在思考，正在等待最终回答。" }}</div>
      </details>
      <p
        v-if="!tasks.length && !message.events?.length && !message.thinkingStartedAt"
        class="waiting-note"
      >
        等待服务返回执行状态。
      </p>
    </div>
  </section>
</template>

<style scoped>
.answer-progress {
  margin-bottom: 0.625rem;
  border: 1px solid var(--workspace-border);
  border-radius: 0.5rem;
  overflow: hidden;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.progress-toggle {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem;
  background: transparent;
  border: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.progress-toggle:hover {
  background: var(--agent-accent-surface-soft);
}
.progress-toggle > svg {
  flex-shrink: 0;
  color: var(--teal-dark);
}
.progress-activity {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--workspace-text);
}
.progress-time,
time {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  font-size: 0.6875rem;
}
.expanded {
  transform: rotate(180deg);
}
.progress-spinner {
  animation: spin 1.4s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.delegation-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.75rem 0.625rem;
  font-size: 0.6875rem;
}
.delegation-summary svg {
  color: var(--teal-dark);
}
.progress-details {
  max-height: 28rem;
  overflow-y: auto;
  padding: 0.75rem;
  border-top: 1px solid var(--workspace-border);
}
.agent-task {
  padding: 0.5rem 0;
}
.agent-task.child {
  margin-left: 0.375rem;
  padding-left: 1rem;
  border-left: 1px solid var(--workspace-border);
}
.task-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.task-title strong {
  color: var(--workspace-text);
  font-weight: 600;
  flex: 1;
}
.task-title > i {
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: var(--workspace-muted);
}
.running .task-title > i,
.completed .task-title > i {
  background: var(--teal-dark);
}
.task-objective,
.task-result,
.agent-task > p {
  margin: 0.375rem 0 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.6;
}
.task-result {
  color: var(--workspace-text);
}
.failed,
.failed .task-title > span {
  color: #dc8585;
}
.fallback-note {
  margin: 0;
  padding: 0 0.75rem 0.625rem;
  color: #d3a464;
}
.execution-steps {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0;
}
.execution-steps li {
  display: flex;
  gap: 0.625rem;
  padding: 0.375rem 0;
}
.execution-steps li > span {
  flex-shrink: 0;
  min-width: 2.5rem;
  font-size: 0.6875rem;
}
.execution-steps strong {
  color: var(--workspace-text);
  font-weight: 500;
}
.execution-steps p {
  margin: 0.25rem 0 0;
  line-height: 1.6;
}
.provider-thinking {
  border-top: 1px solid var(--workspace-border);
  margin-top: 0.5rem;
  padding-top: 0.5rem;
}
.provider-thinking summary {
  cursor: pointer;
}
.provider-thinking summary span {
  margin-left: 0.5rem;
}
.provider-thinking > div {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.7;
  padding-top: 0.5rem;
}
.waiting-note {
  margin: 0;
}
@media (prefers-reduced-motion: reduce) {
  .progress-spinner {
    animation: none;
  }
}
</style>
