import { computed, reactive, ref } from "vue";
import {
  applyMessageProgress,
  elapsedMs,
  finishMessageProgress,
  mergeEvent,
} from "@/utils/agentProgress";
import { agentApi } from "@/api/agent";
import { useWorkspace } from "@/composables/useWorkspace";
import { useAgentQueue } from "@/composables/useAgentQueue";
import type {
  AgentCitation,
  AgentAttachment,
  AgentContextMessage,
  AgentEvent,
  AgentMedia,
  AgentMessage,
  AgentRunMetrics,
  AgentRunConfig,
  AgentRunAccepted,
  AgentStreamEvent,
  AgentThreadSummary,
  ContextCompression,
  TokenUsage,
} from "@/api/types";

type AgentRunCallbacks = {
  onProgress?: (event: AgentStreamEvent) => void;
  onAccepted?: (runId: string | number) => void;
  onRunStarted?: (data?: AgentRunMetrics) => void;
  onEvent: (event: AgentEvent) => void;
  onThinking?: (messageId: string, delta: string) => void;
  onDelta: (messageId: string, delta: string) => void;
  onReplace: (messageId: string, content: string) => void;
  onCitation: (citation: AgentCitation) => void;
  onUsageUpdated?: (data?: AgentRunMetrics) => void;
  onMedia: (messageId: string, media: AgentMedia) => void;
  onArtifact?: (messageId: string, artifact: AgentAttachment) => void;
  onComplete: (messageId: string) => void;
  onRunCompleted?: (data?: AgentRunMetrics) => void;
  onError: (message: string) => void;
};

type AgentTransport = {
  run: (
    context: {
      workspaceId: number | string;
      projectId: number;
      threadId: string;
      messageId: string;
      content: string;
      attachments?: AgentAttachment[];
      config?: AgentRunConfig;
      contextMessages?: AgentContextMessage[];
      resume?: { runId: string; afterEventId?: string };
    },
    callbacks: AgentRunCallbacks,
  ) => Promise<AgentRunAccepted>;
};

type ThreadState = AgentThreadSummary & {
  persisted?: boolean;
  messages: AgentMessage[];
  events: AgentEvent[];
  eventHistory: AgentEvent[];
  citations: AgentCitation[];
  status: "idle" | "running" | "completed" | "failed";
  runId: string | null;
  queueTaskId?: string | null;
  contextUsage?: ContextCompression;
  tokenUsage?: TokenUsage;
  runStartedAt?: string;
  runFinishedAt?: string;
  runDurationMs?: number;
  draft: string;
  lastEventId?: string;
};

const threadStates = reactive<Record<string, ThreadState>>({});
const emptyThread: ThreadState = {
  id: "",
  title: "暂无对话",
  preview: "创建对话后开始提问",
  updatedAt: "",
  messageCount: 0,
  messages: [],
  events: [],
  eventHistory: [],
  citations: [],
  status: "idle",
  runId: null,
  contextUsage: undefined,
  tokenUsage: undefined,
  runStartedAt: undefined,
  runFinishedAt: undefined,
  runDurationMs: undefined,
  draft: "",
};
const threadOrder = ref<string[]>([]);
let historyKey = "";
const activeThreadId = ref<string | null>(null);
const orphanDraft = ref("");
const draft = computed<string>({
  get() {
    const threadId = activeThreadId.value;
    return threadId && threadStates[threadId]
      ? threadStates[threadId].draft
      : orphanDraft.value;
  },
  set(value) {
    const threadId = activeThreadId.value;
    if (threadId && threadStates[threadId]) {
      threadStates[threadId].draft = value;
    } else {
      orphanDraft.value = value;
    }
  },
});
const composerError = ref("");
const cancellingThreads = reactive(new Set<string>());
const threadRunTokens = new Map<string, number>();
const runControls = new Map<string, ActiveRunControl>();
type ActiveRunControl = {
  token: number;
  remoteRunId: string | null;
  cancelRequested: boolean;
  cancelPromise?: Promise<void>;
  accepted?: Promise<void>;
};

function cancelRemoteRun(
  control: ActiveRunControl,
  workspaceId: number | string,
  projectId: number,
) {
  if (!control.remoteRunId) return Promise.resolve();
  if (!control.cancelPromise) {
    control.cancelPromise = agentApi
      .cancelRun(workspaceId, projectId, control.remoteRunId)
      .then(() => undefined);
  }
  return control.cancelPromise;
}

function mergeTokenUsage(
  current: TokenUsage | undefined,
  incoming: TokenUsage | undefined,
) {
  if (!incoming) return current;
  if (!current) return { ...incoming };
  const currentAvailable = current.available !== false;
  const incomingAvailable = incoming.available !== false;
  return {
    inputTokens:
      Number(current.inputTokens || 0) + Number(incoming.inputTokens || 0),
    outputTokens:
      Number(current.outputTokens || 0) + Number(incoming.outputTokens || 0),
    totalTokens:
      Number(current.totalTokens || 0) + Number(incoming.totalTokens || 0),
    model: current.model || incoming.model,
    available: currentAvailable && incomingAvailable,
    estimated: Boolean(current.estimated || incoming.estimated),
  };
}

function summarizeThreadTitle(value: string) {
  let text = value.replace(/\s+/g, " ").trim();
  text = text.replace(/^(请问|请帮我|帮我|我想|想了解|能否|可以)\s*/, "");
  text = text.replace(/[。！？?!；;：:]+$/, "").trim();
  if (!text) return "新的问题整理";
  let summary = `整理：${text}`;
  if (/^为什么\s*.+/.test(text)) summary = `排查${text.slice(3).trim()}问题`;
  else if (/^(如何|怎么|怎样)\s*.+/.test(text))
    summary = `梳理${text.replace(/^(如何|怎么|怎样)\s*/, "")}方案`;
  else if (/^(什么是|是什么)\s*.+/.test(text))
    summary = `了解${text.replace(/^(什么是|是什么)\s*/, "")}`;
  else if (/^(总结|概括)\s*.+/.test(text))
    summary = `总结${text.replace(/^(总结|概括)\s*/, "")}`;
  else if (/^(比较|对比)\s*.+/.test(text))
    summary = `比较${text.replace(/^(比较|对比)\s*/, "")}`;
  return Array.from(summary).slice(0, 40).join("");
}

function createHttpTransport(): AgentTransport {
  return {
    async run(context, callbacks) {
      const accepted: AgentRunAccepted = context.resume
        ? {
            runId: context.resume.runId,
            messageId: context.messageId,
            status: "RUNNING",
            eventsUrl:
              agentApi.eventsUrl(
                context.workspaceId,
                context.projectId,
                context.resume.runId,
              ) +
              (context.resume.afterEventId
                ? `?afterId=${encodeURIComponent(context.resume.afterEventId)}`
                : ""),
          }
        : await agentApi.sendMessage(context.workspaceId, context.projectId, {
            threadId: context.threadId,
            messageId: context.messageId,
            content: context.content,
            ...(context.config || {}),
            attachments: context.attachments?.map(
              ({ url, previewUrl, file, ...attachment }) => attachment,
            ),
            contextMessages: context.contextMessages?.map(
              ({ attachments, ...message }) => ({
                ...message,
                attachments: attachments?.map(
                  ({ url, previewUrl, file, ...attachment }) => attachment,
                ),
              }),
            ),
          });
      callbacks.onAccepted?.(accepted.runId);
      const eventSource = new EventSource(
        accepted.eventsUrl ||
          agentApi.eventsUrl(
            context.workspaceId,
            context.projectId,
            accepted.runId,
          ),
        { withCredentials: true },
      );

      await new Promise<void>((resolve, reject) => {
        let settled = false;
        const seenEventIds = new Set<string>();
        let retryTimer: number | undefined;
        const clearRetryTimer = () => {
          if (retryTimer !== undefined) window.clearTimeout(retryTimer);
          retryTimer = undefined;
        };
        eventSource.onmessage = (message) => {
          const event = agentApi.parseEvent(message);
          if (!event) return;
          const eventId = String(event.eventId || message.lastEventId || "");
          if (eventId) {
            if (seenEventIds.has(eventId)) return;
            seenEventIds.add(eventId);
            // Bound memory for a long-lived/reconnecting stream.
            if (seenEventIds.size > 4096) {
              const oldest = seenEventIds.values().next().value;
              if (oldest) seenEventIds.delete(oldest);
            }
          }
          if (event.type === "run.completed" || event.type === "run.failed") {
            if (settled) return;
            settled = true;
            clearRetryTimer();
          } else if (settled) {
            // Do not allow a late delta from a recovered/duplicate worker to
            // mutate the already finalized assistant message.
            return;
          }
          callbacks.onProgress?.(event);
          handleStreamEvent(event, callbacks, resolve, reject, eventSource);
        };
        eventSource.onopen = clearRetryTimer;
        eventSource.onerror = () => {
          if (settled || retryTimer !== undefined) return;
          // EventSource 会自动重连；只有持续 15 秒无法恢复时才让当前运行失败。
          retryTimer = window.setTimeout(() => {
            eventSource.close();
            reject(new Error("Agent 事件流连接失败"));
          }, 15000);
        };
      });
      return accepted;
    },
  };
}

function handleStreamEvent(
  event: AgentStreamEvent,
  callbacks: AgentRunCallbacks,
  resolve: () => void,
  reject: (error: Error) => void,
  eventSource: EventSource,
) {
  if (event.type === "run.started") {
    callbacks.onRunStarted?.({
      ...(event.data || {}),
      startedAt: event.startedAt || event.data?.startedAt,
    });
  }
  if (event.type === "event.updated") callbacks.onEvent(event.event);
  // Private provider reasoning is never forwarded to presentation callbacks.
  if (event.type === "message.delta")
    callbacks.onDelta(event.messageId, event.delta);
  if (event.type === "message.replace")
    callbacks.onReplace(event.messageId, event.content);
  if (event.type === "citation.added") callbacks.onCitation(event.citation);
  if (event.type === "media.added")
    callbacks.onMedia(event.messageId, event.media);
  if (event.type === "artifact.added")
    callbacks.onArtifact?.(event.messageId, event.artifact);
  if (event.type === "message.completed") callbacks.onComplete(event.messageId);
  if (event.type === "usage.updated") {
    callbacks.onUsageUpdated?.({
      usage: event.usage,
      latencyMs: event.latencyMs,
      delta: event.delta,
    });
  }
  if (event.type === "run.completed") {
    callbacks.onRunCompleted?.({
      ...(event.data || {}),
      startedAt: event.startedAt || event.data?.startedAt,
      finishedAt: event.finishedAt || event.data?.finishedAt,
      durationMs: event.durationMs ?? event.data?.durationMs,
      usage: event.usage || event.data?.usage,
      contextCompression:
        event.contextCompression || event.data?.contextCompression,
      multiAgent: event.multiAgent || event.data?.multiAgent,
    });
    eventSource.close();
    resolve();
  }
  if (event.type === "run.failed") {
    eventSource.close();
    callbacks.onError(event.message);
    reject(new Error(event.message));
  }
}

const transport: AgentTransport = createHttpTransport();

export function useAgentWorkspace() {
  const { workspaceId, projectId } = useWorkspace();
  const { enqueueTask, updateTask, pauseTask } = useAgentQueue();
  const activeThread = computed(
    () =>
      (activeThreadId.value && threadStates[activeThreadId.value]) ||
      emptyThread,
  );
  const threads = computed(() =>
    threadOrder.value.map((id) => threadStates[id]!).filter(Boolean),
  );
  const messages = computed(() => activeThread.value.messages);
  const events = computed(() => activeThread.value.events);
  const citations = computed(() => activeThread.value.citations);
  const isRunning = computed(() => activeThread.value.status === "running");
  const hasRunningThread = computed(() =>
    threadOrder.value.some((id) => threadStates[id]?.status === "running"),
  );

  async function loadHistory() {
    if (projectId.value <= 0) return;
    const projectKey = `${workspaceId.value}/${projectId.value}`;
    if (historyKey === projectKey) return;
    historyKey = projectKey;
    threadOrder.value.splice(0);
    activeThreadId.value = null;
    orphanDraft.value = "";
    Object.keys(threadStates).forEach((id) => delete threadStates[id]);
    threadRunTokens.clear();
    runControls.clear();
    cancellingThreads.clear();
    try {
      const storedThreads = await agentApi.threads(
        workspaceId.value,
        projectId.value,
      );
      storedThreads.forEach((stored) => {
        threadStates[stored.id] = {
          ...stored,
          persisted: true,
          messages: stored.messages || [],
          events: stored.events || [],
          eventHistory: stored.eventHistory || stored.events || [],
          citations: stored.citations || [],
          status:
            stored.status === "failed"
              ? "failed"
              : stored.status === "running"
                ? "running"
                : stored.status === "idle"
                  ? "idle"
                  : "completed",
          runId: stored.runId || null,
          contextUsage: stored.contextUsage,
          tokenUsage: stored.tokenUsage,
          runStartedAt: stored.runStartedAt,
          runFinishedAt: stored.runFinishedAt,
          runDurationMs: stored.runDurationMs,
          // Execution metadata is restored on each message; drafts stay local.
          draft: "",
        };
        threadOrder.value.push(stored.id);
      });
      activeThreadId.value = threadOrder.value[0] || null;
      for (const id of threadOrder.value) {
        const thread = threadStates[id];
        if (thread?.status === "running" && thread.runId)
          void resumeThread(thread);
      }
    } catch {
      historyKey = "";
      // A failed history request may be retried on the next mount.
    }
  }

  async function resumeThread(thread: ThreadState) {
    const message = [...thread.messages]
      .reverse()
      .find((item) => item.role === "assistant" && item.status === "streaming");
    if (!message || !thread.runId) return;
    const token = (threadRunTokens.get(thread.id) || 0) + 1;
    threadRunTokens.set(thread.id, token);
    runControls.set(thread.id, {
      token,
      remoteRunId: thread.runId,
      cancelRequested: false,
    });
    const current = () => threadRunTokens.get(thread.id) === token;
    try {
      await transport.run(
        {
          workspaceId: workspaceId.value,
          projectId: projectId.value,
          threadId: thread.id,
          messageId: message.id,
          content: "",
          resume: {
            runId: thread.runId,
            afterEventId: message.lastEventId || thread.lastEventId,
          },
        },
        {
          onProgress: (event) => {
            if (!current()) return;
            applyMessageProgress(message, event);
            thread.lastEventId = event.eventId || thread.lastEventId;
            thread.runStartedAt = message.runStartedAt || thread.runStartedAt;
            thread.runFinishedAt = message.runFinishedAt;
            thread.runDurationMs = message.runDurationMs;
            if (event.type === "run.completed" || event.type === "run.failed")
              thread.events = message.events || [];
          },
          onEvent: (event) => {
            if (current()) {
              updateEvent(thread, event);
              rememberEvent(thread, event);
            }
          },
          onDelta: (id, delta) => {
            if (current() && id === message.id) message.content += delta;
          },
          onReplace: (id, content) => {
            if (current() && id === message.id) message.content = content;
          },
          onCitation: (citation) => {
            if (
              current() &&
              !message.citations?.some((item) => item.id === citation.id)
            ) {
              (message.citations ||= []).push(citation);
              thread.citations.push(citation);
            }
          },
          onMedia: (id, media) => {
            if (current() && id === message.id)
              (message.media ||= []).push(media);
          },
          onArtifact: (id, artifact) => {
            if (
              current() &&
              id === message.id &&
              !message.attachments?.some((item) => item.id === artifact.id)
            )
              (message.attachments ||= []).push(artifact);
          },
          onComplete: () => {
            if (current()) message.status = "completed";
          },
          onError: () => {},
          onRunCompleted: (data) => {
            if (current()) {
              thread.tokenUsage = data?.usage || thread.tokenUsage;
              thread.contextUsage =
                data?.contextCompression || thread.contextUsage;
            }
          },
        },
      );
      if (current()) {
        thread.status = "completed";
        message.status = "completed";
      }
    } catch (error) {
      if (current()) {
        thread.status = "failed";
        message.status = "failed";
        finishMessageProgress(message, "failed");
        thread.events = message.events || [];
        thread.runFinishedAt = message.runFinishedAt;
        thread.runDurationMs = message.runDurationMs;
        if (activeThreadId.value === thread.id)
          composerError.value = String(error);
      }
    } finally {
      if (current()) runControls.delete(thread.id);
    }
  }

  function selectThread(threadId: string) {
    if (threadStates[threadId]) activeThreadId.value = threadId;
    composerError.value = "";
  }

  async function deleteThread(threadId: string) {
    const thread = threadStates[threadId];
    if (!thread) return;
    if (thread.status === "running") {
      throw new Error("请先停止正在运行的 Agent 对话");
    }

    if (thread.persisted) {
      await agentApi.deleteThread(workspaceId.value, projectId.value, threadId);
    }

    const index = threadOrder.value.indexOf(threadId);
    const wasActive = activeThreadId.value === threadId;
    if (index >= 0) threadOrder.value.splice(index, 1);
    delete threadStates[threadId];
    threadRunTokens.delete(threadId);
    runControls.delete(threadId);
    cancellingThreads.delete(threadId);

    if (wasActive) {
      activeThreadId.value =
        threadOrder.value[index] || threadOrder.value[index - 1] || null;
      composerError.value = "";
    }
  }

  function createThread() {
    const id = `thread-${Date.now()}`;
    threadStates[id] = {
      id,
      title: "新建对话",
      preview: "等待输入第一个问题",
      updatedAt: new Date().toISOString(),
      messageCount: 0,
      messages: [],
      events: [],
      eventHistory: [],
      citations: [],
      status: "idle",
      runId: null,
      contextUsage: undefined,
      tokenUsage: undefined,
      runStartedAt: undefined,
      runFinishedAt: undefined,
      runDurationMs: undefined,
      draft: "",
      persisted: false,
    };
    threadOrder.value.unshift(id);
    activeThreadId.value = id;
    draft.value = "";
    composerError.value = "";
  }

  function updateEvent(thread: ThreadState, nextEvent: AgentEvent) {
    if (!nextEvent?.id) return;
    mergeEvent(thread.events, nextEvent, new Date().toISOString());
  }

  function rememberEvent(thread: ThreadState, nextEvent: AgentEvent) {
    if (!nextEvent?.id) return;
    const history = thread.eventHistory;
    const previous = history.at(-1);
    const sameAsPrevious =
      previous &&
      previous.id === nextEvent.id &&
      previous.status === nextEvent.status &&
      previous.detail === nextEvent.detail;
    if (!sameAsPrevious)
      history.push({
        ...nextEvent,
        meta: nextEvent.meta ? { ...nextEvent.meta } : undefined,
      });
  }

  async function sendMessage(
    value = draft.value,
    attachments: AgentAttachment[] = [],
    config?: AgentRunConfig,
  ) {
    const content = value.trim();
    if (!content) {
      composerError.value = "先输入你希望 Agent 处理的问题";
      return;
    }
    composerError.value = "";
    draft.value = "";
    if (!activeThreadId.value) createThread();
    const thread = activeThread.value;
    if (thread.status === "running") {
      composerError.value = "当前对话正在运行，请切换到其他对话或等待完成";
      return;
    }
    const messageId = `message-${Date.now()}`;
    const createdAt = new Date().toISOString();
    // Stream callbacks must mutate the proxy so each display frame invalidates
    // the rendered Markdown, even when no other run events arrive.
    const assistantMessage = reactive<AgentMessage>({
      id: messageId,
      role: "assistant",
      content: "",
      modelName: config?.modelName || "Shinkou Agent",
      createdAt,
      status: "streaming",
      citations: [],
      media: [],
      thinking: "",
      runStartedAt: createdAt,
      events: [],
      agentTasks: [],
    });
    const contextMessages: AgentContextMessage[] = thread.messages
      .filter(
        (message) => message.content.trim() || message.attachments?.length,
      )
      .map((message) => ({
        role: message.role,
        content:
          message.content.trim() || "上一轮消息包含附件，请结合附件继续回答。",
        attachments: message.attachments?.map((item) => ({ ...item })),
      }))
      .slice(-40);
    thread.messages.push({
      id: `${messageId}-user`,
      role: "user",
      content,
      createdAt,
      status: "completed",
      attachments: attachments.length
        ? attachments.map((item) => ({ ...item }))
        : undefined,
    });
    thread.messages.push(assistantMessage);
    if (
      !thread.messages.some(
        (message) =>
          message.role === "user" &&
          message.id !== `${messageId}-user` &&
          message.content.trim(),
      )
    ) {
      thread.title = summarizeThreadTitle(content);
    }
    thread.preview = content;
    thread.updatedAt = createdAt;
    thread.messageCount = thread.messages.length;
    thread.events.splice(0);
    thread.eventHistory.splice(0);
    thread.citations.splice(0);
    thread.status = "running";
    // Only a backend-issued run ID is safe to send to the cancel endpoint.
    thread.runId = null;
    thread.runStartedAt = createdAt;
    thread.runFinishedAt = undefined;
    thread.runDurationMs = undefined;
    const queueTask = enqueueTask({
      title: content.slice(0, 80),
      source: "agent-chat",
      threadId: thread.id,
      priority: "normal",
    });
    thread.queueTaskId = queueTask.id;
    updateTask(queueTask.id, {
      status: "running",
      currentStep: "等待 Agent 开始规划",
    });
    const token = (threadRunTokens.get(thread.id) || 0) + 1;
    threadRunTokens.set(thread.id, token);
    let resolveAccepted!: () => void;
    const runControl: ActiveRunControl = {
      token,
      remoteRunId: null,
      cancelRequested: false,
      accepted: new Promise<void>((resolve) => {
        resolveAccepted = resolve;
      }),
    };
    runControls.set(thread.id, runControl);
    const isCurrentRun = () => threadRunTokens.get(thread.id) === token;
    const contextChars = contextMessages.reduce(
      (total, message) => total + message.content.length,
      content.length,
    );
    thread.contextUsage = {
      originalChars: contextChars,
      finalChars: contextChars,
      originalTokenEstimate: Math.ceil(contextChars / 4),
      finalTokenEstimate: Math.ceil(contextChars / 4),
      finalMessageCount: contextMessages.length + 1,
    };
    thread.tokenUsage = undefined;
    // Render streamed text once per animation frame instead of once per
    // character. This keeps Markdown parsing and Vue updates smooth.
    const displayBatchSize = 96;
    let pendingDelta = "";
    let streamEnded = false;
    let displayFrame: number | undefined;
    let displayDoneSettled = false;
    let resolveDisplayDone!: () => void;
    const displayDone = new Promise<void>((resolve) => {
      resolveDisplayDone = resolve;
    });
    const settleDisplay = () => {
      if (displayDoneSettled) return;
      displayDoneSettled = true;
      assistantMessage.status = "completed";
      updateTask(queueTask.id, {
        status: "completed",
        progress: 100,
        currentStep: "任务已完成",
        time: "刚刚完成",
      });
      resolveDisplayDone();
    };
    const abortDisplay = () => {
      if (displayFrame !== undefined) window.cancelAnimationFrame(displayFrame);
      displayFrame = undefined;
      pendingDelta = "";
      streamEnded = true;
      if (!displayDoneSettled) {
        displayDoneSettled = true;
        resolveDisplayDone();
      }
    };
    const scheduleDisplay = () => {
      if (displayFrame !== undefined) return;
      displayFrame = window.requestAnimationFrame(pumpDisplay);
    };
    const pumpDisplay = () => {
      displayFrame = undefined;
      if (!isCurrentRun()) {
        abortDisplay();
        return;
      }
      if (!pendingDelta) {
        if (streamEnded) settleDisplay();
        return;
      }
      const pendingCharacters = Array.from(pendingDelta);
      const visibleCharacters = pendingCharacters.slice(0, displayBatchSize);
      pendingDelta = pendingCharacters.slice(displayBatchSize).join("");
      assistantMessage.content += visibleCharacters.join("");
      if (pendingDelta) {
        scheduleDisplay();
      } else if (streamEnded) {
        settleDisplay();
      }
    };
    const enqueueDelta = (delta: string) => {
      pendingDelta += delta;
      scheduleDisplay();
    };
    const endDisplay = () => {
      streamEnded = true;
      if (displayFrame === undefined) pumpDisplay();
    };

    try {
      const accepted = await transport.run(
        {
          workspaceId: workspaceId.value,
          projectId: projectId.value,
          threadId: thread.id,
          messageId,
          content,
          attachments,
          config,
          contextMessages,
        },
        {
          onProgress: (event) => {
            if (!isCurrentRun()) return;
            applyMessageProgress(assistantMessage, event);
            thread.lastEventId = event.eventId || thread.lastEventId;
            if (event.type === "run.completed" || event.type === "run.failed")
              thread.events = assistantMessage.events || [];
          },
          onAccepted: (acceptedRunId) => {
            thread.persisted = true;
            runControl.remoteRunId = String(acceptedRunId);
            resolveAccepted();
            if (isCurrentRun()) {
              thread.runId = String(acceptedRunId);
            }
          },
          onRunStarted: (data) => {
            if (!isCurrentRun()) return;
            thread.runStartedAt = data?.startedAt || thread.runStartedAt;
            thread.runFinishedAt = undefined;
            thread.runDurationMs = undefined;
          },
          onEvent: (event) => {
            if (isCurrentRun()) {
              rememberEvent(thread, event);
              updateEvent(thread, event);
              const completed = thread.events.filter(
                (item) => item.status === "completed",
              ).length;
              updateTask(queueTask.id, {
                status: event.status === "failed" ? "failed" : "running",
                progress: Math.round(
                  (completed / Math.max(thread.events.length, 1)) * 100,
                ),
                currentStep: event.title,
              });
            }
          },
          onDelta: (id, delta) => {
            if (!isCurrentRun() || id !== messageId) return;
            enqueueDelta(delta);
          },
          onReplace: (id, content) => {
            if (!isCurrentRun() || id !== messageId) return;
            pendingDelta = "";
            assistantMessage.content = content;
          },
          onCitation: (citation) => {
            if (!isCurrentRun() || !citation?.id) return;
            if (!thread.citations.some((item) => item.id === citation.id)) {
              thread.citations.push(citation);
              assistantMessage.citations?.push(citation);
            }
          },
          onUsageUpdated: (data) => {
            if (!isCurrentRun() || !data?.usage) return;
            thread.tokenUsage = mergeTokenUsage(thread.tokenUsage, data.usage);
          },
          onMedia: (id, media) => {
            if (!isCurrentRun() || id !== messageId || !media?.id || !media.url)
              return;
            assistantMessage.media?.push(media);
          },
          onArtifact: (id, artifact) => {
            if (
              !isCurrentRun() ||
              id !== messageId ||
              !artifact?.id ||
              !artifact.url
            )
              return;
            if (
              !assistantMessage.attachments?.some(
                (item) => item.id === artifact.id,
              )
            ) {
              assistantMessage.attachments = [
                ...(assistantMessage.attachments || []),
                artifact,
              ];
            }
          },
          onComplete: (id) => {
            if (!isCurrentRun() || id !== messageId) return;
            endDisplay();
          },
          onRunCompleted: (data) => {
            if (isCurrentRun()) {
              if (data?.contextCompression)
                thread.contextUsage = data.contextCompression;
              if (data?.usage) thread.tokenUsage = data.usage;
              if (data?.startedAt) thread.runStartedAt = data.startedAt;
              if (data?.finishedAt) thread.runFinishedAt = data.finishedAt;
              if (data?.durationMs != null)
                thread.runDurationMs = data.durationMs;
            }
          },
          onError: (message) => {
            if (!isCurrentRun()) return;
            if (activeThreadId.value === thread.id)
              composerError.value = message;
            updateTask(queueTask.id, {
              status: "failed",
              currentStep: "运行失败，需要重试",
              errorMessage: message,
            });
          },
        },
      );
      if (isCurrentRun()) {
        thread.runId = String(accepted.runId);
      }
      endDisplay();
      await displayDone;
      if (isCurrentRun()) {
        thread.status = "completed";
        thread.runFinishedAt =
          assistantMessage.runFinishedAt || new Date().toISOString();
        thread.runDurationMs =
          assistantMessage.runDurationMs ??
          elapsedMs(thread.runStartedAt, thread.runFinishedAt, Date.now());
      }
    } catch (error) {
      resolveAccepted();
      abortDisplay();
      if (isCurrentRun()) {
        thread.status = "failed";
        finishMessageProgress(assistantMessage, "failed");
        thread.events = assistantMessage.events || [];
        thread.runFinishedAt = assistantMessage.runFinishedAt;
        thread.runDurationMs = assistantMessage.runDurationMs;
        updateTask(queueTask.id, {
          status: "failed",
          currentStep: "运行失败，需要重试",
          errorMessage:
            error instanceof Error ? error.message : "Agent 运行失败",
        });
        assistantMessage.status = "failed";
        assistantMessage.content =
          assistantMessage.content ||
          "这次运行没有完成，请检查 Agent 接口或稍后重试。";
        if (activeThreadId.value === thread.id) {
          composerError.value =
            error instanceof Error ? error.message : "Agent 运行失败";
        }
      }
    }
    if (runControls.get(thread.id) === runControl && isCurrentRun()) {
      runControls.delete(thread.id);
    }
  }

  async function stopRun() {
    if (!isRunning.value) return;
    const thread = activeThread.value;
    if (cancellingThreads.has(thread.id)) return;
    cancellingThreads.add(thread.id);
    const control = runControls.get(thread.id);
    const currentToken = threadRunTokens.get(thread.id) || 0;
    const cancelWorkspaceId = workspaceId.value;
    const cancelProjectId = projectId.value;
    try {
      if (control && control.token === currentToken) {
        control.cancelRequested = true;
        await control.accepted;
        await cancelRemoteRun(control, cancelWorkspaceId, cancelProjectId);
      } else if (thread.runId) {
        await agentApi.cancelRun(
          cancelWorkspaceId,
          cancelProjectId,
          thread.runId,
        );
      }
    } catch (error) {
      if (control) {
        control.cancelRequested = false;
        control.cancelPromise = undefined;
      }
      if (activeThreadId.value === thread.id)
        composerError.value =
          error instanceof Error ? error.message : "暂停失败，请重试";
      return;
    } finally {
      cancellingThreads.delete(thread.id);
    }
    // SSE may already have delivered the terminal snapshot while the cancel
    // request was in flight. Never overwrite that authoritative final state.
    if (
      threadRunTokens.get(thread.id) !== currentToken ||
      thread.status !== "running"
    )
      return;
    threadRunTokens.set(thread.id, currentToken + 1);
    runControls.delete(thread.id);
    thread.status = "completed";
    thread.runFinishedAt = new Date().toISOString();
    thread.runDurationMs = elapsedMs(
      thread.runStartedAt,
      thread.runFinishedAt,
      Date.now(),
    );
    if (thread.queueTaskId) pauseTask(thread.queueTaskId);
    const stoppedMessage = thread.messages.at(-1);
    if (
      stoppedMessage?.role === "assistant" &&
      stoppedMessage.status === "streaming"
    ) {
      finishMessageProgress(stoppedMessage, "cancelled", thread.runFinishedAt);
      thread.events = stoppedMessage.events || [];
      stoppedMessage.status = "completed";
      stoppedMessage.content += "\n\n已由你暂停本次运行。";
    }
    cancellingThreads.delete(thread.id);
    return;
  }

  return {
    activeThread,
    threads,
    activeThreadId,
    messages,
    events,
    eventHistory: computed(() => activeThread.value.eventHistory),
    citations,
    draft,
    composerError,
    isRunning,
    hasRunningThread,
    cancelling: computed(() =>
      Boolean(
        activeThreadId.value && cancellingThreads.has(activeThreadId.value),
      ),
    ),
    selectThread,
    deleteThread,
    createThread,
    sendMessage,
    stopRun,
    loadHistory,
  };
}
