import { computed, reactive, ref } from "vue";
import { agentApi } from "@/api/agent";
import { useWorkspace } from "@/composables/useWorkspace";
import { useAgentQueue } from "@/composables/useAgentQueue";
import type {
  AgentCitation,
  AgentAttachment,
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
  onAccepted?: (runId: string | number) => void;
  onRunStarted?: (data?: AgentRunMetrics) => void;
  onEvent: (event: AgentEvent) => void;
  onDelta: (messageId: string, delta: string) => void;
  onReplace: (messageId: string, content: string) => void;
  onCitation: (citation: AgentCitation) => void;
  onUsageUpdated?: (data?: AgentRunMetrics) => void;
  onMedia: (messageId: string, media: AgentMedia) => void;
  onComplete: (messageId: string) => void;
  onRunCompleted?: (data?: AgentRunMetrics) => void;
  onError: (message: string) => void;
};

type AgentTransport = {
  run: (context: {
    workspaceId: number | string;
    projectId: number;
    threadId: string;
    messageId: string;
    content: string;
    attachments?: AgentAttachment[];
    config?: AgentRunConfig;
    contextMessages?: Array<{ role: "user" | "assistant"; content: string }>;
  }, callbacks: AgentRunCallbacks) => Promise<AgentRunAccepted>;
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
};
const threadOrder = ref<string[]>([]);
const activeThreadId = ref<string | null>(null);
const draft = ref("");
const composerError = ref("");
const cancelling = ref(false);
let activeRunToken = 0;

function mergeTokenUsage(current: TokenUsage | undefined, incoming: TokenUsage | undefined) {
  if (!incoming) return current;
  if (!current) return { ...incoming };
  const currentAvailable = current.available !== false;
  const incomingAvailable = incoming.available !== false;
  return {
    inputTokens: Number(current.inputTokens || 0) + Number(incoming.inputTokens || 0),
    outputTokens: Number(current.outputTokens || 0) + Number(incoming.outputTokens || 0),
    totalTokens: Number(current.totalTokens || 0) + Number(incoming.totalTokens || 0),
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
  else if (/^(如何|怎么|怎样)\s*.+/.test(text)) summary = `梳理${text.replace(/^(如何|怎么|怎样)\s*/, "")}方案`;
  else if (/^(什么是|是什么)\s*.+/.test(text)) summary = `了解${text.replace(/^(什么是|是什么)\s*/, "")}`;
  else if (/^(总结|概括)\s*.+/.test(text)) summary = `总结${text.replace(/^(总结|概括)\s*/, "")}`;
  else if (/^(比较|对比)\s*.+/.test(text)) summary = `比较${text.replace(/^(比较|对比)\s*/, "")}`;
  return Array.from(summary).slice(0, 40).join("");
}

function createHttpTransport(): AgentTransport {
  return {
    async run(context, callbacks) {
      const accepted = await agentApi.sendMessage(context.workspaceId, context.projectId, {
        threadId: context.threadId,
        messageId: context.messageId,
        content: context.content,
        ...(context.config || {}),
        attachments: context.attachments?.map(({ url, previewUrl, file, ...attachment }) => attachment),
        contextMessages: context.contextMessages,
      });
      callbacks.onAccepted?.(accepted.runId);
      const eventSource = new EventSource(
        accepted.eventsUrl || agentApi.eventsUrl(context.workspaceId, context.projectId, accepted.runId),
        { withCredentials: true },
      );

      await new Promise<void>((resolve, reject) => {
        let settled = false;
        let retryTimer: number | undefined;
        const clearRetryTimer = () => {
          if (retryTimer !== undefined) window.clearTimeout(retryTimer);
          retryTimer = undefined;
        };
        eventSource.onmessage = (message) => {
          const event = agentApi.parseEvent(message);
          if (!event) return;
          if (event.type === "run.completed" || event.type === "run.failed") {
            settled = true;
            clearRetryTimer();
          }
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
  if (event.type === "message.delta") callbacks.onDelta(event.messageId, event.delta);
  if (event.type === "message.replace") callbacks.onReplace(event.messageId, event.content);
  if (event.type === "citation.added") callbacks.onCitation(event.citation);
  if (event.type === "media.added") callbacks.onMedia(event.messageId, event.media);
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
      contextCompression: event.contextCompression || event.data?.contextCompression,
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
  let historyKey = "";

  async function loadHistory() {
    if (projectId.value <= 0) return;
    const projectKey = `${workspaceId.value}/${projectId.value}`;
    if (historyKey === projectKey) return;
    historyKey = projectKey;
    threadOrder.value.splice(0);
    activeThreadId.value = null;
    Object.keys(threadStates).forEach((id) => delete threadStates[id]);
    try {
      const storedThreads = await agentApi.threads(workspaceId.value, projectId.value);
      storedThreads.forEach((stored) => {
      threadStates[stored.id] = {
        ...stored,
        persisted: true,
        messages: stored.messages || [],
        events: stored.events || [],
        eventHistory: stored.eventHistory || stored.events || [],
        citations: stored.citations || [],
        status: stored.status === "failed" ? "failed" : stored.status === "running" ? "running" : stored.status === "idle" ? "idle" : "completed",
        runId: stored.runId || null,
        contextUsage: stored.contextUsage,
        tokenUsage: stored.tokenUsage,
        runStartedAt: stored.runStartedAt,
        runFinishedAt: stored.runFinishedAt,
        runDurationMs: stored.runDurationMs,
      };
        threadOrder.value.push(stored.id);
      });
      activeThreadId.value = threadOrder.value[0] || null;
    } catch {
      // History is optional for a new project; the empty state remains truthful.
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

    if (wasActive) {
      activeThreadId.value = threadOrder.value[index] || threadOrder.value[index - 1] || null;
      draft.value = "";
      composerError.value = "";
    }
  }

  function createThread() {
    if (isRunning.value) return;
    const id = `thread-${Date.now()}`;
    threadStates[id] = {
      id,
      title: "新建对话",
      preview: "等待输入第一个问题",
      updatedAt: "刚刚",
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
      persisted: false,
    };
    threadOrder.value.unshift(id);
    activeThreadId.value = id;
    draft.value = "";
    composerError.value = "";
  }

  function updateEvent(nextEvent: AgentEvent) {
    if (!nextEvent?.id) return;
    const current = activeThread.value.events;
    const index = current.findIndex((event) => event.id === nextEvent.id);
    if (index >= 0) current[index] = nextEvent;
    else current.push(nextEvent);
  }

  function rememberEvent(nextEvent: AgentEvent) {
    if (!nextEvent?.id) return;
    const history = activeThread.value.eventHistory;
    const previous = history.at(-1);
    const sameAsPrevious = previous && previous.id === nextEvent.id && previous.status === nextEvent.status && previous.detail === nextEvent.detail;
    if (!sameAsPrevious) history.push({ ...nextEvent, meta: nextEvent.meta ? { ...nextEvent.meta } : undefined });
  }

  async function sendMessage(value = draft.value, attachments: AgentAttachment[] = [], config?: AgentRunConfig) {
    const content = value.trim();
    if (!content) {
      composerError.value = "先输入你希望 Agent 处理的问题";
      return;
    }
    if (hasRunningThread.value) {
      composerError.value = "已有对话正在运行，请先暂停后再发送新消息";
      return;
    }
    composerError.value = "";
    draft.value = "";
    if (!activeThreadId.value) createThread();
    const thread = activeThread.value;
    const messageId = `message-${Date.now()}`;
    const runId = `agent-run-${Date.now()}`;
    const assistantMessage: AgentMessage = {
      id: messageId,
      role: "assistant",
      content: "",
      createdAt: "刚刚",
      status: "streaming",
      citations: [],
      media: [],
    };
    const contextMessages = thread.messages
      .filter((message) => message.content.trim())
      .map((message) => ({ role: message.role, content: message.content }))
      .slice(-40);
    thread.messages.push({
      id: `${messageId}-user`,
      role: "user",
      content,
      createdAt: "刚刚",
      status: "completed",
      attachments: attachments.length ? attachments.map((item) => ({ ...item })) : undefined,
    });
    thread.messages.push(assistantMessage);
    if (!thread.messages.some((message) => message.role === "user" && message.id !== `${messageId}-user` && message.content.trim())) {
      thread.title = summarizeThreadTitle(content);
    }
    thread.preview = content;
    thread.updatedAt = "刚刚";
    thread.messageCount = thread.messages.length;
    thread.events.splice(0);
    thread.eventHistory.splice(0);
    thread.citations.splice(0);
    thread.status = "running";
    thread.runId = runId;
    thread.runStartedAt = undefined;
    thread.runFinishedAt = undefined;
    thread.runDurationMs = undefined;
    const queueTask = enqueueTask({
      title: content.slice(0, 80),
      source: "agent-chat",
      threadId: thread.id,
      priority: "normal",
    });
    thread.queueTaskId = queueTask.id;
    updateTask(queueTask.id, { status: "running", currentStep: "等待 Agent 开始规划" });
    const token = ++activeRunToken;
    const contextChars = contextMessages.reduce((total, message) => total + message.content.length, content.length);
    thread.contextUsage = {
      originalChars: contextChars,
      finalChars: contextChars,
      originalTokenEstimate: Math.ceil(contextChars / 4),
      finalTokenEstimate: Math.ceil(contextChars / 4),
      finalMessageCount: contextMessages.length + 1,
    };
    thread.tokenUsage = undefined;
    const typewriterInterval = 14;
    let pendingDelta = "";
    let streamEnded = false;
    let displayTimer: number | undefined;
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
      if (displayTimer !== undefined) window.clearTimeout(displayTimer);
      displayTimer = undefined;
      pendingDelta = "";
      streamEnded = true;
      if (!displayDoneSettled) {
        displayDoneSettled = true;
        resolveDisplayDone();
      }
    };
    const pumpDisplay = () => {
      displayTimer = undefined;
      if (token !== activeRunToken) {
        abortDisplay();
        return;
      }
      if (!pendingDelta) {
        if (streamEnded) settleDisplay();
        return;
      }
      const nextCharacter = Array.from(pendingDelta)[0] || "";
      pendingDelta = pendingDelta.slice(nextCharacter.length);
      assistantMessage.content += nextCharacter;
      if (pendingDelta) {
        displayTimer = window.setTimeout(pumpDisplay, typewriterInterval);
      } else if (streamEnded) {
        settleDisplay();
      }
    };
    const enqueueDelta = (delta: string) => {
      pendingDelta += delta;
      if (displayTimer === undefined) pumpDisplay();
    };
    const endDisplay = () => {
      streamEnded = true;
      if (displayTimer === undefined) pumpDisplay();
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
          onAccepted: (acceptedRunId) => {
            thread.persisted = true;
            if (token === activeRunToken) thread.runId = String(acceptedRunId);
          },
          onRunStarted: (data) => {
            if (token !== activeRunToken) return;
            thread.runStartedAt = data?.startedAt;
            thread.runFinishedAt = undefined;
            thread.runDurationMs = undefined;
          },
          onEvent: (event) => {
            if (token === activeRunToken) {
              rememberEvent(event);
              updateEvent(event);
              const completed = thread.events.filter((item) => item.status === "completed").length;
              updateTask(queueTask.id, {
                status: event.status === "failed" ? "failed" : "running",
                progress: Math.round((completed / Math.max(thread.events.length, 1)) * 100),
                currentStep: event.title,
              });
            }
          },
          onDelta: (id, delta) => {
            if (token !== activeRunToken || id !== messageId) return;
            enqueueDelta(delta);
          },
          onReplace: (id, content) => {
            if (token !== activeRunToken || id !== messageId) return;
            pendingDelta = "";
            assistantMessage.content = content;
          },
          onCitation: (citation) => {
            if (token !== activeRunToken || !citation?.id) return;
            if (!thread.citations.some((item) => item.id === citation.id)) {
              thread.citations.push(citation);
              assistantMessage.citations?.push(citation);
            }
          },
          onUsageUpdated: (data) => {
            if (token !== activeRunToken || !data?.usage) return;
            thread.tokenUsage = mergeTokenUsage(thread.tokenUsage, data.usage);
          },
          onMedia: (id, media) => {
            if (token !== activeRunToken || id !== messageId || !media?.id || !media.url) return;
            assistantMessage.media?.push(media);
          },
          onComplete: (id) => {
            if (token !== activeRunToken || id !== messageId) return;
            endDisplay();
          },
          onRunCompleted: (data) => {
            if (token === activeRunToken) {
              if (data?.contextCompression) thread.contextUsage = data.contextCompression;
              if (data?.usage) thread.tokenUsage = data.usage;
              if (data?.startedAt) thread.runStartedAt = data.startedAt;
              if (data?.finishedAt) thread.runFinishedAt = data.finishedAt;
              if (data?.durationMs != null) thread.runDurationMs = data.durationMs;
            }
          },
          onError: (message) => {
            composerError.value = message;
            updateTask(queueTask.id, {
              status: "failed",
              currentStep: "运行失败，需要重试",
              errorMessage: message,
            });
          },
        },
      );
      if (token === activeRunToken) {
        thread.runId = String(accepted.runId);
      }
      endDisplay();
      await displayDone;
      if (token === activeRunToken) thread.status = "completed";
    } catch (error) {
      abortDisplay();
      if (token === activeRunToken) {
        thread.status = "failed";
        updateTask(queueTask.id, {
          status: "failed",
          currentStep: "运行失败，需要重试",
          errorMessage: error instanceof Error ? error.message : "Agent 运行失败",
        });
        assistantMessage.status = "failed";
        assistantMessage.content = assistantMessage.content || "这次运行没有完成，请检查 Agent 接口或稍后重试。";
        composerError.value = error instanceof Error ? error.message : "Agent 运行失败";
      }
    }
  }

  async function stopRun() {
    if (!isRunning.value) return;
    cancelling.value = true;
    if (activeThread.value.runId) {
      try {
        await agentApi.cancelRun(workspaceId.value, projectId.value, activeThread.value.runId);
      } catch (error) {
        cancelling.value = false;
        composerError.value = error instanceof Error ? error.message : "Agent 运行取消失败";
        return;
      }
    }
    activeRunToken += 1;
    activeThread.value.status = "completed";
    if (activeThread.value.queueTaskId) pauseTask(activeThread.value.queueTaskId);
    const message = activeThread.value.messages.at(-1);
    if (message?.role === "assistant" && message.status === "streaming") {
      message.status = "completed";
      message.content += "\n\n已由你暂停本次运行。";
    }
    window.setTimeout(() => {
      cancelling.value = false;
    }, 250);
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
    cancelling,
    selectThread,
    deleteThread,
    createThread,
    sendMessage,
    stopRun,
    loadHistory,
  };
}
