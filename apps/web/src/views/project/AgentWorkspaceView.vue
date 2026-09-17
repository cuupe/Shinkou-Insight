<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
} from "vue";
import {
  AlertCircle,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronRight,
  Circle,
  Clock3,
  Cpu,
  Database,
  Download,
  FileCheck2,
  FileSearch,
  FileSpreadsheet,
  FileText,
  Image,
  Music2,
  Paperclip,
  Presentation,
  Link2,
  ListChecks,
  MessageCircle,
  Plus,
  Search,
  Send,
  Settings2,
  Sparkles,
  Square,
  Trash2,
  Video,
  Wrench,
  X,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { agentApi } from "@/api/agent";
import { getApiErrorMessage } from "@/api/core";
import { assetsApi } from "@/api/assets";
import {
  settingsApi,
  type ProjectModelConfig,
  type WebSearchConfig,
} from "@/api/settings";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAgentWorkspace } from "@/composables/useAgentWorkspace";
import type {
  AgentAttachment,
  AgentAttachmentKind,
  AgentEvent,
  AgentEventKind,
  AgentMessage,
  AgentThreadSummary,
} from "@/api/types";
import { useWorkspace } from "@/composables/useWorkspace";

const { notify, router, routeTo, workspaceId, projectId, allowWeb } =
  useWorkspace();
const {
  activeThread,
  threads,
  messages,
  events,
  eventHistory,
  citations,
  draft,
  composerError,
  isRunning,
  hasRunningThread,
  cancelling,
  selectThread,
  deleteThread,
  createThread,
  loadHistory,
  sendMessage,
  stopRun,
} = useAgentWorkspace();
const projectAssetCount = ref(0);
const canSubmitMessage = computed(
  () => Boolean(draft.value.trim() || pendingAttachments.value.length) && !hasRunningThread.value,
);
const contextLoading = ref(false);
const conversationScroll = ref<HTMLElement | null>(null);
const attachmentInput = ref<HTMLInputElement | null>(null);
const pendingAttachments = ref<AgentAttachment[]>([]);
const processReviewOpen = ref(false);
const deleteOpen = ref(false);
const deletingThread = ref<AgentThreadSummary | null>(null);
const deleting = ref(false);
const modelOptions = ref<ProjectModelConfig[]>([]);
const webSearchConfig = ref<WebSearchConfig | null>(null);
const selectedModelId = ref<number | string>("");
const multiAgentMode = ref<"AUTO" | "ON" | "OFF">("AUTO");
type ChatGenerationForm = {
  strategy: "AUTO" | "REACT" | "PLAN_AND_SOLVE" | "REFLECTION";
  retrievalTopK: number;
  maxTokens: number;
  temperature: number;
  topP: number;
  topK: number | null;
  frequencyPenalty: number;
  thinkingEnabled: boolean;
  reasoningEffort: "low" | "medium" | "high";
};
const generationOpen = ref(false);
const reflectionEnabled = ref(true);
const generation = reactive<ChatGenerationForm>({
  strategy: "AUTO",
  retrievalTopK: 1,
  maxTokens: 4096,
  temperature: 0.3,
  topP: 0.9,
  topK: null,
  frequencyPenalty: 0,
  thinkingEnabled: false,
  reasoningEffort: "high",
});
const savingCitationIds = reactive(new Set<string>());
const savedCitationAssets = reactive<Record<string, string>>({});
const webSearchReady = computed(() =>
  Boolean(
    webSearchConfig.value?.enabled && webSearchConfig.value?.hasCredential,
  ),
);
const agentConfig = computed(() => ({
  allowWebSearch: allowWeb.value && webSearchReady.value,
  reflectionEnabled: reflectionEnabled.value,
  strategy: generation.strategy,
  multiAgentMode: multiAgentMode.value,
  maxResearchRounds: 3,
  topK: generation.retrievalTopK,
  retrievalMode: "HYBRID" as const,
  useReranker: true,
  outputLanguage: "zh-CN",
  temperature: generation.temperature,
  topP: generation.topP,
  modelTopK: generation.topK,
  maxTokens: generation.maxTokens,
  frequencyPenalty: generation.frequencyPenalty,
  reasoningEffort: generation.thinkingEnabled
    ? generation.reasoningEffort
    : ("none" as const),
  ...(selectedModelId.value ? { modelConfigId: selectedModelId.value } : {}),
}));
const completedEvents = computed(
  () => events.value.filter((event) => event.status === "completed").length,
);
const progress = computed(() =>
  events.value.length
    ? Math.round((completedEvents.value / events.value.length) * 100)
    : 0,
);
const currentEvent = computed(() => {
  for (let index = events.value.length - 1; index >= 0; index -= 1) {
    if (events.value[index]?.status === "running") return events.value[index];
  }
  return events.value.at(-1);
});
const activityNow = ref(Date.now());
const activityStartedAt = ref<number | null>(null);
let activityTimer: number | undefined;
let activityKey = "";

function formatElapsed(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function activityDetail(event: AgentEvent | undefined) {
  if (event?.detail) return event.detail;
  if (event?.kind === "tool") return "正在调用工具并等待返回结果";
  if (event?.kind === "search") return "正在读取项目资料并整理可用信息";
  if (event?.kind === "synthesis") return "正在结合上下文与证据生成回答";
  if (event?.kind === "reflection") return "正在检查回答是否有遗漏或无依据内容";
  return "正在准备下一步操作";
}

function nextActivityLabel(event: AgentEvent | undefined) {
  if (!event) return "接收 Agent 事件";
  if (event.kind === "search" || event.kind === "tool")
    return "整理证据并生成回答";
  if (event.kind === "evidence") return "结合证据生成回答";
  if (event.kind === "synthesis")
    return reflectionEnabled.value ? "判断是否需要自检" : "发送回答";
  if (event.kind === "reflection") return "完成并发送回答";
  return "继续执行 Agent 流程";
}

const activityElapsed = computed(() => {
  if (!isRunning.value || activityStartedAt.value == null) return 0;
  return Math.max(0, activityNow.value - activityStartedAt.value);
});

const runElapsed = computed(() => {
  if (activeThread.value.runDurationMs != null)
    return activeThread.value.runDurationMs;
  if (!activeThread.value.runStartedAt || !isRunning.value) return null;
  const startedAt = Date.parse(activeThread.value.runStartedAt);
  return Number.isFinite(startedAt)
    ? Math.max(0, activityNow.value - startedAt)
    : null;
});

function formatProcessingTime(milliseconds: number | null) {
  if (milliseconds == null) return "等待服务计时";
  if (milliseconds < 1_000) return milliseconds + " ms";
  const totalSeconds = Math.floor(milliseconds / 1_000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes
    ? minutes + "分 " + seconds.toString().padStart(2, "0") + "秒"
    : seconds + "." + Math.floor((milliseconds % 1_000) / 100) + "秒";
}

const runElapsedLabel = computed(() =>
  activeThread.value.status === "idle"
    ? "暂无"
    : formatProcessingTime(runElapsed.value),
);
const runTimingSource = computed(() => {
  if (activeThread.value.status === "idle") return "尚未运行";
  return activeThread.value.runStartedAt ? "AI 服务真实计时" : "等待服务确认";
});

function formatRealToken(value: number | undefined) {
  if (!tokenUsage.value || tokenUsage.value.available === false) return "暂无";
  return formatTokenCount(value);
}

const tokenUsageStatus = computed(() => {
  if (tokenUsage.value?.available === false) return "提供方未返回 usage";
  if (tokenUsage.value) return "模型提供方 usage";
  return isRunning.value ? "等待模型返回 usage" : "暂无真实 usage";
});

watch(
  () =>
    `${isRunning.value}:${currentEvent.value?.id || "pending"}:${currentEvent.value?.status || "pending"}:${currentEvent.value?.detail || ""}`,
  (key) => {
    if (!isRunning.value) {
      activityKey = "";
      activityStartedAt.value = null;
      return;
    }
    if (key !== activityKey) {
      activityKey = key;
      activityStartedAt.value = Date.now();
      activityNow.value = Date.now();
    }
  },
  { immediate: true },
);

watch(
  isRunning,
  (running) => {
    if (activityTimer !== undefined) window.clearInterval(activityTimer);
    activityTimer = undefined;
    if (running) {
      activityNow.value = Date.now();
      activityTimer = window.setInterval(() => {
        activityNow.value = Date.now();
      }, 500);
    }
  },
  { immediate: true },
);

onUnmounted(() => {
  if (activityTimer !== undefined) window.clearInterval(activityTimer);
});
const contextUsage = computed(() => activeThread.value.contextUsage);
const tokenUsage = computed(() => activeThread.value.tokenUsage);
const contextSourceCount = computed(
  () => projectAssetCount.value + sourceCitations.value.length,
);
const processEvents = computed(() =>
  eventHistory.value.length ? eventHistory.value : events.value,
);

function formatTokenCount(value: number | undefined) {
  return value == null ? "暂无" : value.toLocaleString("zh-CN");
}

async function loadContextSources() {
  if (projectId.value <= 0) return;
  contextLoading.value = true;
  try {
    projectAssetCount.value = (
      await assetsApi.list(workspaceId.value, projectId.value)
    ).length;
  } catch {
    projectAssetCount.value = 0;
  } finally {
    contextLoading.value = false;
  }
}

const activeModel = computed(
  () =>
    modelOptions.value.find(
      (model) => String(model.id) === String(selectedModelId.value),
    ) || modelOptions.value[0],
);

function modelConfig(model: ProjectModelConfig | undefined) {
  if (!model?.config) return {} as Record<string, unknown>;
  try {
    return JSON.parse(model.config) as Record<string, unknown>;
  } catch {
    return {} as Record<string, unknown>;
  }
}

function applyModelGenerationDefaults() {
  const config = modelConfig(activeModel.value);
  const reasoning = String(config.reasoningEffort || "none");
  Object.assign(generation, {
    maxTokens: Number(config.maxTokens ?? 4096),
    temperature: Number(config.temperature ?? 0.3),
    topP: Number(config.topP ?? 0.9),
    topK: config.topK == null ? null : Number(config.topK),
    frequencyPenalty: Number(config.frequencyPenalty ?? 0),
    thinkingEnabled: reasoning !== "none",
    reasoningEffort: ["low", "medium", "high"].includes(reasoning)
      ? (reasoning as ChatGenerationForm["reasoningEffort"])
      : "high",
  });
}

async function loadModelOptions() {
  if (projectId.value <= 0) {
    modelOptions.value = [];
    return;
  }
  try {
    modelOptions.value = (
      await settingsApi.models.list(workspaceId.value, projectId.value)
    ).filter((model) => model.enabled);
    // Empty means the backend applies the project default, including the
    // project creator's credential precedence.
    selectedModelId.value = "";
    applyModelGenerationDefaults();
  } catch {
    notify("模型配置加载失败，将使用服务默认配置");
  }
}

async function loadWebSearchConfig() {
  if (projectId.value <= 0) {
    webSearchConfig.value = null;
    allowWeb.value = false;
    return;
  }
  try {
    webSearchConfig.value = await settingsApi.webSearch.get(
      workspaceId.value,
      projectId.value,
    );
    if (!webSearchReady.value) allowWeb.value = false;
  } catch {
    webSearchConfig.value = null;
    allowWeb.value = false;
  }
}

onMounted(loadModelOptions);
onMounted(loadWebSearchConfig);
onMounted(loadContextSources);
onMounted(loadHistory);
watch(projectId, (next, previous) => {
  if (next !== previous) {
    void loadModelOptions();
    void loadWebSearchConfig();
    void loadContextSources();
    void loadHistory();
  }
});

const eventIcons = {
  chat: MessageCircle,
  plan: ListChecks,
  search: Search,
  tool: Wrench,
  file: FileText,
  evidence: FileCheck2,
  synthesis: Sparkles,
  reflection: CheckCircle2,
  multi_agent: Bot,
};

function eventIcon(kind: AgentEventKind) {
  return eventIcons[kind] || ListChecks;
}

type MessageCitation = NonNullable<AgentMessage["citations"]>[number];
type MessageSegment = { text: string; citation?: MessageCitation };

function citationForMarker(message: AgentMessage, marker: string) {
  const citationsForMessage = message.citations || [];
  const normalizedMarker = marker.trim().toLowerCase();
  const direct = citationsForMessage.find(
    (citation) => citation.id.toLowerCase() === normalizedMarker,
  );
  if (direct) return direct;
  if (/^\d+$/.test(normalizedMarker))
    return citationsForMessage[Number(normalizedMarker) - 1];
  return undefined;
}

function citationSourceKey(citation: MessageCitation) {
  if (citation.url) return `web:${citation.url.trim().toLowerCase()}`;
  if (citation.assetId != null) return `asset:${String(citation.assetId)}`;
  const source = (citation.source || citation.title || "").replace(
    /\s*[·•|]\s*第\s*\d+\s*页\s*$/i,
    "",
  );
  return `${citation.sourceType || "internal"}:${source.trim().toLowerCase()}`;
}

function uniqueCitations(citationsForDisplay: MessageCitation[]) {
  const seen = new Set<string>();
  return citationsForDisplay.filter((citation) => {
    const key = citationSourceKey(citation);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function messageCitations(message: AgentMessage) {
  const citationsForMessage = message.citations || [];
  if (!citationsForMessage.length || !message.content) return [];
  const referenced: MessageCitation[] = [];
  const markerPattern = /(?:\[([^\]\r\n]{1,100})\]|【([^】\r\n]{1,100})】)/g;
  let match: RegExpExecArray | null;
  while ((match = markerPattern.exec(message.content))) {
    const citation = citationForMarker(message, match[1] || match[2] || "");
    if (citation && !referenced.some((item) => item.id === citation.id)) {
      referenced.push(citation);
    }
  }
  return uniqueCitations(referenced);
}

function messageParagraphs(message: AgentMessage): MessageSegment[][] {
  const markerPattern = /(?:\[([^\]\r\n]{1,100})\]|【([^】\r\n]{1,100})】)/g;
  const parsed = message.content
    .split(/\n+/)
    .filter(Boolean)
    .map((line) => {
      const segments: MessageSegment[] = [];
      const renderedSources = new Set<string>();
      let cursor = 0;
      let match: RegExpExecArray | null;
      while ((match = markerPattern.exec(line))) {
        const citation = citationForMarker(message, match[1] || match[2] || "");
        if (!citation) continue;
        if (match.index > cursor)
          segments.push({ text: line.slice(cursor, match.index) });
        const sourceKey = citationSourceKey(citation);
        if (!renderedSources.has(sourceKey)) {
          segments.push({ text: match[0], citation });
          renderedSources.add(sourceKey);
        }
        cursor = match.index + match[0].length;
      }
      markerPattern.lastIndex = 0;
      if (cursor < line.length) segments.push({ text: line.slice(cursor) });
      return segments.length ? segments : [{ text: line }];
    });

  const citations = message.citations || [];
  if (!citations.length || !parsed.length) return parsed;

  const citationSegments = parsed.map((paragraph) =>
    paragraph.filter((segment) => Boolean(segment.citation)),
  );
  const explicitCitations = citationSegments.flatMap((segments) =>
    segments.flatMap((segment) => (segment.citation ? [segment.citation] : [])),
  );
  const lastIndex = parsed.length - 1;
  const lastCitationCount = citationSegments[lastIndex]?.length || 0;
  const lastText = (parsed[lastIndex] || [])
    .filter((segment) => !segment.citation)
    .map((segment) => segment.text)
    .join("")
    .trim();
  const trailingLabel =
    /^(参考|引用|来源|参考资料|参考来源|sources?|references?|citations?)(?:列表|如下)?[：:\s]*$/i.test(
      lastText,
    );
  const trailingCitationList =
    parsed.length > 1 &&
    explicitCitations.length >= 2 &&
    lastCitationCount === explicitCitations.length &&
    (trailingLabel || !lastText);
  if (trailingCitationList) {
    parsed.pop();
    citationSegments.pop();
    explicitCitations.splice(0, explicitCitations.length);
  }

  return parsed;
}

function citationNumber(message: AgentMessage, citation: MessageCitation) {
  const visible = messageCitations(message);
  const sourceKey = citationSourceKey(citation);
  return visible.findIndex((item) => citationSourceKey(item) === sourceKey) + 1;
}

function inspectorCitationNumber(citation: MessageCitation) {
  return (
    sourceCitations.value.findIndex(
      (item) => citationSourceKey(item) === citationSourceKey(citation),
    ) + 1
  );
}

const sourceCitations = computed(() => uniqueCitations(citations.value));

function citationTitle(citation: MessageCitation) {
  return citation.title || citation.source || "引用来源";
}

function eventStatusLabel(event: AgentEvent) {
  if (event.status === "running") return "进行中";
  if (event.status === "failed") return "失败";
  if (event.status === "completed" && event.meta?.skipped) return "已跳过";
  if (event.status === "completed") return event.duration || "已完成";
  return "等待中";
}

function eventTimeLabel(event: AgentEvent) {
  return event.completedAt || event.startedAt || event.duration || "等待中";
}

const attachmentIcons = {
  image: Image,
  video: Video,
  audio: Music2,
  pdf: FileText,
  document: FileText,
  spreadsheet: FileSpreadsheet,
  presentation: Presentation,
  file: FileText,
};

const attachmentLabels: Record<AgentAttachmentKind, string> = {
  image: "图片",
  video: "视频",
  audio: "音频",
  pdf: "PDF",
  document: "Word 文档",
  spreadsheet: "Excel 表格",
  presentation: "PowerPoint 演示文稿",
  file: "文件",
};

function attachmentIcon(kind: AgentAttachmentKind) {
  return attachmentIcons[kind] || FileText;
}

function attachmentLabel(kind: AgentAttachmentKind) {
  return attachmentLabels[kind] || "文件";
}

function detectAttachmentKind(file: File): AgentAttachmentKind {
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  if (
    file.type.startsWith("image/") ||
    ["png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "svg"].includes(extension)
  )
    return "image";
  if (
    file.type.startsWith("video/") ||
    ["mp4", "webm", "mov", "mkv", "avi", "m4v"].includes(extension)
  )
    return "video";
  if (
    file.type.startsWith("audio/") ||
    ["mp3", "wav", "m4a", "ogg", "aac", "flac", "opus"].includes(extension)
  )
    return "audio";
  if (file.type === "application/pdf" || extension === "pdf") return "pdf";
  if (["doc", "docx", "odt", "rtf"].includes(extension)) return "document";
  if (["xls", "xlsx", "ods", "csv"].includes(extension)) return "spreadsheet";
  if (["ppt", "pptx", "odp"].includes(extension)) return "presentation";
  return "file";
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function openAttachmentPicker() {
  attachmentInput.value?.click();
}

function handleFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  files.forEach((file, index) => {
    pendingAttachments.value.push({
      id: `attachment-${Date.now()}-${index}`,
      name: file.name,
      kind: detectAttachmentKind(file),
      mimeType: file.type || "application/octet-stream",
      size: formatFileSize(file.size),
      url: URL.createObjectURL(file),
      file,
    });
  });
  input.value = "";
}

function removePendingAttachment(id: string) {
  const index = pendingAttachments.value.findIndex((item) => item.id === id);
  const attachment = pendingAttachments.value[index];
  if (!attachment) return;
  if (attachment.url?.startsWith("blob:")) URL.revokeObjectURL(attachment.url);
  pendingAttachments.value.splice(index, 1);
}

function openCitation(
  citation: NonNullable<AgentMessage["citations"]>[number],
) {
  if (citation.url) {
    window.open(citation.url, "_blank", "noopener,noreferrer");
    return;
  }
  if (citation.assetId != null) {
    router.push({
      ...routeTo("project-asset-detail"),
      params: {
        ...routeTo("project-asset-detail").params,
        assetId: String(citation.assetId),
      },
      query: {
        ...(citation.chunkId != null ? { chunkId: String(citation.chunkId) } : {}),
        ...(citation.pageNumber != null ? { page: String(citation.pageNumber) } : {}),
        ...(citation.quote ? { quote: citation.quote.slice(0, 300) } : {}),
      },
    });
    return;
  }
  notify(
    `${citation.source}${citation.pageNumber ? ` · 第 ${citation.pageNumber} 页` : ""}`,
  );
}

function isWebCitation(
  citation: NonNullable<AgentMessage["citations"]>[number],
) {
  return citation.sourceType === "web" || Boolean(citation.url);
}

async function saveCitationToKnowledge(
  citation: NonNullable<AgentMessage["citations"]>[number],
) {
  if (
    !isWebCitation(citation) ||
    savedCitationAssets[citation.id] ||
    savingCitationIds.has(citation.id)
  )
    return;
  const excerpt = (citation.content || citation.quote || "").trim();
  if (!excerpt) {
    notify("这条外部结果没有可保存的证据摘录");
    return;
  }
  savingCitationIds.add(citation.id);
  try {
    const source = citation.url || citation.source;
    const markdown = `# ${citation.title}\n\n来源类型：外部网络搜索\n来源地址：${source}\n\n检索摘录：\n\n${excerpt}\n`;
    const safeTitle =
      citation.title
        .replace(/[\\/:*?"<>|\r\n]+/g, " ")
        .trim()
        .slice(0, 80) || "外部检索证据";
    const asset = await assetsApi.upload(
      workspaceId.value,
      projectId.value,
      new File([markdown], `${safeTitle}.md`, { type: "text/markdown" }),
      { name: `外部来源｜${safeTitle}`, language: "zh-CN" },
    );
    savedCitationAssets[citation.id] = String(asset.id);
    notify(`已手动加入知识库：${asset.name}`);
  } catch (error) {
    notify(
      error instanceof Error
        ? `加入知识库失败：${error.message}`
        : "加入知识库失败，未写入数据库",
    );
  } finally {
    savingCitationIds.delete(citation.id);
  }
}

async function handleSubmit() {
  if (!draft.value.trim() && !pendingAttachments.value.length) {
    void sendMessage(undefined, [], agentConfig.value);
    return;
  }
  const attachments = pendingAttachments.value.splice(0);
  try {
    const uploadedAttachments = await Promise.all(
      attachments.map(async (attachment) => {
        if (!attachment.file) return attachment;
        const uploaded = await agentApi.uploadAttachment(
          workspaceId.value,
          projectId.value,
          attachment.file,
        );
        return {
          ...attachment,
          uploadId: uploaded.uploadId,
          url: uploaded.url,
          file: undefined,
          size: formatFileSize(uploaded.size),
        };
      }),
    );
    void sendMessage(
      draft.value.trim() || "请分析我上传的附件。",
      uploadedAttachments,
      agentConfig.value,
    );
  } catch (error) {
    pendingAttachments.value.unshift(...attachments);
    notify(error instanceof Error ? error.message : "附件上传失败，请重试");
  }
}

function handleCreateThread() {
  createThread();
  notify("已创建新的 Agent 对话");
}

function requestDeleteThread(thread: AgentThreadSummary & { status?: string }) {
  if (thread.status === "running") {
    notify("请先停止正在运行的 Agent 对话");
    return;
  }
  deletingThread.value = thread;
  deleteOpen.value = true;
}

async function confirmDeleteThread() {
  const thread = deletingThread.value;
  if (!thread || deleting.value) return;

  deleting.value = true;
  try {
    await deleteThread(thread.id);
    notify(`对话「${thread.title}」已删除`);
  } catch (error) {
    notify(getApiErrorMessage(error, "对话删除失败"));
  } finally {
    deleting.value = false;
    deleteOpen.value = false;
    deletingThread.value = null;
  }
}

function openSettings(
  routeName: "settings-models" | "settings-web-search" | "project-assets",
) {
  router.push(routeTo(routeName));
}

function exportConversation() {
  if (!messages.value.length) {
    notify("当前对话还没有可导出的内容");
    return;
  }
  const body = messages.value
    .map(
      (message) =>
        `## ${message.role === "assistant" ? "Shinkou Agent" : "用户"}\n\n${message.content}`,
    )
    .join("\n\n");
  const sources = sourceCitations.value.length
    ? `\n\n## 引用记录\n\n${sourceCitations.value.map((citation) => `- ${citation.title} — ${citation.source}${citation.url ? ` (${citation.url})` : ""}`).join("\n")}`
    : "";
  const blob = new Blob(
    [`# ${activeThread.value.title}\n\n${body}${sources}\n`],
    { type: "text/markdown;charset=utf-8" },
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${activeThread.value.title || "项目对话"}.md`;
  link.click();
  URL.revokeObjectURL(url);
  notify("已导出当前对话与引用记录");
}

function scrollConversationToBottom() {
  nextTick(() => {
    const element = conversationScroll.value;
    if (element) element.scrollTop = element.scrollHeight;
  });
}

watch(messages, scrollConversationToBottom, { deep: true });
watch(events, scrollConversationToBottom, { deep: true });
watch(selectedModelId, applyModelGenerationDefaults);
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / WORKBENCH"
    title="项目工作台"
    subtitle="对话、资料、规划、审查和输出共享项目上下文，按需使用，不预设顺序"
  >
    <template #action>
      <button
        class="button button-primary"
        type="button"
        @click="handleCreateThread"
      >
        <Plus :size="17" />新建对话
      </button>
    </template>
  </PageHeader>

  <div class="agent-page">
    <input
      ref="attachmentInput"
      class="sr-only"
      type="file"
      multiple
      accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.json,.html,.htm,.ppt,.pptx,.odt,.ods,.odp,.rtf,.txt,.md,.markdown"
      @change="handleFilesSelected"
    />

    <div class="agent-shell">
      <section class="workspace-shortcuts" aria-label="独立工作区入口">
        <div class="shortcut-intro">
          <span class="workflow-kicker">RESEARCH DESK</span>
          <strong>工作台</strong>
        </div>
        <nav class="shortcut-grid" aria-label="项目独立模块">
          <RouterLink
            class="shortcut-card active"
            :to="routeTo('project-agent-chat')"
            ><MessageCircle :size="17" /><span
              ><strong>对话</strong><small>获取信息与整理思路</small></span
            ></RouterLink
          >
          <RouterLink class="shortcut-card" :to="routeTo('project-runs')"
            ><Search :size="17" /><span
              ><strong>搜索记录</strong><small>查看来源与证据</small></span
            ></RouterLink
          >
          <RouterLink class="shortcut-card" :to="routeTo('project-assets')"
            ><Database :size="17" /><span
              ><strong>知识库</strong><small>管理项目资料</small></span
            ></RouterLink
          >
          <RouterLink class="shortcut-card" :to="routeTo('project-planning')"
            ><ListChecks :size="17" /><span
              ><strong>规划</strong><small>整理目标与方案</small></span
            ></RouterLink
          >
          <RouterLink class="shortcut-card" :to="routeTo('project-reports')"
            ><FileText :size="17" /><span
              ><strong>输出</strong><small>导出已确认内容</small></span
            ></RouterLink
          >
          <RouterLink class="shortcut-card" :to="routeTo('project-overview')"
            ><BarChart3 :size="17" /><span
              ><strong>用量</strong><small>查看真实 Token 记录</small></span
            ></RouterLink
          >
        </nav>
      </section>

      <section class="agent-config-card" aria-label="Agent 当前配置">
        <div class="agent-config-intro">
          <span class="config-intro-icon"><Settings2 :size="16" /></span>
          <div>
            <strong>本次对话配置</strong>
            <small>配置只影响当前 Agent，不改变项目数据</small>
          </div>
        </div>
        <div class="agent-config-items">
          <div class="agent-config-item agent-config-model">
            <span class="config-item-icon"><Cpu :size="15" /></span>
            <label class="config-copy">
              <small>本次模型</small>
              <select v-model="selectedModelId" aria-label="选择本次对话模型">
                <option value="">使用项目默认模型</option>
                <option
                  v-for="model in modelOptions"
                  :key="model.id"
                  :value="model.id"
                >
                  {{ model.name }}
                </option>
              </select>
            </label>
            <button
              class="config-link-button"
              type="button"
              aria-label="管理模型配置"
              @click="openSettings('settings-models')"
            >
              <ChevronRight :size="13" />
            </button>
          </div>
          <button
            class="agent-config-item"
            type="button"
            @click="openSettings('project-assets')"
          >
            <span class="config-item-icon"><Database :size="15" /></span>
            <span class="config-copy"
              ><small>知识范围</small><strong>当前项目资料</strong></span
            >
            <span class="config-action">查看<ChevronRight :size="13" /></span>
          </button>
          <div class="agent-config-item agent-config-tool">
            <span class="config-item-icon"><Link2 :size="15" /></span>
            <span class="config-copy"
              ><small>联网搜索</small
              ><strong>{{
                !webSearchReady
                  ? "未配置独立搜索服务"
                  : allowWeb
                    ? "本次运行已开启"
                    : "本次运行已关闭"
              }}</strong
              ><small>只保存来源记录，不自动入库</small></span
            >
            <label
              class="inline-switch"
              :title="
                !webSearchReady
                  ? '请先配置联网搜索'
                  : allowWeb
                    ? '关闭本次运行联网搜索'
                    : '允许本次运行联网搜索'
              "
              ><input
                v-model="allowWeb"
                :disabled="!webSearchReady"
                type="checkbox"
                aria-label="允许本次运行联网搜索" /><span
            /></label>
            <button
              class="config-link-button"
              type="button"
              aria-label="管理联网搜索配置"
              @click="openSettings('settings-web-search')"
            >
              <ChevronRight :size="13" />
            </button>
          </div>
          <button
            class="agent-config-item"
            type="button"
            @click="generationOpen = !generationOpen"
          >
            <span class="config-item-icon"><Settings2 :size="15" /></span>
            <span class="config-copy"
              ><small>生成参数</small
              ><strong
                >T {{ generation.temperature }} ·
                {{ generation.maxTokens }} tokens</strong
              ></span
            >
            <span class="config-action"
              >{{ generationOpen ? "收起" : "调整" }}<ChevronRight :size="13"
            /></span>
          </button>
        </div>
      </section>

      <section
        v-if="generationOpen"
        class="agent-generation-panel"
        aria-label="本次对话生成参数"
      >
        <div class="generation-heading">
          <div>
            <strong>本次对话生成参数</strong
            ><small
              >优先使用项目模型配置；这里只覆盖本次运行，不修改数据库中的模型默认值。</small
            >
          </div>
          <span>{{ activeModel?.name || "未选择项目模型" }}</span>
        </div>
        <div class="generation-grid">
          <label class="generation-field"
            ><span>检索 Top-K <small>项目资料</small></span
            ><input
              v-model.number="generation.retrievalTopK"
              type="number"
              min="1"
              max="20"
              step="1"
          /></label>
          <label class="generation-field"
            ><span>最大输出长度 <small>tokens</small></span
            ><input
              v-model.number="generation.maxTokens"
              type="number"
              min="1"
              max="1000000"
              step="256"
          /></label>
          <label class="generation-field"
            ><span>回答随机性 <small>Temperature</small></span
            ><input
              v-model.number="generation.temperature"
              type="number"
              min="0"
              max="2"
              step="0.1"
          /></label>
          <label class="generation-field"
            ><span>候选概率范围 <small>Top-P</small></span
            ><input
              v-model.number="generation.topP"
              type="number"
              min="0.01"
              max="1"
              step="0.05"
          /></label>
          <label class="generation-field"
            ><span>候选数量 <small>模型参数 Top-K</small></span
            ><input
              v-model.number="generation.topK"
              type="number"
              min="1"
              max="1000"
              step="1"
              placeholder="供应商默认"
          /></label>
          <label class="generation-field"
            ><span>重复内容惩罚 <small>Frequency Penalty</small></span
            ><input
              v-model.number="generation.frequencyPenalty"
              type="number"
              min="-2"
              max="2"
              step="0.1"
          /></label>
          <label class="generation-field"
            ><span>深度思考</span
            ><select v-model="generation.thinkingEnabled">
              <option :value="true">开启</option>
              <option :value="false">关闭</option>
            </select></label
          >
          <label class="generation-field"
            ><span>思考强度</span
            ><select
              v-model="generation.reasoningEffort"
              :disabled="!generation.thinkingEnabled"
            >
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select></label
          >
          <label class="generation-field"
            ><span>回答方式</span
            ><select v-model="generation.strategy">
              <option value="AUTO">自动选择（推荐）</option>
              <option value="PLAN_AND_SOLVE">先整理步骤</option>
              <option value="REACT">边查边确认</option>
              <option value="REFLECTION">回答后检查</option>
            </select></label
          >
          <label class="generation-field"
            ><span>多智能体协作</span
            ><select v-model="multiAgentMode">
              <option value="AUTO">自动按需（推荐）</option>
              <option value="ON">强制开启</option>
              <option value="OFF">关闭</option>
            </select></label
          >
          <label class="generation-field"
            ><span>回答质量检查</span
            ><select v-model="reflectionEnabled">
              <option :value="true">按需检查</option>
              <option :value="false">关闭</option>
            </select></label
          >
        </div>
        <p class="generation-note">
          系统会根据问题范围自动选择处理方式：复杂任务或明确要求时由主智能体协调多个子智能体，普通问题保持单智能体快速回答；需要多步核对时先整理步骤，必要时再检查回答质量。
        </p>
      </section>

      <div class="agent-workspace">
        <aside class="panel agent-thread-panel">
          <div class="agent-panel-heading">
            <div>
              <span class="agent-kicker">CONVERSATIONS</span>
              <h2>项目对话</h2>
            </div>
            <button
              class="mini-button"
              type="button"
              aria-label="新建对话"
              @click="handleCreateThread"
            >
              <Plus :size="15" />
            </button>
          </div>
          <div class="thread-list">
            <div
              v-for="thread in threads"
              :key="thread.id"
              class="thread-item"
              :class="{ active: activeThread.id === thread.id }"
            >
              <button
                class="thread-select"
                type="button"
                @click="selectThread(thread.id)"
              >
                <span class="thread-icon"><MessageCircle :size="15" /></span>
                <span class="thread-copy">
                  <strong>{{ thread.title }}</strong>
                  <small>{{ thread.preview }}</small>
                </span>
                <ChevronRight :size="14" />
              </button>
              <button
                class="thread-delete"
                type="button"
                :disabled="thread.status === 'running'"
                :aria-label="`删除对话 ${thread.title}`"
                :title="
                  thread.status === 'running' ? '请先停止当前运行' : '删除对话'
                "
                @click.stop="requestDeleteThread(thread)"
              >
                <Trash2 :size="14" />
              </button>
            </div>
          </div>
        </aside>

        <section class="panel agent-conversation" aria-label="Agent 对话区域">
          <header class="conversation-header">
            <div class="conversation-title">
              <span class="agent-avatar"><Bot :size="17" /></span>
              <div>
                <strong>{{ activeThread.title }}</strong>
                <span
                  ><i :class="{ live: isRunning }" />{{
                    isRunning ? "Agent 正在工作" : "对话已就绪"
                  }}</span
                >
              </div>
            </div>
            <div class="conversation-meta">
              <button
                class="conversation-export"
                type="button"
                title="导出当前对话"
                @click="exportConversation"
              >
                <Download :size="13" />导出
              </button>
              <span v-if="activeThread.runId"
                >运行 {{ activeThread.runId }}</span
              >
              <span><Clock3 :size="13" />{{ activeThread.updatedAt }}</span>
            </div>
          </header>

          <div
            v-if="isRunning"
            class="live-activity"
            role="status"
            aria-live="polite"
          >
            <span class="live-activity-icon">
              <component
                :is="eventIcon(currentEvent?.kind || 'plan')"
                :size="15"
              />
            </span>
            <div class="live-activity-copy">
              <div class="live-activity-topline">
                <span
                  >处理 {{ runElapsedLabel }} · 当前阶段
                  {{ formatElapsed(activityElapsed) }}</span
                >
                <em>实时活动</em>
              </div>
              <strong>{{ currentEvent?.title || "正在连接 Agent" }}</strong>
              <p>{{ activityDetail(currentEvent) }}</p>
            </div>
            <span class="live-activity-next"
              >下一步：{{ nextActivityLabel(currentEvent) }}</span
            >
          </div>

          <div ref="conversationScroll" class="conversation-scroll">
            <div v-if="!messages.length" class="conversation-empty">
              <span class="empty-orb"><Sparkles :size="22" /></span>
              <h2>先从一个问题开始</h2>
              <p>
                Agent
                会读取项目资料，按需搜索网页，并把来源保存在本次记录中。是否纳入知识库、是否形成规划，由你决定。
              </p>
              <div class="launch-hints">
                <span>资料记录</span><span>人工判断</span><span>按需规划</span>
              </div>
            </div>

            <div
              v-for="message in messages"
              :key="message.id"
              class="message-row"
              :class="message.role"
            >
              <div v-if="message.role === 'assistant'" class="message-avatar">
                <Bot :size="15" />
              </div>
              <div class="message-body">
                <div class="message-meta">
                  <strong>{{
                    message.role === "assistant" ? "Shinkou Agent" : "你"
                  }}</strong>
                  <span>{{ message.createdAt }}</span>
                  <span
                    v-if="message.status === 'streaming'"
                    class="streaming-label"
                    ><i />生成中</span
                  >
                </div>
                <div class="message-bubble">
                  <p
                    v-for="(paragraph, paragraphIndex) in messageParagraphs(
                      message,
                    )"
                    :key="paragraphIndex"
                  >
                    <template
                      v-for="(segment, segmentIndex) in paragraph"
                      :key="segmentIndex"
                    >
                      <span v-if="!segment.citation">{{ segment.text }}</span>
                      <button
                        v-else
                        type="button"
                        class="inline-citation"
                        :title="
                          '引用 ' +
                          citationNumber(message, segment.citation) +
                          '：' +
                          citationTitle(segment.citation)
                        "
                        @click="openCitation(segment.citation)"
                      >
                        【{{ citationNumber(message, segment.citation) }}】
                      </button>
                    </template>
                  </p>
                  <span
                    v-if="message.status === 'streaming'"
                    class="typing-caret"
                  />
                </div>
                <div
                  v-if="message.media?.length"
                  class="message-media"
                  aria-label="Agent 输出媒体"
                >
                  <figure
                    v-for="media in message.media"
                    :key="media.id"
                    class="message-media-card"
                  >
                    <img
                      v-if="media.kind === 'image'"
                      :src="media.url"
                      :alt="media.name"
                    />
                    <video
                      v-else
                      controls
                      preload="metadata"
                      :src="media.url"
                      :aria-label="media.name"
                    />
                    <figcaption>{{ media.name }}</figcaption>
                  </figure>
                </div>
                <details
                  v-if="message.attachments?.length"
                  class="attachment-dropdown"
                  :class="{ 'is-single': message.attachments.length === 1 }"
                  :open="message.attachments.length === 1"
                >
                  <summary
                    v-if="message.attachments.length > 1"
                    class="attachment-dropdown-summary"
                  >
                    <span><Paperclip :size="13" />文件</span
                    ><strong>{{ message.attachments.length }}</strong
                    ><ChevronRight :size="13" />
                  </summary>
                  <div class="message-attachments">
                    <article
                      v-for="attachment in message.attachments"
                      :key="attachment.id"
                      class="attachment-card"
                      :class="`attachment-${attachment.kind}`"
                    >
                      <div
                        v-if="
                          attachment.kind === 'image' &&
                          (attachment.previewUrl || attachment.url)
                        "
                        class="attachment-media image-media"
                      >
                        <img
                          :src="attachment.previewUrl || attachment.url"
                          :alt="attachment.name"
                        />
                      </div>
                      <div
                        v-else-if="
                          attachment.kind === 'video' && attachment.url
                        "
                        class="attachment-media"
                      >
                        <video
                          controls
                          preload="metadata"
                          :src="attachment.url"
                          :aria-label="attachment.name"
                        />
                      </div>
                      <div
                        v-else-if="
                          attachment.kind === 'audio' && attachment.url
                        "
                        class="attachment-media audio-media"
                      >
                        <audio
                          controls
                          :src="attachment.url"
                          :aria-label="attachment.name"
                        />
                      </div>
                      <div
                        v-else-if="attachment.kind === 'pdf' && attachment.url"
                        class="attachment-media pdf-media"
                      >
                        <iframe
                          :src="attachment.url"
                          :title="attachment.name"
                        />
                      </div>
                      <div v-else class="attachment-icon">
                        <component
                          :is="attachmentIcon(attachment.kind)"
                          :size="19"
                        />
                      </div>
                      <div class="attachment-copy">
                        <strong :title="attachment.name">{{
                          attachment.name
                        }}</strong>
                        <small
                          >{{ attachmentLabel(attachment.kind) }} ·
                          {{ attachment.size || "待上传" }}</small
                        >
                      </div>
                      <a
                        v-if="attachment.url"
                        class="attachment-open"
                        :href="attachment.previewUrl || attachment.url"
                        target="_blank"
                        rel="noreferrer"
                        >在线打开</a
                      >
                    </article>
                  </div>
                </details>
                <details
                  v-if="
                    message.role === 'assistant' &&
                    messageCitations(message).length
                  "
                  class="message-citations"
                >
                  <summary class="message-citations-summary">
                    <span class="citation-label"
                      ><FileSearch :size="13" />引用
                      {{ messageCitations(message).length }}</span
                    >
                    <small>展开查看来源</small>
                    <ChevronRight :size="13" />
                  </summary>
                  <div class="message-citation-list">
                    <div
                      v-for="citation in messageCitations(message)"
                      :key="citation.id"
                      class="message-citation-row"
                    >
                      <button type="button" @click="openCitation(citation)">
                        <span
                          >【{{ citationNumber(message, citation) }}】
                          {{ citation.title }}</span
                        ><small>{{ citation.source }}</small
                        ><ChevronRight :size="12" />
                      </button>
                      <button
                        v-if="isWebCitation(citation)"
                        type="button"
                        class="citation-save-mini"
                        :disabled="
                          Boolean(savedCitationAssets[citation.id]) ||
                          savingCitationIds.has(citation.id)
                        "
                        @click.stop="saveCitationToKnowledge(citation)"
                      >
                        <CheckCircle2
                          v-if="savedCitationAssets[citation.id]"
                          :size="12"
                        />
                        <Plus v-else :size="12" />
                        {{
                          savedCitationAssets[citation.id]
                            ? "已加入"
                            : savingCitationIds.has(citation.id)
                              ? "加入中"
                              : "加入知识库"
                        }}
                      </button>
                    </div>
                  </div>
                </details>
              </div>
            </div>
          </div>

          <footer class="composer-wrap">
            <div
              v-if="pendingAttachments.length"
              class="pending-attachments"
              aria-label="待发送附件"
            >
              <div
                v-for="attachment in pendingAttachments"
                :key="attachment.id"
                class="pending-attachment"
              >
                <component :is="attachmentIcon(attachment.kind)" :size="14" />
                <span :title="attachment.name">{{ attachment.name }}</span>
                <button
                  type="button"
                  :aria-label="`移除附件 ${attachment.name}`"
                  @click="removePendingAttachment(attachment.id)"
                >
                  <X :size="13" />
                </button>
              </div>
            </div>
            <form class="composer" @submit.prevent="handleSubmit">
              <textarea
                v-model="draft"
                rows="3"
                :disabled="hasRunningThread"
                placeholder="问问 Agent：比较方案、查找证据或整理下一步…"
                aria-label="输入给 Agent 的问题"
                @keydown.enter.exact.prevent="handleSubmit"
              />
              <div class="composer-bottom">
                <div class="composer-tools">
                  <button
                    type="button"
                    class="composer-tool-button"
                    @click="openAttachmentPicker"
                  >
                    <Paperclip :size="14" />添加附件
                  </button>
                  <span
                    ><Sparkles
                      :size="13"
                    />来源只会记录，不会自动写入知识库</span
                  >
                </div>
                <button
                  v-if="isRunning"
                  class="button button-secondary button-sm"
                  type="button"
                  :disabled="cancelling"
                  @click="stopRun"
                >
                  <Square :size="13" />{{
                    cancelling ? "正在暂停" : "暂停运行"
                  }}
                </button>
                <button
                  v-else
                  class="button button-primary button-sm"
                  type="submit"
                  :disabled="!canSubmitMessage"
                >
                  {{ hasRunningThread ? "请先暂停运行" : canSubmitMessage ? "发送" : "输入内容" }}
                  <Send :size="14" />
                </button>
              </div>
            </form>
            <p v-if="composerError" class="composer-error" role="alert">
              <AlertCircle :size="14" />{{ composerError }}
            </p>
          </footer>
        </section>

        <aside class="panel agent-inspector">
          <div class="agent-panel-heading inspector-heading">
            <div>
              <span class="agent-kicker">EXECUTION</span>
              <h2>运行与上下文</h2>
            </div>
            <span class="run-state" :class="activeThread.status"
              ><i />{{
                isRunning
                  ? "运行中"
                  : activeThread.status === "failed"
                    ? "失败"
                    : activeThread.status === "completed"
                      ? "已完成"
                      : "就绪"
              }}</span
            >
          </div>
          <div class="run-progress">
            <div class="progress-top">
              <span>本次运行</span
              ><small
                >{{ completedEvents }}/{{ events.length }} 个阶段完成</small
              ><strong>{{
                activeThread.status === "idle" ? "—" : `${progress}%`
              }}</strong>
            </div>
            <div class="progress-track">
              <i
                :style="{
                  width: activeThread.status === 'idle' ? '0%' : `${progress}%`,
                }"
              />
            </div>
            <div class="run-timing">
              <span
                ><small>处理时间</small
                ><strong>{{ runElapsedLabel }}</strong></span
              >
              <span
                ><small>计时来源</small
                ><strong>{{ runTimingSource }}</strong></span
              >
            </div>
            <div
              v-if="currentEvent"
              class="current-stage"
              :class="currentEvent.status"
            >
              <div class="current-stage-heading">
                <span>{{
                  currentEvent.status === "running" ? "当前阶段" : "最近成果"
                }}</span
                ><strong>{{ currentEvent.title }}</strong>
              </div>
              <div
                v-if="currentEvent.status === 'running'"
                class="current-stage-live"
              >
                <i />已运行 {{ formatElapsed(activityElapsed) }}
              </div>
              <p>{{ activityDetail(currentEvent) }}</p>
              <small v-if="currentEvent.status === 'running'"
                >下一步：{{ nextActivityLabel(currentEvent) }}</small
              >
            </div>
            <p v-else>发送问题后，这里会显示 Agent 的实时执行过程</p>
          </div>

          <div class="context-panel" aria-label="当前上下文">
            <div class="inspector-section-title">
              <span>上下文占用（预估）</span
              ><strong
                >{{
                  formatTokenCount(contextUsage?.finalTokenEstimate)
                }}
                tokens</strong
              >
            </div>
            <div class="context-metrics">
              <span
                ><strong>{{
                  formatTokenCount(contextUsage?.finalTokenEstimate)
                }}</strong
                ><small>送入模型预估</small></span
              >
              <span
                ><strong>{{ formatRealToken(tokenUsage?.inputTokens) }}</strong
                ><small>模型实际输入</small></span
              >
              <span
                ><strong>{{ formatRealToken(tokenUsage?.outputTokens) }}</strong
                ><small>模型实际输出</small></span
              >
              <span
                ><strong>{{ formatRealToken(tokenUsage?.totalTokens) }}</strong
                ><small>模型实际合计</small></span
              >
            </div>
            <div class="context-metrics context-record-metrics">
              <span
                ><strong>{{ messages.length }}</strong
                ><small>对话消息</small></span
              >
              <span
                ><strong>{{ contextSourceCount }}</strong
                ><small>资料 / 引用</small></span
              >
            </div>
            <p class="token-usage-status">
              <span class="token-status-dot" />{{ tokenUsageStatus }}
            </p>
            <p v-if="contextUsage?.filteredMessages">
              已省略
              {{ contextUsage.filteredMessages }} 条无关历史消息，保留
              {{ contextUsage.selectedContextMessages ?? "相关" }} 条上下文。
            </p>
            <p v-else-if="contextUsage?.compressedMessages">
              已自动压缩
              {{ contextUsage.compressedMessages }} 条较早消息，保留最近
              {{ contextUsage.finalMessageCount ?? "部分" }} 条上下文。
            </p>
            <p v-if="contextUsage?.modelContextWindow">
              模型上下文上限
              {{ formatTokenCount(contextUsage.modelContextWindow) }} tokens；
              本次上下文预算
              {{ formatTokenCount(contextUsage.contextTokenBudget) }} tokens。
            </p>
            <p v-else-if="contextUsage">
              当前上下文约
              {{ formatTokenCount(contextUsage.finalTokenEstimate) }}
              tokens；这是发送给模型前的上下文估算值。
            </p>
            <p v-else-if="contextLoading">正在读取项目资料数量…</p>
            <p v-else-if="tokenUsage?.available === false">
              模型提供方未返回本次 usage；不以字符数估算冒充真实 token。
            </p>
            <p v-else-if="tokenUsage">
              已接收模型提供方返回的真实 usage；历史运行没有保存上下文估算明细。
            </p>
            <p v-else>当前运行没有可用的 token 记录，不使用虚假的 0 值代替。</p>
          </div>

          <div class="event-list">
            <div class="event-list-heading">
              <span>实时执行阶段</span
              ><strong>{{ completedEvents }}/{{ events.length }}</strong>
            </div>
            <div
              v-for="event in events"
              :key="event.id"
              class="event-item"
              :class="event.status"
            >
              <span class="event-icon"
                ><component :is="eventIcon(event.kind)" :size="14"
              /></span>
              <div class="event-copy">
                <div>
                  <strong>{{ event.title }}</strong
                  ><span class="event-meta"
                    ><small>{{ eventStatusLabel(event) }}</small
                    ><em>{{ eventTimeLabel(event) }}</em></span
                  >
                </div>
                <p>{{ event.detail }}</p>
              </div>
            </div>
            <div v-if="!events.length" class="event-empty">
              <Circle :size="15" />等待下一次运行
            </div>
          </div>

          <section class="process-review-section" aria-label="过程回顾">
            <button
              class="process-review-toggle"
              type="button"
              :aria-expanded="processReviewOpen"
              @click="processReviewOpen = !processReviewOpen"
            >
              <span><ListChecks :size="14" />过程回顾</span>
              <small>{{ processEvents.length }} 条真实活动</small>
              <ChevronRight :size="14" :class="{ open: processReviewOpen }" />
            </button>
            <div v-if="processReviewOpen" class="process-review-list">
              <div
                v-for="(event, index) in processEvents"
                :key="`${event.id}-${event.meta?.eventId || index}`"
                class="process-review-item"
                :class="event.status"
              >
                <span class="process-review-index">{{
                  String(index + 1).padStart(2, "0")
                }}</span>
                <span class="process-review-icon"
                  ><component :is="eventIcon(event.kind)" :size="12"
                /></span>
                <div>
                  <strong>{{ event.title }}</strong>
                  <small
                    >{{ eventStatusLabel(event)
                    }}<template v-if="event.duration">
                      · {{ event.duration }}</template
                    ></small
                  >
                  <p>{{ event.detail || activityDetail(event) }}</p>
                </div>
              </div>
              <p v-if="!processEvents.length" class="process-review-empty">
                本次运行还没有可回顾的活动。
              </p>
              <p v-else class="process-review-note">
                这里只展示阶段、工具、证据和结果摘要，不展示模型隐藏思维内容。
              </p>
            </div>
          </section>

          <div class="inspector-footer">
            <CheckCircle2
              :size="14"
            />不展示模型隐藏思维；这里展示检索、证据、生成和自检等可审计阶段与成果。
          </div>
        </aside>
      </div>
    </div>
  </div>

  <Dialog v-model:open="deleteOpen">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>删除 Agent 对话</DialogTitle>
        <DialogDescription>
          删除「{{
            deletingThread?.title
          }}」后，消息、运行记录和引用信息将无法恢复。
        </DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <button
          class="button button-secondary"
          type="button"
          :disabled="deleting"
          @click="deleteOpen = false"
        >
          取消
        </button>
        <button
          class="button button-danger"
          type="button"
          :disabled="deleting"
          @click="confirmDeleteThread"
        >
          {{ deleting ? "删除中..." : "确认删除" }}
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.agent-page {
  --agent-accent-border: #b7e9e1;
  --agent-accent-surface: #f2fcfa;
  --agent-accent-surface-strong: #dff7f3;
  --agent-accent-surface-soft: #eaf9f6;
  --agent-live-gradient-start: #f2fcfa;
  --agent-live-gradient-end: #f8fdfc;
  --agent-danger-text: #c15b5b;
  --agent-danger-fill: #d76363;

  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 0.625rem;
  overflow: hidden;
}

.agent-shell {
  display: flex;
  min-height: 0;
  flex: 1 1 0;
  flex-direction: column;
  overflow: hidden;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.875rem;
  background: var(--surface);
  box-shadow: 0 0.75rem 2rem rgb(21 53 52 / 5%);
}

.agent-config-card {
  display: grid;
  grid-template-columns: minmax(11rem, 0.72fr) minmax(0, 2.28fr);
  align-items: center;
  gap: 0.75rem;
  flex: 0 0 auto;
  padding: 0.5rem 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.875rem;
  background: linear-gradient(
    110deg,
    color-mix(in oklab, var(--teal) 6%, var(--surface)),
    var(--surface)
  );
}

.agent-config-intro,
.agent-config-item {
  display: flex;
  align-items: center;
}

.agent-config-intro {
  min-width: 0;
  flex: 0 0 auto;
  gap: 0.5rem;
}

.config-intro-icon {
  display: grid;
  width: 1.875rem;
  height: 1.875rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5625rem;
  background: #e2f7f3;
  color: var(--teal-dark);
}

.agent-config-intro strong,
.agent-config-intro small {
  display: block;
}

.agent-config-intro strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}

.agent-config-intro small {
  margin-top: 0.125rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.agent-config-items {
  display: grid;
  min-width: 0;
  flex: 1;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  min-height: 3.25rem;
}

.agent-generation-panel {
  display: grid;
  gap: 0.75rem;
  flex: 0 0 auto;
  padding: 0.75rem 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;
  background: var(--surface-raised);
}

.generation-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.generation-heading > div {
  display: grid;
  gap: 0.1875rem;
}

.generation-heading strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}

.generation-heading small,
.generation-heading > span,
.generation-note {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.5;
}

.generation-heading > span {
  flex: 0 0 auto;
  padding: 0.25rem 0.4375rem;
  border-radius: 999px;
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
  color: var(--teal-dark);
}

.generation-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.625rem;
}

.generation-field {
  display: grid;
  min-width: 0;
  gap: 0.3125rem;
}

.generation-field > span {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.generation-field > span small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.generation-field input,
.generation-field select {
  width: 100%;
  min-width: 0;
  padding: 0.4375rem 0.5rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  background: var(--surface);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.75rem;
}

.generation-field input:focus,
.generation-field select:focus {
  border-color: var(--teal);
  outline: 0.125rem solid color-mix(in oklab, var(--teal) 20%, transparent);
}

.generation-note {
  margin: 0;
}

.agent-config-item {
  min-width: 0;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border: 0;
  border-left: 0.0625rem solid var(--workspace-divider);
  border-radius: 0;
  background: transparent;
  color: var(--teal-dark);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}

.agent-config-item:first-child {
  border-left: 0;
}

.agent-config-item:hover {
  background: color-mix(in oklab, var(--teal) 6%, transparent);
}

.config-item-icon {
  display: grid;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5rem;
  background: color-mix(in oklab, var(--teal) 10%, var(--surface));
  color: var(--teal);
}

.agent-config-item select {
  width: 100%;
  min-width: 0;
  max-width: none;
  border: 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 650;
  outline: none;
  cursor: pointer;
}

.config-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: flex-start;
  flex-direction: column;
  gap: 0.125rem;
}

.config-link-button {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--workspace-subtle);
  cursor: pointer;
}

.config-action {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.125rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.inline-switch {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  cursor: pointer;
}

.inline-switch input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.inline-switch span {
  position: relative;
  display: block;
  width: 1.75rem;
  height: 1rem;
  border-radius: 999px;
  background: var(--workspace-divider);
  transition: background 0.16s ease;
}

.inline-switch span::after {
  position: absolute;
  top: 0.125rem;
  left: 0.125rem;
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  background: var(--surface);
  content: "";
  transition: transform 0.16s ease;
}

.inline-switch input:checked + span {
  background: var(--teal);
}

.inline-switch input:checked + span::after {
  transform: translateX(0.75rem);
}

.agent-config-item small,
.agent-config-item strong {
  overflow: hidden;
  max-width: 100%;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-config-item small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.agent-config-item strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
}

.agent-workspace {
  gap: 0;
  overflow: hidden;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.875rem;
  background: var(--surface);
  box-shadow: 0 0.75rem 2rem rgb(21 53 52 / 5%);
}

.agent-shell > .agent-workspace {
  flex: 1 1 0;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

.agent-workspace > .agent-thread-panel,
.agent-workspace > .agent-conversation,
.agent-workspace > .agent-inspector {
  border: 0;
  border-radius: 0;
  background: var(--surface);
  box-shadow: none;
}

.agent-workspace > .agent-thread-panel,
.agent-workspace > .agent-conversation {
  border-right: 0.0625rem solid var(--workspace-divider);
}

.agent-workspace > .agent-inspector {
  border-right: 0;
}

@media (max-width: 68.75rem) and (min-width: 47.51rem) {
  .agent-workspace > .agent-inspector {
    border-top: 0.0625rem solid var(--workspace-divider);
  }
}

@media (max-width: 47.5rem) {
  .agent-workspace {
    gap: 0;
  }

  .agent-workspace > .agent-thread-panel,
  .agent-workspace > .agent-conversation {
    border-right: 0;
    border-bottom: 0.0625rem solid var(--workspace-divider);
  }
}

.agent-workspace {
  display: grid;
  grid-template-columns: 13.5rem minmax(36rem, 1fr) 18rem;
  min-height: 0;
  height: min(68rem, calc(100dvh - 10rem));
  flex: 1 1 0;
}

.agent-thread-panel,
.agent-conversation,
.agent-inspector {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.agent-thread-panel,
.agent-inspector {
  display: flex;
  flex-direction: column;
}

.agent-inspector .event-list {
  min-height: 0;
  flex: 1 1 auto;
}

.agent-panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.875rem 1rem 0.75rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.agent-kicker {
  display: block;
  margin-bottom: 0.375rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.agent-panel-heading h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.875rem;
  font-weight: 680;
}

.thread-list {
  display: grid;
  gap: 0.25rem;
  padding: 0.875rem;
  overflow-y: auto;
}

.thread-item {
  display: flex;
  width: 100%;
  align-items: center;
  min-width: 0;
  border-radius: 0.5625rem;
  background: transparent;
  color: var(--workspace-muted);
  text-align: left;
  transition:
    background 0.16s ease,
    color 0.16s ease;
}

.thread-item:hover,
.thread-item.active {
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  color: var(--workspace-text);
}

.thread-item.active {
  box-shadow: inset 0.125rem 0 0 var(--teal);
}

.thread-select {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 0.5625rem;
  padding: 0.6875rem 0.25rem 0.6875rem 0.5625rem;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.thread-delete {
  display: grid;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 auto;
  margin-right: 0.375rem;
  place-items: center;
  border: 0;
  border-radius: 0.375rem;
  background: transparent;
  color: var(--workspace-subtle);
  opacity: 0;
  cursor: pointer;
  transition:
    background 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease;
}

.thread-item:hover .thread-delete,
.thread-item.active .thread-delete,
.thread-delete:focus-visible {
  opacity: 1;
}

.thread-delete:hover:not(:disabled) {
  background: color-mix(in oklab, #ef4444 10%, var(--surface));
  color: #dc2626;
}

.thread-delete:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}

.thread-icon,
.message-avatar,
.agent-avatar,
.empty-orb {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5rem;
}

.thread-icon {
  width: 1.875rem;
  height: 1.875rem;
  background: var(--surface-soft);
  color: var(--workspace-subtle);
}

.thread-item.active .thread-icon {
  background: #dff7f3;
  color: var(--teal-dark);
}

.thread-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.25rem;
}

.thread-copy strong,
.thread-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thread-copy strong {
  font-size: 0.8125rem;
  font-weight: 650;
}

.thread-copy small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.agent-conversation {
  display: flex;
  flex-direction: column;
  background: var(--surface);
}

.conversation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 3.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.conversation-title,
.conversation-meta,
.conversation-title > div,
.message-meta,
.composer-bottom,
.streaming-label,
.citation-label,
.inspector-footer,
.run-state,
.progress-top,
.event-item > div:first-of-type,
.citation-card-top {
  display: flex;
  align-items: center;
}

.conversation-title {
  min-width: 0;
  gap: 0.625rem;
}

.agent-avatar {
  width: 2.125rem;
  height: 2.125rem;
  border-radius: 0.625rem;
  background: #dff7f3;
  color: var(--teal-dark);
}

.conversation-title > div {
  min-width: 0;
  align-items: flex-start;
  flex-direction: column;
  gap: 0.25rem;
}

.conversation-title strong {
  overflow: hidden;
  color: var(--workspace-text);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-title span:not(.agent-avatar) {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.conversation-title span i,
.streaming-label i,
.run-state i {
  display: inline-block;
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: #a7b1b4;
}

.conversation-title span i.live,
.streaming-label i,
.run-state.running i {
  background: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 14%, transparent);
}

.conversation-meta {
  gap: 0.6875rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  white-space: nowrap;
}

.conversation-meta span:last-child {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.conversation-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.875rem 1.125rem 1rem;
  scroll-behavior: smooth;
}

.message-row {
  display: flex;
  gap: 0.625rem;
  margin-bottom: 1rem;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.user .message-body {
  max-width: 82%;
  align-items: flex-end;
}

.message-row.assistant .message-body {
  max-width: calc(100% - 2.25rem);
}

.message-avatar {
  width: 1.875rem;
  height: 1.875rem;
  background: var(--surface-soft);
  color: var(--teal-dark);
}

.message-body {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.3125rem;
}

.message-meta {
  gap: 0.5rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.message-meta strong {
  color: var(--workspace-muted);
  font-weight: 650;
}

.streaming-label {
  gap: 0.3125rem;
  color: var(--teal-dark);
}

.message-bubble {
  padding: 0.875rem 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.25rem 0.75rem 0.75rem 0.75rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
  font-size: 0.75rem;
  line-height: 1.8;
}

.message-media {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.message-media-card {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-raised);
}

.message-media-card img,
.message-media-card video {
  display: block;
  width: 100%;
  max-height: 18rem;
  object-fit: contain;
  background: #101d22;
}

.message-media-card figcaption {
  overflow: hidden;
  padding: 0.375rem 0.5rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-row.user .message-bubble {
  border-color: transparent;
  border-radius: 0.75rem 0.25rem 0.75rem 0.75rem;
  background: #173b3a;
  color: #effffc;
}

.message-bubble p {
  margin: 0;
}

.message-bubble p + p {
  margin-top: 0.5rem;
}

.typing-caret {
  display: inline-block;
  width: 0.375rem;
  height: 0.875rem;
  margin-left: 0.125rem;
  vertical-align: text-bottom;
  background: var(--teal);
  animation: blink 0.8s steps(2, jump-none) infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.message-citations {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.375rem;
}

.citation-label {
  gap: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.message-citations button {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  max-width: 13rem;
  overflow: hidden;
  padding: 0.3125rem 0.4375rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  background: var(--surface);
  color: var(--teal-dark);
  font: inherit;
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.message-citations button:hover {
  border-color: var(--teal);
  background: var(--surface-soft);
}

.conversation-empty {
  display: grid;
  max-width: 28rem;
  margin: 3.5rem auto 0;
  justify-items: center;
  text-align: center;
}

.empty-orb {
  width: 3.25rem;
  height: 3.25rem;
  margin-bottom: 1rem;
  border-radius: 1rem;
  background: #dff7f3;
  color: var(--teal-dark);
}

.conversation-empty h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 1rem;
}

.conversation-empty p {
  margin: 0.5rem 0 1.25rem;
  color: var(--workspace-muted);
  font-size: 0.8125rem;
  line-height: 1.65;
}

.launch-hints {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.3125rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
}

.launch-hints span {
  padding: 0.25rem 0.375rem;
  border-radius: 999px;
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
}

.launch-hints i {
  color: var(--workspace-subtle);
  font-style: normal;
}

.composer-wrap {
  padding: 0.75rem 1.125rem 1rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  background: var(--surface);
}

.composer {
  padding: 0.6875rem 0.75rem 0.5625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.6875rem;
  background: var(--surface-raised);
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}

.composer:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 12%, transparent);
}

.composer textarea {
  display: block;
  width: 100%;
  resize: none;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.8125rem;
  line-height: 1.6;
}

.composer textarea::placeholder {
  color: var(--workspace-subtle);
}

.composer-bottom {
  justify-content: space-between;
  gap: 0.625rem;
  margin-top: 0.375rem;
}

.composer-bottom > span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.composer-bottom > span svg {
  color: var(--teal-dark);
}

.composer-error {
  display: flex;
  align-items: center;
  gap: 0.3125rem;
  margin: 0.5rem 0 0;
  color: var(--agent-danger-text);
  font-size: 0.75rem;
}

.inspector-heading {
  align-items: center;
}

.run-state {
  gap: 0.3125rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.run-state.completed {
  color: var(--teal-dark);
}

.run-state.completed i {
  background: var(--teal);
}

.run-state.failed {
  color: var(--agent-danger-text);
}

.run-state.failed i {
  background: var(--agent-danger-fill);
}

.run-progress {
  padding: 1rem 1.125rem 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.progress-top {
  justify-content: space-between;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.progress-top strong {
  color: var(--teal-dark);
  font-size: 0.8125rem;
}

.progress-top small {
  margin-left: auto;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.progress-track {
  height: 0.3125rem;
  margin-top: 0.5625rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--workspace-divider);
}

.progress-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--teal);
  transition: width 0.25s ease;
}

.run-progress p {
  overflow: hidden;
  margin: 0.5625rem 0 0;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-stage {
  margin-top: 0.75rem;
  padding: 0.625rem 0.6875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-raised);
}

.current-stage.running {
  border-color: var(--agent-accent-border);
  background: var(--agent-accent-surface);
}

.current-stage-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.current-stage-heading span {
  flex: 0 0 auto;
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.current-stage-heading strong {
  overflow: hidden;
  color: var(--workspace-text);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-stage p {
  margin: 0.3125rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.5;
  white-space: normal;
}

.current-stage-live {
  display: flex;
  align-items: center;
  gap: 0.3125rem;
  margin-top: 0.375rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.current-stage-live i,
.live-activity-topline::before {
  display: inline-block;
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 13%, transparent);
  content: "";
  animation: activity-pulse 1.5s ease-in-out infinite;
}

.current-stage small {
  display: block;
  margin-top: 0.375rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.live-activity {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin: 0.625rem 1.125rem 0;
  padding: 0.6875rem 0.75rem;
  border: 0.0625rem solid var(--agent-accent-border);
  border-radius: 0.625rem;
  background: linear-gradient(
    90deg,
    var(--agent-live-gradient-start),
    var(--agent-live-gradient-end)
  );
  box-shadow: 0 0.375rem 1.125rem
    color-mix(in oklab, var(--teal) 7%, transparent);
}

.live-activity-icon {
  display: grid;
  width: 1.75rem;
  height: 1.75rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5rem;
  background: var(--agent-accent-surface-strong);
  color: var(--teal-dark);
}

.live-activity-copy {
  min-width: 0;
  flex: 1;
}

.live-activity-topline {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.live-activity-topline em {
  padding: 0.125rem 0.3125rem;
  border-radius: 999px;
  background: var(--agent-accent-surface-strong);
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-style: normal;
}

.live-activity-copy strong {
  display: block;
  margin-top: 0.1875rem;
  overflow: hidden;
  color: var(--workspace-text);
  font-size: 0.8125rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-activity-copy p {
  margin: 0.1875rem 0 0;
  overflow: hidden;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-activity-next {
  max-width: 10rem;
  flex: 0 0 auto;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  line-height: 1.45;
  text-align: right;
}

@keyframes activity-pulse {
  0%,
  100% {
    opacity: 0.55;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.05);
  }
}

.context-panel {
  padding: 0.875rem 1.125rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  background: color-mix(in oklab, var(--teal) 3%, var(--surface));
}

.context-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.625rem;
}

.context-metrics span {
  display: grid;
  min-width: 0;
  gap: 0.125rem;
}

.context-metrics strong {
  color: var(--workspace-text);
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.context-metrics small {
  overflow: hidden;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-record-metrics {
  margin-top: 0.75rem;
  padding-top: 0.625rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}

.context-panel p {
  margin: 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.55;
}

.event-list {
  display: grid;
  gap: 0.125rem;
  padding: 0.875rem 1.125rem;
  overflow-y: auto;
}

.event-list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.event-list-heading strong {
  color: var(--teal-dark);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.event-item {
  position: relative;
  display: flex;
  gap: 0.5625rem;
  padding: 0.5rem 0;
}

.event-item:not(:last-child)::after {
  position: absolute;
  top: 1.75rem;
  bottom: -0.125rem;
  left: 0.5rem;
  border-left: 0.0625rem dashed var(--workspace-border);
  content: "";
}

.event-icon {
  position: relative;
  z-index: 1;
  display: grid;
  width: 1.125rem;
  height: 1.125rem;
  flex: 0 0 auto;
  place-items: center;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 50%;
  background: var(--surface);
  color: var(--workspace-subtle);
}

.event-item.completed .event-icon {
  border-color: var(--agent-accent-border);
  background: var(--agent-accent-surface-soft);
  color: var(--teal-dark);
}

.event-item.running .event-icon {
  border-color: var(--agent-accent-border);
  background: var(--agent-accent-surface-strong);
  color: var(--teal-dark);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 12%, transparent);
}

.event-copy {
  min-width: 0;
  flex: 1;
}

.event-copy > div {
  justify-content: space-between;
  gap: 0.375rem;
}

.event-copy strong {
  overflow: hidden;
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-copy small {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.event-copy p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.5;
}

.event-empty,
.inspector-empty {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.process-review-section {
  padding: 0.625rem 1.125rem 0.75rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}

.process-review-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.375rem;
  padding: 0.125rem 0;
  border: 0;
  background: transparent;
  color: var(--workspace-muted);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.process-review-toggle > span {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 650;
}

.process-review-toggle > span svg {
  color: var(--teal-dark);
}

.process-review-toggle small {
  margin-left: auto;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.process-review-toggle > svg {
  color: var(--workspace-subtle);
  transition: transform 160ms ease;
}

.process-review-toggle > svg.open {
  transform: rotate(90deg);
}

.process-review-list {
  display: grid;
  gap: 0.125rem;
  margin-top: 0.625rem;
  max-height: min(30rem, 48vh);
  overflow-y: auto;
  padding: 0.625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-raised);
  scrollbar-gutter: stable;
}

.process-review-item {
  display: grid;
  grid-template-columns: 1.25rem 1.25rem minmax(0, 1fr);
  align-items: start;
  gap: 0.375rem;
  padding: 0.375rem 0;
}

.process-review-index {
  padding-top: 0.125rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
}

.process-review-icon {
  display: grid;
  width: 1.125rem;
  height: 1.125rem;
  place-items: center;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 50%;
  color: var(--workspace-subtle);
}

.process-review-item.completed .process-review-icon {
  border-color: var(--agent-accent-border);
  background: var(--agent-accent-surface-soft);
  color: var(--teal-dark);
}

.process-review-item.running .process-review-icon {
  border-color: var(--agent-accent-border);
  background: var(--agent-accent-surface-strong);
  color: var(--teal-dark);
  animation: activity-pulse 1.5s ease-in-out infinite;
}

.process-review-item > div {
  min-width: 0;
}

.process-review-item strong {
  display: block;
  overflow: hidden;
  color: var(--workspace-text);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.process-review-item small {
  display: block;
  margin-top: 0.125rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.process-review-item p {
  margin: 0.1875rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.45;
}

.process-review-empty,
.process-review-note {
  margin: 0.25rem 0 0;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  line-height: 1.45;
}

.process-review-note {
  padding-top: 0.375rem;
  border-top: 0.0625rem solid var(--workspace-divider);
}

.inspector-section {
  padding: 0.875rem 1.125rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  overflow-y: auto;
}

.inspector-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.625rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.inspector-section-title strong {
  color: var(--teal-dark);
  font-size: 0.8125rem;
}

.citation-card {
  display: grid;
  width: 100%;
  gap: 0.25rem;
  margin-top: 0.4375rem;
  padding: 0.625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-raised);
  text-align: left;
}

.citation-card:hover {
  border-color: var(--teal);
}

.citation-card-top {
  gap: 0.25rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
}

.citation-card strong,
.citation-card small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-card strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}

.citation-card small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.inspector-footer {
  gap: 0.375rem;
  margin-top: auto;
  padding: 0.75rem 1.125rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  line-height: 1.45;
}

.inspector-footer svg {
  flex: 0 0 auto;
  color: var(--teal-dark);
}

/* Keep the chat shell fixed while the message stream and inspector scroll locally. */
.agent-workspace {
  height: min(68rem, calc(100dvh - 10rem));
  flex: 1 1 0;
  min-height: 0;
}

.agent-conversation {
  position: relative;
  height: 100%;
  min-height: 0;
}

.agent-inspector {
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.agent-inspector .event-list {
  flex: 0 0 auto;
  /* Let the inspector's own scrollbar reveal every recorded stage. */
  max-height: none;
  overflow: visible;
  scrollbar-gutter: stable;
}

.conversation-scroll {
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.composer-wrap {
  position: sticky;
  bottom: 0;
  z-index: 4;
  flex: 0 0 auto;
  box-shadow: 0 -0.75rem 1.75rem
    color-mix(in oklab, var(--surface) 88%, transparent);
}

.message-attachments {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  width: min(100%, 36rem);
}

.attachment-card {
  display: grid;
  grid-template-columns: 2.125rem minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  padding: 0.5rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5625rem;
  background: var(--surface-raised);
}

.attachment-media {
  display: grid;
  width: 2.125rem;
  height: 2.125rem;
  place-items: center;
  overflow: hidden;
  border-radius: 0.375rem;
  background: #eaf5f3;
}

.attachment-media img,
.attachment-media video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.attachment-media audio {
  width: 16rem;
  max-width: 100%;
  height: 2rem;
}

.attachment-media.pdf-media {
  width: 5rem;
  height: 4rem;
}

.attachment-media.pdf-media iframe {
  width: 100%;
  height: 100%;
  border: 0;
}

.attachment-icon {
  display: grid;
  width: 2.125rem;
  height: 2.125rem;
  place-items: center;
  border-radius: 0.375rem;
  background: #edf5ff;
  color: #6076c5;
}

.attachment-video .attachment-icon {
  color: #bb6c52;
  background: #fff0ea;
}
.attachment-audio .attachment-icon {
  color: #8c68bf;
  background: #f3ecff;
}
.attachment-pdf .attachment-icon {
  color: #b45b49;
  background: #fff0ea;
}
.attachment-spreadsheet .attachment-icon {
  color: #4c976f;
  background: #eaf8ef;
}
.attachment-presentation .attachment-icon {
  color: #c17a3b;
  background: #fff3e6;
}

.attachment-copy {
  display: grid;
  min-width: 0;
  gap: 0.1875rem;
}

.attachment-copy strong,
.attachment-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-copy strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.attachment-copy small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.attachment-open {
  padding: 0.25rem 0.375rem;
  border-radius: 0.3125rem;
  color: var(--teal-dark);
  font-size: 0.75rem;
  text-decoration: none;
}

.attachment-open:hover {
  background: #e6f7f3;
}

.attachment-dropdown {
  width: min(100%, 36rem);
}

.attachment-dropdown.is-single > .message-attachments {
  margin-top: 0;
}

.attachment-dropdown-summary {
  display: flex;
  width: fit-content;
  align-items: center;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
  padding: 0.375rem 0.5rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  background: var(--surface-raised);
  color: var(--workspace-muted);
  cursor: pointer;
  list-style: none;
  font-size: 0.75rem;
}

.attachment-dropdown-summary::-webkit-details-marker {
  display: none;
}
.attachment-dropdown-summary > span {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}
.attachment-dropdown-summary strong {
  min-width: 1rem;
  color: var(--teal-dark);
  text-align: center;
}
.attachment-dropdown-summary > svg:last-child {
  transition: transform 160ms ease;
}
.attachment-dropdown[open] > .attachment-dropdown-summary > svg:last-child {
  transform: rotate(90deg);
}
.attachment-dropdown-summary:hover {
  border-color: var(--teal);
  color: var(--teal-dark);
}

.message-citations {
  width: min(100%, 36rem);
  align-items: stretch;
  flex-direction: column;
  gap: 0.375rem;
}

.message-citations button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.125rem 0.5rem;
  width: 100%;
  max-width: none;
  align-items: center;
  text-align: left;
}

.message-citations button span,
.message-citations button small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-citations button span {
  grid-column: 1;
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.message-citations button small {
  grid-column: 1;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}
.message-citations button > svg {
  grid-column: 2;
  grid-row: 1 / span 2;
}

.composer-tools > span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.composer-tools > span svg {
  color: var(--teal-dark);
}

.pending-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
}

.pending-attachment {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  max-width: 15rem;
  padding: 0.375rem 0.4375rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  background: var(--surface-raised);
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.pending-attachment span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pending-attachment button {
  display: grid;
  width: 1.125rem;
  height: 1.125rem;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 0.25rem;
  background: transparent;
  color: var(--workspace-subtle);
  cursor: pointer;
}

.pending-attachment button:hover {
  background: #fff0f0;
  color: #b65353;
}

.composer-tools {
  display: flex;
  align-items: center;
  gap: 0.5625rem;
  min-width: 0;
}

.composer-tool-button {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  padding: 0.3125rem 0.4375rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  background: var(--surface);
  color: var(--workspace-muted);
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}

.composer-tool-button:hover {
  border-color: var(--teal);
  color: var(--teal-dark);
}

.event-meta {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  flex: 0 0 auto;
}

.event-meta em {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
  font-style: normal;
}

.citation-card p {
  display: -webkit-box;
  margin: 0.125rem 0 0;
  overflow: hidden;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.citation-card-open {
  display: grid;
  width: 100%;
  gap: 0.25rem;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.citation-import-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  justify-self: start;
  margin-top: 0.25rem;
  padding: 0.25rem 0.375rem;
  border: 0.0625rem solid
    color-mix(in oklab, var(--teal) 26%, var(--workspace-border));
  border-radius: 0.3125rem;
  background: color-mix(in oklab, var(--teal) 7%, var(--surface));
  color: var(--teal-dark);
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}

.citation-import-button:hover:not(:disabled) {
  border-color: var(--teal);
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
}

.citation-import-button:disabled {
  cursor: default;
  opacity: 0.72;
}

@media (max-width: 75rem) {
  .agent-config-card {
    align-items: flex-start;
    grid-template-columns: minmax(10rem, 0.72fr) minmax(0, 2.28fr);
  }

  .agent-workspace {
    grid-template-columns: 13rem minmax(30rem, 1fr) 17rem;
  }

  .agent-config-items {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .agent-config-item:nth-child(3),
  .agent-config-item:nth-child(4) {
    border-top: 0.0625rem solid var(--workspace-divider);
  }

  .agent-config-item:nth-child(3) {
    border-left: 0;
  }

  .agent-inspector {
    grid-column: auto;
    min-height: 0;
    max-height: none;
  }

  .agent-inspector .event-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 68.75rem) and (min-width: 47.51rem) {
  .agent-workspace {
    grid-template-columns: 13rem minmax(0, 1fr);
  }

  .agent-inspector {
    grid-column: 1 / -1;
    min-height: 30rem;
    max-height: min(34rem, calc(100dvh - 8rem));
  }

  .agent-inspector .event-list {
    max-height: 12rem;
    overflow-y: auto;
  }
}

@media (max-width: 47.5rem) {
  .agent-config-card {
    gap: 0.75rem;
    padding: 0.75rem;
    grid-template-columns: 1fr;
  }

  .agent-config-items {
    grid-template-columns: 1fr;
  }

  .agent-config-item {
    border-top: 0.0625rem solid var(--workspace-divider);
    border-left: 0;
  }

  .agent-config-item:first-child {
    border-top: 0;
  }

  .agent-workspace {
    display: flex;
    height: auto;
    min-height: 0;
    flex-direction: column;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  .agent-thread-panel {
    flex: 0 0 13rem;
    min-height: 13rem;
  }

  .thread-list {
    max-height: 13rem;
  }

  .agent-conversation {
    flex: 0 0 min(44rem, calc(100dvh - 8rem));
    min-height: 42rem;
  }

  .conversation-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .conversation-meta {
    padding-left: 2.75rem;
  }

  .live-activity {
    align-items: flex-start;
  }

  .live-activity-next {
    display: none;
  }

  .conversation-scroll {
    min-height: 27rem;
  }

  .agent-inspector {
    flex: 0 0 min(30rem, calc(100dvh - 6rem));
    max-height: none;
  }

  .agent-inspector .event-list {
    grid-template-columns: 1fr;
  }

  .message-row.user .message-body,
  .message-row.assistant .message-body {
    max-width: calc(100% - 2.25rem);
  }

  .composer-bottom > span {
    max-width: 12rem;
    line-height: 1.4;
  }

  .agent-workspace {
    height: auto;
  }

  .agent-conversation {
    height: min(44rem, calc(100dvh - 8rem));
    min-height: 34rem;
  }

  .message-attachments {
    grid-template-columns: 1fr;
  }

  .composer-tools {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.3125rem;
  }
}
.workspace-shortcuts {
  display: grid;
  grid-template-columns: minmax(12rem, 0.82fr) minmax(0, 3.18fr);
  align-items: center;
  gap: 0.75rem;
  flex: 0 0 auto;
  padding: 0.75rem;
  border-bottom: 0.0625rem solid var(--workspace-border);
  background: linear-gradient(
    110deg,
    color-mix(in oklab, var(--teal) 6%, var(--surface)),
    var(--surface)
  );
}

.shortcut-intro {
  display: grid;
  gap: 0.1875rem;
}

.shortcut-intro strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}

.shortcut-intro small {
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.45;
}

.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.375rem;
}

.shortcut-card {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.4375rem;
  padding: 0.5625rem 0.5rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface);
  color: var(--workspace-muted);
  text-decoration: none;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease;
}

.shortcut-card:hover,
.shortcut-card.active {
  border-color: color-mix(in oklab, var(--teal) 45%, var(--workspace-border));
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  color: var(--workspace-text);
}

.shortcut-card > svg {
  flex: 0 0 auto;
  color: var(--teal-dark);
}

.shortcut-card span {
  display: grid;
  min-width: 0;
  gap: 0.125rem;
}

.shortcut-card strong,
.shortcut-card small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shortcut-card strong {
  color: inherit;
  font-size: 0.75rem;
}

.shortcut-card small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

@media (max-width: 75rem) {
  .workspace-shortcuts {
    grid-template-columns: 1fr;
  }

  .shortcut-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 47.5rem) {
  .shortcut-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .thread-delete {
    opacity: 1;
  }
}
/* Inline source markers keep citations attached to the claim that uses them. */
.message-bubble .inline-citation {
  display: inline-flex;
  align-items: center;
  margin: 0 0.1rem;
  padding: 0.05rem 0.25rem;
  border: 0.0625rem solid
    color-mix(in oklab, var(--teal) 42%, var(--workspace-border));
  border-radius: 0.25rem;
  background: color-mix(in oklab, var(--teal) 12%, var(--surface-raised));
  color: var(--teal-dark);
  font: inherit;
  font-size: 0.82em;
  font-weight: 700;
  line-height: 1.35;
  cursor: pointer;
}

.message-bubble .inline-citation:hover,
.message-bubble .inline-citation:focus-visible {
  border-color: var(--teal);
  background: color-mix(in oklab, var(--teal) 22%, var(--surface-raised));
  outline: none;
}

.message-citations {
  display: block;
  width: min(100%, 36rem);
  margin-top: 0.125rem;
}

.message-citations-summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3125rem 0.125rem;
  color: var(--workspace-muted);
  cursor: pointer;
  list-style: none;
}

.message-citations-summary::-webkit-details-marker,
.citation-inspector-summary::-webkit-details-marker {
  display: none;
}

.message-citations-summary > small {
  margin-left: auto;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.message-citations-summary > svg {
  color: var(--teal-dark);
  transition: transform 160ms ease;
}

.message-citations[open] .message-citations-summary > svg {
  transform: rotate(90deg);
}

.message-citation-list {
  display: grid;
  gap: 0.25rem;
  padding: 0.125rem 0 0.25rem 0.125rem;
}

.message-citation-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.25rem;
}

.message-citation-list button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.125rem 0.5rem;
  width: 100%;
  align-items: center;
  padding: 0.375rem 0.4375rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.375rem;
  background: var(--surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.message-citation-row > button:first-child {
  min-width: 0;
}

.message-citation-row > .citation-save-mini {
  display: inline-flex;
  width: auto;
  min-width: 6.25rem;
  grid-template-columns: none;
  grid-column: auto;
  grid-row: auto;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  padding-inline: 0.5rem;
  color: var(--teal-dark);
  font-size: 0.6875rem;
  white-space: nowrap;
}

.message-citation-row > .citation-save-mini:hover:not(:disabled) {
  background: var(--surface-soft);
}

.message-citation-row > .citation-save-mini:disabled {
  cursor: default;
  opacity: 0.65;
}

.message-citation-list button:hover {
  border-color: var(--teal);
  background: var(--surface-soft);
}

.message-citation-list button span,
.message-citation-list button small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-citation-list button span {
  grid-column: 1;
  color: var(--workspace-text);
  font-size: 0.75rem;
}

.message-citation-list button small {
  grid-column: 1;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.message-citation-list button > svg {
  grid-column: 2;
  grid-row: 1 / span 2;
}

.citation-inspector > summary {
  cursor: pointer;
  list-style: none;
}

.citation-inspector-summary {
  gap: 0.375rem;
  margin-bottom: 0;
}

.citation-inspector-summary > span:first-child,
.citation-summary-count {
  display: inline-flex;
  align-items: center;
}

.citation-inspector-summary > span:first-child {
  gap: 0.25rem;
}

.citation-summary-count {
  gap: 0.375rem;
  margin-left: auto;
}

.citation-summary-count svg {
  color: var(--teal-dark);
  transition: transform 160ms ease;
}

.citation-inspector[open] .citation-summary-count svg {
  transform: rotate(90deg);
}

.citation-inspector .citation-list {
  display: grid;
  gap: 0.4375rem;
  max-height: 16rem;
  margin-top: 0.625rem;
  overflow-y: auto;
}

.citation-inspector .citation-card {
  margin-top: 0;
}
.run-timing {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  margin: 0.625rem 0 0.25rem;
  padding: 0.5rem 0;
  border-top: 0.0625rem solid var(--workspace-divider);
  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.run-timing span {
  display: grid;
  gap: 0.125rem;
  min-width: 0;
}

.run-timing small {
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.run-timing strong {
  overflow: hidden;
  color: var(--teal-dark);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.token-usage-status {
  display: flex;
  align-items: center;
  gap: 0.3125rem;
  margin: 0.5rem 0 0;
  color: var(--workspace-subtle);
  font-size: 0.75rem;
}

.token-status-dot {
  width: 0.375rem;
  height: 0.375rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--workspace-subtle);
}

.token-usage-status:has(.token-status-dot) .token-status-dot {
  background: var(--teal-dark);
}
</style>
