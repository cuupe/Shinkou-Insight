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
  AgentRunAccepted,
  AgentStreamEvent,
  AgentThreadSummary,
} from "@/api/types";

type AgentRunCallbacks = {
  onEvent: (event: AgentEvent) => void;
  onDelta: (messageId: string, delta: string) => void;
  onCitation: (citation: AgentCitation) => void;
  onMedia: (messageId: string, media: AgentMedia) => void;
  onComplete: (messageId: string) => void;
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
  }, callbacks: AgentRunCallbacks) => Promise<AgentRunAccepted>;
};

type ThreadState = AgentThreadSummary & {
  messages: AgentMessage[];
  events: AgentEvent[];
  citations: AgentCitation[];
  status: "idle" | "running" | "completed" | "failed";
  runId: string | null;
  queueTaskId?: string | null;
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
  citations: [],
  status: "idle",
  runId: null,
};
const threadOrder = ref<string[]>([]);
const activeThreadId = ref<string | null>(null);
const draft = ref("");
const composerError = ref("");
const cancelling = ref(false);
let activeRunToken = 0;

function createHttpTransport(): AgentTransport {
  return {
    async run(context, callbacks) {
      const accepted = await agentApi.sendMessage(context.workspaceId, context.projectId, {
        threadId: context.threadId,
        messageId: context.messageId,
        content: context.content,
        attachments: context.attachments?.map(({ url, previewUrl, file, ...attachment }) => attachment),
      });
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
  if (event.type === "event.updated") callbacks.onEvent(event.event);
  if (event.type === "message.delta") callbacks.onDelta(event.messageId, event.delta);
  if (event.type === "citation.added") callbacks.onCitation(event.citation);
  if (event.type === "media.added") callbacks.onMedia(event.messageId, event.media);
  if (event.type === "message.completed") callbacks.onComplete(event.messageId);
  if (event.type === "run.completed") {
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

  function selectThread(threadId: string) {
    if (isRunning.value) return;
    if (threadStates[threadId]) activeThreadId.value = threadId;
    composerError.value = "";
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
      citations: [],
      status: "idle",
      runId: null,
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

  async function sendMessage(value = draft.value, attachments: AgentAttachment[] = []) {
    const content = value.trim();
    if (!content || isRunning.value) {
      if (!content) composerError.value = "先输入你希望 Agent 处理的问题";
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
    thread.messages.push({
      id: `${messageId}-user`,
      role: "user",
      content,
      createdAt: "刚刚",
      status: "completed",
      attachments: attachments.length ? attachments.map((item) => ({ ...item })) : undefined,
    });
    thread.messages.push(assistantMessage);
    thread.title = content.slice(0, 24);
    thread.preview = content;
    thread.updatedAt = "刚刚";
    thread.messageCount = thread.messages.length;
    thread.events.splice(0);
    thread.citations.splice(0);
    thread.status = "running";
    thread.runId = runId;
    const queueTask = enqueueTask({
      title: content.slice(0, 80),
      source: "agent-chat",
      threadId: thread.id,
      priority: "normal",
    });
    thread.queueTaskId = queueTask.id;
    updateTask(queueTask.id, { status: "running", currentStep: "等待 Agent 开始规划" });
    const token = ++activeRunToken;

    try {
      const accepted = await transport.run(
        {
          workspaceId: workspaceId.value,
          projectId: projectId.value,
          threadId: thread.id,
          messageId,
          content,
          attachments,
        },
        {
          onEvent: (event) => {
            if (token === activeRunToken) {
              updateEvent(event);
              const completed = thread.events.filter((item) => item.status === "completed").length;
              updateTask(queueTask.id, {
                status: event.status === "failed" ? "failed" : "running",
                progress: Math.round((completed / 4) * 100),
                currentStep: event.title,
              });
            }
          },
          onDelta: (id, delta) => {
            if (token !== activeRunToken || id !== messageId) return;
            assistantMessage.content += delta;
          },
          onCitation: (citation) => {
            if (token !== activeRunToken || !citation?.id) return;
            if (!thread.citations.some((item) => item.id === citation.id)) {
              thread.citations.push(citation);
              assistantMessage.citations?.push(citation);
            }
          },
          onMedia: (id, media) => {
            if (token !== activeRunToken || id !== messageId || !media?.id || !media.url) return;
            assistantMessage.media?.push(media);
          },
          onComplete: (id) => {
            if (id !== messageId) return;
            assistantMessage.status = "completed";
            updateTask(queueTask.id, {
              status: "completed",
              progress: 100,
              currentStep: "任务已完成",
              time: "刚刚完成",
            });
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
      if (token === activeRunToken) thread.status = "completed";
    } catch (error) {
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

  function stopRun() {
    if (!isRunning.value) return;
    cancelling.value = true;
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
    citations,
    draft,
    composerError,
    isRunning,
    cancelling,
    selectThread,
    createThread,
    sendMessage,
    stopRun,
  };
}
