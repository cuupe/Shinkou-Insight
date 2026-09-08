<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronRight,
  Circle,
  Clock3,
  Cpu,
  Database,
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
  Video,
  Wrench,
  X,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { agentApi } from "@/api/agent";
import { settingsApi, type ProjectModelConfig } from "@/api/settings";
import { useAgentWorkspace } from "@/composables/useAgentWorkspace";
import type {
  AgentAttachment,
  AgentAttachmentKind,
  AgentEvent,
  AgentEventKind,
  AgentMessage,
} from "@/api/types";
import { useWorkspace } from "@/composables/useWorkspace";

const { notify, router, routeTo, workspaceId, projectId, allowWeb } = useWorkspace();
const {
  activeThread,
  threads,
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
} = useAgentWorkspace();
const conversationScroll = ref<HTMLElement | null>(null);
const attachmentInput = ref<HTMLInputElement | null>(null);
const pendingAttachments = ref<AgentAttachment[]>([]);
const modelOptions = ref<ProjectModelConfig[]>([]);
const selectedModelId = ref<number | string>("");
const selectedModelName = computed(
  () => modelOptions.value.find((model) => String(model.id) === String(selectedModelId.value))?.name || "使用项目默认模型",
);
const agentConfig = computed(() => ({
  allowWebSearch: allowWeb.value,
  maxResearchRounds: 3,
  topK: 8,
  retrievalMode: "HYBRID" as const,
  useReranker: true,
  outputLanguage: "zh-CN",
  ...(selectedModelId.value ? { modelConfigId: selectedModelId.value } : {}),
}));
const completedEvents = computed(
  () => events.value.filter((event) => event.status === "completed").length,
);
const progress = computed(() =>
  events.value.length ? Math.round((completedEvents.value / events.value.length) * 100) : 0,
);
const latestEvent = computed(() => events.value.at(-1));

onMounted(async () => {
  if (projectId.value <= 0) return;
  try {
    modelOptions.value = (await settingsApi.models.list(workspaceId.value, projectId.value)).filter((model) => model.enabled);
    // Empty means the backend applies the project default, including the
    // project creator's credential precedence.
    selectedModelId.value = "";
  } catch {
    notify("模型配置加载失败，将使用服务默认配置");
  }
});

const eventIcons = {
  plan: ListChecks,
  search: Search,
  tool: Wrench,
  evidence: FileCheck2,
  synthesis: Sparkles,
};

function eventIcon(kind: AgentEventKind) {
  return eventIcons[kind] || ListChecks;
}

function messageLines(message: AgentMessage) {
  return message.content.split(/\n+/).filter(Boolean);
}

function eventStatusLabel(event: AgentEvent) {
  if (event.status === "running") return "进行中";
  if (event.status === "failed") return "失败";
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
  if (file.type.startsWith("image/") || ["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(extension)) return "image";
  if (file.type.startsWith("video/") || ["mp4", "webm", "mov", "m4v"].includes(extension)) return "video";
  if (file.type.startsWith("audio/") || ["mp3", "wav", "m4a", "ogg", "aac"].includes(extension)) return "audio";
  if (file.type === "application/pdf" || extension === "pdf") return "pdf";
  if (["doc", "docx"].includes(extension)) return "document";
  if (["xls", "xlsx", "csv"].includes(extension)) return "spreadsheet";
  if (["ppt", "pptx"].includes(extension)) return "presentation";
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

function openCitation(citation: NonNullable<AgentMessage["citations"]>[number]) {
  if (citation.url) {
    window.open(citation.url, "_blank", "noopener,noreferrer");
    return;
  }
  notify(`${citation.source}${citation.pageNumber ? ` · 第 ${citation.pageNumber} 页` : ""}`);
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
        const uploaded = await agentApi.uploadAttachment(workspaceId.value, projectId.value, attachment.file);
        return {
          ...attachment,
          uploadId: uploaded.uploadId,
          url: uploaded.url,
          file: undefined,
          size: formatFileSize(uploaded.size),
        };
      }),
    );
    void sendMessage(draft.value.trim() || "请分析我上传的附件。", uploadedAttachments, agentConfig.value);
  } catch (error) {
    pendingAttachments.value.unshift(...attachments);
    notify(error instanceof Error ? error.message : "附件上传失败，请重试");
  }
}

function handleCreateThread() {
  createThread();
  notify("已创建新的 Agent 对话");
}

function openSettings(routeName: "settings-models" | "settings-tools" | "project-assets") {
  router.push(routeTo(routeName));
}

function scrollConversationToBottom() {
  nextTick(() => {
    const element = conversationScroll.value;
    if (element) element.scrollTop = element.scrollHeight;
  });
}

watch(messages, scrollConversationToBottom, { deep: true });
watch(events, scrollConversationToBottom, { deep: true });
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / AGENT"
    title="Agent 对话"
    subtitle="和 Agent 一起检索、核对证据，并沿着执行过程得到可追溯的回答"
  >
    <template #action>
      <button class="button button-primary" type="button" @click="handleCreateThread">
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
    accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.ppt,.pptx,.txt,.md"
    @change="handleFilesSelected"
  />

  <div class="agent-shell">
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
          <Cpu :size="15" />
          <span><small>本次模型</small><strong>{{ selectedModelName }}</strong><select v-model="selectedModelId" aria-label="选择本次对话模型">
            <option value="">使用项目默认模型</option>
            <option v-for="model in modelOptions" :key="model.id" :value="model.id">{{ model.name }}</option>
          </select></span>
          <button class="config-link-button" type="button" aria-label="管理模型配置" @click="openSettings('settings-models')"><ChevronRight :size="13" /></button>
        </div>
        <button class="agent-config-item" type="button" @click="openSettings('project-assets')">
          <Database :size="15" />
          <span><small>知识范围</small><strong>当前项目资料</strong></span>
          <ChevronRight :size="13" />
        </button>
        <div class="agent-config-item agent-config-tool">
          <Link2 :size="15" />
          <span><small>工具策略</small><strong>按需调用，写入需确认</strong></span>
          <label class="inline-switch" title="允许本次运行联网搜索"><input v-model="allowWeb" type="checkbox" aria-label="允许本次运行联网搜索" /><span /></label>
          <button class="config-link-button" type="button" aria-label="管理工具配置" @click="openSettings('settings-tools')"><ChevronRight :size="13" /></button>
        </div>
      </div>
    </section>

    <div class="agent-workspace">
    <aside class="panel agent-thread-panel">
      <div class="agent-panel-heading">
        <div>
          <span class="agent-kicker">CONVERSATIONS</span>
          <h2>项目对话</h2>
        </div>
        <button class="mini-button" type="button" aria-label="新建对话" @click="handleCreateThread">
          <Plus :size="15" />
        </button>
      </div>
      <div class="thread-list">
        <button
          v-for="thread in threads"
          :key="thread.id"
          class="thread-item"
          :class="{ active: activeThread.id === thread.id }"
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
      </div>
    </aside>

    <section class="panel agent-conversation" aria-label="Agent 对话区域">
      <header class="conversation-header">
        <div class="conversation-title">
          <span class="agent-avatar"><Bot :size="17" /></span>
          <div>
            <strong>{{ activeThread.title }}</strong>
            <span><i :class="{ live: isRunning }" />{{ isRunning ? "Agent 正在工作" : "对话已就绪" }}</span>
          </div>
        </div>
        <div class="conversation-meta">
          <span v-if="activeThread.runId">运行 {{ activeThread.runId }}</span>
          <span><Clock3 :size="13" />{{ activeThread.updatedAt }}</span>
        </div>
      </header>

      <div ref="conversationScroll" class="conversation-scroll">
        <div v-if="!messages.length" class="conversation-empty">
          <span class="empty-orb"><Sparkles :size="22" /></span>
          <h2>从一个问题开始</h2>
          <p>描述你需要研究、比较或核对的内容，Agent 会把过程和证据一起展示出来。</p>
        </div>

        <div v-for="message in messages" :key="message.id" class="message-row" :class="message.role">
          <div v-if="message.role === 'assistant'" class="message-avatar"><Bot :size="15" /></div>
          <div class="message-body">
            <div class="message-meta">
              <strong>{{ message.role === "assistant" ? "Shinkou Agent" : "你" }}</strong>
              <span>{{ message.createdAt }}</span>
              <span v-if="message.status === 'streaming'" class="streaming-label"><i />生成中</span>
            </div>
            <div class="message-bubble">
              <p v-for="line in messageLines(message)" :key="line">{{ line }}</p>
              <span v-if="message.status === 'streaming'" class="typing-caret" />
            </div>
            <div v-if="message.media?.length" class="message-media" aria-label="Agent 输出媒体">
              <figure v-for="media in message.media" :key="media.id" class="message-media-card">
                <img v-if="media.kind === 'image'" :src="media.url" :alt="media.name" />
                <video v-else controls preload="metadata" :src="media.url" :aria-label="media.name" />
                <figcaption>{{ media.name }}</figcaption>
              </figure>
            </div>
            <details
              v-if="message.attachments?.length"
              class="attachment-dropdown"
              :class="{ 'is-single': message.attachments.length === 1 }"
              :open="message.attachments.length === 1"
            >
              <summary v-if="message.attachments.length > 1" class="attachment-dropdown-summary">
                <span><Paperclip :size="13" />文件</span><strong>{{ message.attachments.length }}</strong><ChevronRight :size="13" />
              </summary>
              <div class="message-attachments">
                <article
                  v-for="attachment in message.attachments"
                  :key="attachment.id"
                  class="attachment-card"
                  :class="`attachment-${attachment.kind}`"
                >
                  <div v-if="attachment.kind === 'image' && (attachment.previewUrl || attachment.url)" class="attachment-media image-media">
                    <img :src="attachment.previewUrl || attachment.url" :alt="attachment.name" />
                  </div>
                  <div v-else-if="attachment.kind === 'video' && attachment.url" class="attachment-media">
                    <video controls preload="metadata" :src="attachment.url" :aria-label="attachment.name" />
                  </div>
                  <div v-else-if="attachment.kind === 'audio' && attachment.url" class="attachment-media audio-media">
                    <audio controls :src="attachment.url" :aria-label="attachment.name" />
                  </div>
                  <div v-else-if="attachment.kind === 'pdf' && attachment.url" class="attachment-media pdf-media">
                    <iframe :src="attachment.url" :title="attachment.name" />
                  </div>
                  <div v-else class="attachment-icon"><component :is="attachmentIcon(attachment.kind)" :size="19" /></div>
                  <div class="attachment-copy">
                    <strong :title="attachment.name">{{ attachment.name }}</strong>
                    <small>{{ attachmentLabel(attachment.kind) }} · {{ attachment.size || "待上传" }}</small>
                  </div>
                  <a v-if="attachment.url" class="attachment-open" :href="attachment.previewUrl || attachment.url" target="_blank" rel="noreferrer">在线打开</a>
                </article>
              </div>
            </details>
            <div v-if="message.role === 'assistant' && message.citations?.length" class="message-citations">
              <span class="citation-label"><FileSearch :size="13" />引用 {{ message.citations.length }}</span>
              <button v-for="citation in message.citations" :key="citation.id" type="button" @click="openCitation(citation)">
                <span>{{ citation.title }}</span><small>{{ citation.source }}</small><ChevronRight :size="12" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <footer class="composer-wrap">
        <div v-if="pendingAttachments.length" class="pending-attachments" aria-label="待发送附件">
          <div v-for="attachment in pendingAttachments" :key="attachment.id" class="pending-attachment">
            <component :is="attachmentIcon(attachment.kind)" :size="14" />
            <span :title="attachment.name">{{ attachment.name }}</span>
            <button type="button" :aria-label="`移除附件 ${attachment.name}`" @click="removePendingAttachment(attachment.id)"><X :size="13" /></button>
          </div>
        </div>
        <form class="composer" @submit.prevent="handleSubmit">
          <textarea
            v-model="draft"
            rows="3"
            :disabled="isRunning"
            placeholder="问问 Agent：比较方案、查找证据或整理下一步…"
            aria-label="输入给 Agent 的问题"
            @keydown.enter.exact.prevent="handleSubmit"
          />
          <div class="composer-bottom">
            <div class="composer-tools">
              <button type="button" class="composer-tool-button" @click="openAttachmentPicker"><Paperclip :size="14" />添加附件</button>
              <span><Sparkles :size="13" />回答会附带执行过程和证据</span>
            </div>
            <button v-if="isRunning" class="button button-secondary button-sm" type="button" :disabled="cancelling" @click="stopRun">
              <Square :size="13" />{{ cancelling ? "正在暂停" : "暂停运行" }}
            </button>
            <button v-else class="button button-primary button-sm" type="submit">
              发送 <Send :size="14" />
            </button>
          </div>
        </form>
        <p v-if="composerError" class="composer-error" role="alert"><AlertCircle :size="14" />{{ composerError }}</p>
      </footer>
    </section>

    <aside class="panel agent-inspector">
      <div class="agent-panel-heading inspector-heading">
        <div>
          <span class="agent-kicker">EXECUTION</span>
          <h2>执行进度</h2>
        </div>
        <span class="run-state" :class="activeThread.status"><i />{{ isRunning ? "运行中" : activeThread.status === "failed" ? "失败" : "已完成" }}</span>
      </div>
      <div class="run-progress">
        <div class="progress-top"><span>执行进度</span><strong>{{ progress }}%</strong></div>
        <div class="progress-track"><i :style="{ width: `${progress}%` }" /></div>
        <p v-if="latestEvent">{{ latestEvent.status === "running" ? latestEvent.title : "本次运行已完成，可继续追问" }}</p>
        <p v-else>发送问题后，这里会显示 Agent 的实时执行过程</p>
      </div>

      <div class="event-list">
        <div v-for="event in events" :key="event.id" class="event-item" :class="event.status">
          <span class="event-icon"><component :is="eventIcon(event.kind)" :size="14" /></span>
          <div class="event-copy">
            <div><strong>{{ event.title }}</strong><span class="event-meta"><small>{{ eventStatusLabel(event) }}</small><em>{{ eventTimeLabel(event) }}</em></span></div>
            <p>{{ event.detail }}</p>
          </div>
        </div>
        <div v-if="!events.length" class="event-empty"><Circle :size="15" />等待下一次运行</div>
      </div>

      <div class="inspector-section">
        <div class="inspector-section-title"><span>证据引用</span><strong>{{ citations.length }}</strong></div>
        <button v-for="citation in citations" :key="citation.id" class="citation-card" type="button" @click="openCitation(citation)">
          <span class="citation-card-top"><FileSearch :size="13" />{{ citation.score ? `相关度 ${citation.score}` : "项目证据" }}</span>
          <strong>{{ citation.title }}</strong>
          <small>{{ citation.source }}</small>
          <p v-if="citation.quote">{{ citation.quote }}</p>
        </button>
        <p v-if="!citations.length" class="inspector-empty">运行后会自动收集引用证据。</p>
      </div>

      <div class="inspector-footer"><CheckCircle2 :size="14" />不会展示模型隐藏思维，仅展示可审计的执行事件。</div>
    </aside>
    </div>
  </div>
  </div>
</template>

<style scoped>
.agent-page {
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
  grid-template-columns: minmax(14rem, 0.7fr) minmax(0, 1.8fr);
  align-items: center;
  gap: 1rem;
  flex: 0 0 auto;
  padding: 0.6875rem 0.75rem;
  border: 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
  border-radius: 0;
  background: linear-gradient(110deg, color-mix(in oklab, var(--teal) 7%, var(--surface)), var(--surface));
}

.agent-config-intro,
.agent-config-item,
.agent-config-item span {
  display: flex;
  align-items: center;
}

.agent-config-intro {
  min-width: 0;
  flex: 0 0 auto;
  gap: 0.5625rem;
}

.config-intro-icon {
  display: grid;
  width: 2rem;
  height: 2rem;
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
  font-size: 0.6875rem;
}

.agent-config-intro small {
  margin-top: 0.1875rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}

.agent-config-items {
  display: grid;
  min-width: 0;
  flex: 1;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
}

.agent-config-item {
  min-width: 0;
  gap: 0.4375rem;
  padding: 0.4375rem 0.5625rem;
  border: 0.0625rem solid var(--workspace-divider);
  border-radius: 0.5rem;
  background: var(--surface-raised);
  color: var(--teal-dark);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease;
}

.agent-config-item:hover {
  border-color: var(--teal);
  background: var(--surface-soft);
}

.agent-config-item select {
  max-width: 10rem;
  border: 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.5625rem;
  outline: none;
}

.agent-config-model > span {
  gap: 0.0625rem;
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

.agent-config-item span {
  min-width: 0;
  flex: 1;
  align-items: flex-start;
  flex-direction: column;
  gap: 0.125rem;
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
  font-size: 0.5rem;
}

.agent-config-item strong {
  color: var(--workspace-text);
  font-size: 0.5625rem;
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
  height: auto;
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
  font-size: 0.5rem;
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
  gap: 0.5625rem;
  padding: 0.6875rem 0.5625rem;
  border: 0;
  border-radius: 0.5625rem;
  background: transparent;
  color: var(--workspace-muted);
  text-align: left;
  cursor: pointer;
  transition: background 0.16s ease, color 0.16s ease;
}

.thread-item:hover,
.thread-item.active {
  background: color-mix(in oklab, var(--teal) 9%, var(--surface));
  color: var(--workspace-text);
}

.thread-item.active {
  box-shadow: inset 0.125rem 0 0 var(--teal);
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
  font-size: 0.6875rem;
  font-weight: 650;
}

.thread-copy small {
  color: var(--workspace-subtle);
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
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
  font-size: 0.5rem;
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
  50% { opacity: 0; }
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
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
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
  font-size: 0.6875rem;
  line-height: 1.65;
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
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
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
  font-size: 0.6875rem;
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
  font-size: 0.5rem;
}

.composer-bottom > span svg {
  color: var(--teal-dark);
}

.composer-error {
  display: flex;
  align-items: center;
  gap: 0.3125rem;
  margin: 0.5rem 0 0;
  color: #c15b5b;
  font-size: 0.5625rem;
}

.inspector-heading {
  align-items: center;
}

.run-state {
  gap: 0.3125rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}

.run-state.completed {
  color: var(--teal-dark);
}

.run-state.completed i {
  background: var(--teal);
}

.run-state.failed {
  color: #c15b5b;
}

.run-state.failed i {
  background: #d76363;
}

.run-progress {
  padding: 1rem 1.125rem 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.progress-top {
  justify-content: space-between;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}

.progress-top strong {
  color: var(--teal-dark);
  font-size: 0.6875rem;
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
  font-size: 0.5625rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-list {
  display: grid;
  gap: 0.125rem;
  padding: 0.875rem 1.125rem;
  overflow-y: auto;
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
  border-color: #b7e9e1;
  background: #eaf9f6;
  color: var(--teal-dark);
}

.event-item.running .event-icon {
  border-color: #b7e9e1;
  background: #dff7f3;
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
  font-size: 0.625rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-copy small {
  flex: 0 0 auto;
  color: var(--workspace-subtle);
  font-size: 0.5rem;
}

.event-copy p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  line-height: 1.5;
}

.event-empty,
.inspector-empty {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--workspace-subtle);
  font-size: 0.5625rem;
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
  font-size: 0.5625rem;
}

.inspector-section-title strong {
  color: var(--teal-dark);
  font-size: 0.6875rem;
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
  cursor: pointer;
}

.citation-card:hover {
  border-color: var(--teal);
}

.citation-card-top {
  gap: 0.25rem;
  color: var(--teal-dark);
  font-size: 0.5rem;
}

.citation-card strong,
.citation-card small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-card strong {
  color: var(--workspace-text);
  font-size: 0.625rem;
}

.citation-card small {
  color: var(--workspace-muted);
  font-size: 0.5rem;
}

.inspector-footer {
  gap: 0.375rem;
  margin-top: auto;
  padding: 0.75rem 1.125rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-subtle);
  font-size: 0.5rem;
  line-height: 1.45;
}

.inspector-footer svg {
  flex: 0 0 auto;
  color: var(--teal-dark);
}

/* Keep the chat shell fixed while the message stream and inspector scroll locally. */
.agent-workspace {
  height: auto;
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
  max-height: min(24rem, 45vh);
  overflow-y: auto;
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
  box-shadow: 0 -0.75rem 1.75rem color-mix(in oklab, var(--surface) 88%, transparent);
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

.attachment-video .attachment-icon { color: #bb6c52; background: #fff0ea; }
.attachment-audio .attachment-icon { color: #8c68bf; background: #f3ecff; }
.attachment-pdf .attachment-icon { color: #b45b49; background: #fff0ea; }
.attachment-spreadsheet .attachment-icon { color: #4c976f; background: #eaf8ef; }
.attachment-presentation .attachment-icon { color: #c17a3b; background: #fff3e6; }

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

.attachment-copy strong { color: var(--workspace-text); font-size: 0.5625rem; }
.attachment-copy small { color: var(--workspace-muted); font-size: 0.5rem; }

.attachment-open {
  padding: 0.25rem 0.375rem;
  border-radius: 0.3125rem;
  color: var(--teal-dark);
  font-size: 0.5rem;
  text-decoration: none;
}

.attachment-open:hover { background: #e6f7f3; }

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
  font-size: 0.5625rem;
}

.attachment-dropdown-summary::-webkit-details-marker { display: none; }
.attachment-dropdown-summary > span { display: inline-flex; align-items: center; gap: 0.25rem; }
.attachment-dropdown-summary strong { min-width: 1rem; color: var(--teal-dark); text-align: center; }
.attachment-dropdown-summary > svg:last-child { transition: transform 160ms ease; }
.attachment-dropdown[open] > .attachment-dropdown-summary > svg:last-child { transform: rotate(90deg); }
.attachment-dropdown-summary:hover { border-color: var(--teal); color: var(--teal-dark); }

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

.message-citations button span { grid-column: 1; color: var(--workspace-text); font-size: 0.5625rem; }
.message-citations button small { grid-column: 1; color: var(--workspace-muted); font-size: 0.5rem; }
.message-citations button > svg { grid-column: 2; grid-row: 1 / span 2; }

.composer-tools > span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  color: var(--workspace-subtle);
  font-size: 0.5rem;
}

.composer-tools > span svg { color: var(--teal-dark); }

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
  font-size: 0.5625rem;
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

.pending-attachment button:hover { background: #fff0f0; color: #b65353; }

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
  font-size: 0.5625rem;
  cursor: pointer;
}

.composer-tool-button:hover { border-color: var(--teal); color: var(--teal-dark); }

.event-meta {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  flex: 0 0 auto;
}

.event-meta em {
  color: var(--workspace-subtle);
  font-size: 0.4375rem;
  font-style: normal;
}

.citation-card p {
  display: -webkit-box;
  margin: 0.125rem 0 0;
  overflow: hidden;
  color: var(--workspace-muted);
  font-size: 0.5rem;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

@media (max-width: 75rem) {
  .agent-config-card {
    align-items: flex-start;
    grid-template-columns: minmax(12rem, 0.75fr) minmax(0, 1.8fr);
  }

  .agent-workspace {
    grid-template-columns: 13rem minmax(30rem, 1fr) 17rem;
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
    max-height: 18rem;
  }

  .agent-inspector .event-list {
    max-height: 8rem;
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

  .conversation-scroll {
    min-height: 27rem;
  }

  .agent-inspector {
    flex: 0 0 18rem;
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
</style>
