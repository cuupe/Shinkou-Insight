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
