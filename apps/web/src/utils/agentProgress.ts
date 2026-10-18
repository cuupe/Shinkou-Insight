import type { AgentEvent, AgentMessage, AgentStreamEvent } from "../api/types";

export function elapsedMs(
  start: string | undefined,
  end: string | undefined,
  now: number,
) {
  if (!start) return undefined;
  const first = Date.parse(start);
  const last = end ? Date.parse(end) : now;
  return Number.isFinite(first) && Number.isFinite(last)
    ? Math.max(0, last - first)
    : undefined;
}

export function messageElapsed(message: AgentMessage, now: number) {
  if (message.runDurationMs != null) return message.runDurationMs;
  if (message.status !== "streaming" && !message.runFinishedAt)
    return undefined;
  return elapsedMs(message.runStartedAt, message.runFinishedAt, now);
}

/** Keep runtime errors in the message's error card, not in the composer. */
export function recordMessageFailure(message: AgentMessage, error: unknown) {
  message.status = "failed";
  message.executionError ||= {
    code: "RUN_FAILED",
    stage: "execution",
    message: error instanceof Error ? error.message : String(error || "Agent 运行失败"),
    remedy: "查看执行记录中的具体原因后重试",
    retryable: true,
  };
  finishMessageProgress(message, "failed");
}

/** Legacy backend replies may contain the same serialized error as metadata.
 * Remove only that exact error text; preserve any earlier answer content.
 */
export function visibleAnswerContent(message: AgentMessage) {
  const content = message.content || "";
  const failure = message.executionError?.message;
  if (message.role !== "assistant" || !failure) return content;
  if (content.trim() === failure.trim()) return "";
  const suffix = "\n\n运行失败：" + failure;
  return content.endsWith(suffix) ? content.slice(0, -suffix.length) : content;
}

export function conversationStatusLabel(messages: AgentMessage[], running: boolean) {
  if (running) return "Agent 正在工作";
  const latest = messages.filter(message => message.role === "assistant").at(-1);
  if (latest?.status === "failed") return "上次运行未完成";
  if (latest?.decisions?.at(-1)?.action === "clarify") return "待你确认条件";
  return "对话已就绪";
}

function finishThinking(
  message: AgentMessage,
  timestamp: string,
  duration?: number,
) {
  if (!message.thinkingStartedAt || message.thinkingFinishedAt) return;
  message.thinkingFinishedAt = timestamp;
  message.thinkingDurationMs =
    (message.thinkingDurationMs || 0) +
    (duration ??
      elapsedMs(message.thinkingStartedAt, timestamp, Date.now()) ??
      0);
  message.thinkingSeconds = Math.floor(message.thinkingDurationMs / 1000);
}

export function currentMessageActivity(message: AgentMessage) {
  const runningTasks = (message.agentTasks || []).filter(
    (task) => task.parentId && task.status === "running",
  );
  if (runningTasks.length)
    return runningTasks.length > 1
      ? `${runningTasks.length} 个子智能体正在执行`
      : runningTasks[0]!.title;
  const event = [...(message.events || [])]
    .reverse()
    .find((item) => item.status === "running");
  if (event) return event.title;
  if (message.thinkingStartedAt && !message.thinkingFinishedAt)
    return "正在思考";
  return message.content ? "正在生成回答" : "等待智能体响应";
}

export function mergeEvent(
  events: AgentEvent[],
  next: AgentEvent,
  timestamp: string,
) {
  const index = events.findIndex((item) => item.id === next.id);
  const previous = events[index];
  const merged = {
    ...previous,
    ...next,
    startedAt: next.startedAt || previous?.startedAt || timestamp,
    ...(next.status !== "running" && next.status !== "pending"
      ? { completedAt: next.completedAt || timestamp }
      : {}),
  };
  if (index < 0) events.push(merged);
  else events[index] = merged;
}

export function finishMessageProgress(
  message: AgentMessage,
  status: string,
  now = new Date().toISOString(),
) {
  message.runStatus = status;
  message.runFinishedAt ||= now;
  message.runDurationMs ??= elapsedMs(
    message.runStartedAt,
    message.runFinishedAt,
    Date.now(),
  );
  finishThinking(message, now);
  for (const item of [
    ...(message.events || []),
    ...(message.agentTasks || []),
  ]) {
    if (item.status === "running" || item.status === "pending") {
      item.status = status === "failed" ? "failed" : "cancelled";
      item.completedAt ||= now;
    }
  }
}

/** Execution metadata is independent of animation batching and the selected chat. */
export function applyMessageProgress(
  message: AgentMessage,
  event: AgentStreamEvent,
) {
  const timestamp = event.timestamp || new Date().toISOString();
  message.runId = event.runId;
  if (event.eventId) message.lastEventId = event.eventId;
  switch (event.type) {
    case "run.started":
      message.runStartedAt =
        event.startedAt ||
        event.data?.startedAt ||
        message.runStartedAt ||
        timestamp;
      break;
    case "event.updated":
      mergeEvent((message.events ||= []), event.event, timestamp);
      break;
    case "decision.updated": {
      const decisions = (message.decisions ||= []);
      const index = decisions.findIndex((decision) => decision.id === event.decision.id);
      if (index < 0) decisions.push(event.decision);
      else decisions[index] = event.decision;
      break;
    }
    case "agent.task.updated": {
      const tasks = (message.agentTasks ||= []);
      const index = tasks.findIndex((task) => task.id === event.task.id);
      if (index < 0) tasks.push(event.task);
      else tasks[index] = { ...tasks[index], ...event.task };
      break;
    }
    case "thinking.started":
      message.thinkingStartedAt = event.startedAt || timestamp;
      message.thinkingFinishedAt = undefined;
      break;
    case "thinking.delta":
      message.thinkingStartedAt ||= timestamp;
      // Legacy events provide activity only; private text is not displayed.
      break;
    case "thinking.completed":
      finishThinking(message, event.finishedAt || timestamp, event.durationMs);
      break;
    case "message.delta":
    case "message.replace":
      if (
        (event.type === "message.delta" ? event.delta : event.content).length
      ) {
        message.answerStartedAt ||= timestamp;
        finishThinking(message, timestamp);
      }
      break;
    case "run.completed":
    case "run.failed": {
      const metrics =
        event.type === "run.completed" ? { ...event.data, ...event } : event;
      message.runStartedAt = metrics.startedAt || message.runStartedAt;
      message.runFinishedAt = metrics.finishedAt || timestamp;
      message.runDurationMs =
        metrics.durationMs ??
        elapsedMs(message.runStartedAt, message.runFinishedAt, Date.now());
      if (event.type === "run.completed")
        message.multiAgent = event.multiAgent || event.data?.multiAgent;
      if (event.type === "run.failed") message.executionError = event.error || {
        code: "RUN_FAILED", stage: "execution", message: event.message || "Agent 运行失败",
        remedy: "查看执行记录中的具体原因后重试", retryable: true,
      };
      else message.decisionMetrics = event.decisionMetrics;
      finishMessageProgress(
        message,
        event.type === "run.failed"
          ? "failed"
          : event.status?.toLowerCase() || "completed",
        timestamp,
      );
      break;
    }
  }
}
