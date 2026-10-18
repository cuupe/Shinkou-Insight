<script setup lang="ts">
import { computed, ref } from "vue";
import { ChevronDown, GitBranch, LoaderCircle, Sparkles } from "@lucide/vue";
import type { AgentMessage, AgentEventStatus, AgentExecutionError } from "@/api/types";
import {
  currentMessageActivity,
  elapsedMs,
  messageElapsed,
} from "@/utils/agentProgress";

const props = defineProps<{ message: AgentMessage; now: number }>();
const expanded = ref(false);
const tasks = computed(() => props.message.agentTasks || []);
const decisions = computed(() => props.message.decisions || []);
const latestDecision = computed(() => decisions.value.at(-1));
const failure = computed(() => props.message.executionError);
const children = computed(() => tasks.value.filter((task) => task.parentId));
const live = computed(() => props.message.status === "streaming");
const visible = computed(
  () =>
    live.value ||
    props.message.thinkingStartedAt ||
    props.message.events?.length ||
    failure.value ||
    decisions.value.length ||
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
        : "决策与执行记录",
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
    blocked: "已阻止",
    reused: "已复用",
    empty: "无结果",
  }[value];
}
function eventError(meta: Record<string, unknown> | undefined) {
  const error = meta?.error;
  return error && typeof error === "object" ? error as AgentExecutionError : undefined;
}
</script>

<template>
  <section v-if="visible" class="answer-progress" aria-label="决策与执行过程">
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
    <p v-if="latestDecision" class="decision-preview" data-testid="decision-summary">{{ latestDecision.summary }}</p>
    <aside v-if="failure" class="execution-error" role="alert">
      <strong>{{ failure.code === "ANSWER_VALIDATION" ? "答案校验未通过" : "本轮执行未完成" }}</strong>
      <p>{{ failure.remedy }}</p>
      <details>
        <summary>查看失败原因</summary>
        <p>{{ failure.message }}</p>
        <span>{{ failure.stage }} · {{ failure.code }}</span>
      </details>
    </aside>
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
      <div v-if="decisions.length" class="decision-list" aria-label="模型决策说明">
        <article v-for="decision in decisions" :key="decision.id" class="decision-card">
          <header><strong>第 {{ decision.sequence }} 轮决策</strong><span>剩余工具预算 {{ decision.remainingToolCalls }}</span></header>
          <p class="decision-goal">{{ decision.resolvedGoal }}</p>
          <p>{{ decision.summary }}</p>
          <p
            v-if="decision.rationale?.trim() && decision.rationale.trim() !== decision.summary?.trim()"
            class="decision-rationale"
          >{{ decision.rationale }}</p>
          <ul v-if="decision.needs.length" class="evidence-needs">
            <li v-for="need in decision.needs" :key="need.id" :class="need.status">
              <span>{{ { covered: "已覆盖", missing: "待补充", unavailable: "无法核实" }[need.status] }}</span>
              <div>{{ need.description }}<small v-if="need.basis">{{ { general:'稳定常识或创作', material:'给定材料', world:'现实状态核验', derived:'派生计算', context:'用户或系统上下文' }[need.basis] }}</small><small v-if="need.evidenceIds?.length">依据 {{ need.evidenceIds.join('、') }}</small></div>
            </li>
          </ul>
          <p v-for="(tool, index) in decision.tools" :key="index" class="decision-tool">{{ tool.tool }}：{{ tool.purpose }}</p>
          <details v-if="decision.assessments?.length"><summary>资料相关性判断</summary><p v-for="item in decision.assessments" :key="item.evidenceId">{{ item.evidenceId }} · {{ item.relevant ? '采用' : '排除' }}：{{ item.reason }}</p></details>
          <p v-if="decision.stopReason" class="fallback-note">执行已收束：{{ { budget: '达到预算', no_progress: '检索没有新增证据', answer_support: '回答需要修正证据支持', clarification: '等待确认必要条件' }[decision.stopReason as 'budget' | 'no_progress' | 'answer_support' | 'clarification'] || decision.stopReason }}</p>
        </article>
      </div>
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
            <aside v-if="eventError(event.meta)" class="execution-error">
              <span>{{ eventError(event.meta)?.stage }} · {{ eventError(event.meta)?.code }}</span>
              <p>{{ eventError(event.meta)?.remedy }}</p>
            </aside>
          </div>
        </li>
      </ol>
      <details v-if="message.thinkingStartedAt" class="provider-thinking">
        <summary>
          模型响应阶段
          <span v-if="reasoningElapsed">{{ duration(reasoningElapsed) }}</span>
        </summary>
        <div>此项记录响应耗时。模型的公开决策说明显示在上方。</div>
      </details>
      <p
        v-if="!tasks.length && !message.events?.length && !message.thinkingStartedAt && !decisions.length"
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
.decision-preview { margin: 0; padding: 0 0.75rem 0.75rem; color: var(--workspace-text); line-height: 1.7; overflow-wrap: anywhere; }
.decision-card { margin-bottom: 0.75rem; padding: 0.75rem; border: 1px solid var(--workspace-border); border-radius: 0.375rem; }
.decision-card header { display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: space-between; }
.decision-card header strong { color: var(--teal-dark); }
.decision-card p { margin: 0.5rem 0; white-space: pre-wrap; line-height: 1.7; overflow-wrap: anywhere; }
.decision-goal, .decision-rationale { color: var(--workspace-text); }
.evidence-needs { list-style: none; margin: 0.75rem 0; padding: 0; }
.evidence-needs li { display: flex; gap: 0.625rem; margin: 0.375rem 0; line-height: 1.6; }
.evidence-needs li > span { flex-shrink: 0; min-width: 3rem; }
.evidence-needs small { display: block; }
.covered > span { color: var(--teal-dark); }
.missing > span, .unavailable > span, .blocked, .empty { color: #d3a464; }
.execution-error { margin: 0.5rem 0.75rem 0.75rem; padding: 0.625rem; border-left: 2px solid #dc8585; background: rgba(220, 133, 133, 0.07); line-height: 1.6; color: #dc8585; }
.execution-error > span { display: block; font-size: 0.6875rem; }
.execution-error p { margin: 0.375rem 0 0; }
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
