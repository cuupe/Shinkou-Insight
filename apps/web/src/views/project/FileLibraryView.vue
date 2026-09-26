<script setup lang="ts">
import {
  FileArchive,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  Music2,
  Presentation,
  Video,
  X,
} from "@lucide/vue";
import { computed, onMounted, ref, watch } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import StorageUsageCard from "@/components/common/StorageUsageCard.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { agentApi } from "@/api/agent";
import type {
  AgentAttachment,
  AgentAttachmentKind,
  AgentAttachmentUploadResponse,
} from "@/api/types";
import { useWorkspace } from "@/composables/useWorkspace";
import { formatDateTime } from "@/lib/utils";

const { workspaceId, projectId, notify } = useWorkspace();
const files = ref<AgentAttachment[]>([]);
const loading = ref(false);
const previewOpen = ref(false);
const previewFile = ref<AgentAttachment | null>(null);
const previewContent = ref("");
const previewLoading = ref(false);
const searchQuery = ref("");

const visibleFiles = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return files.value;
  return files.value.filter((file) => file.name.toLowerCase().includes(query));
});

const previewIsImage = computed(() => previewFile.value?.kind === "image");
const previewIsPdf = computed(() => previewFile.value?.kind === "pdf");
const previewIsDocument = computed(() =>
  ["document", "spreadsheet", "presentation"].includes(
    previewFile.value?.kind || "",
  ),
);

function normalizeFile(item: AgentAttachmentUploadResponse): AgentAttachment {
  return {
    id: String(item.uploadId),
    uploadId: item.uploadId,
    name: item.name,
    kind: item.kind,
    mimeType: item.mimeType,
    size: formatBytes(item.size),
    url: item.url,
    createdAt: item.createdAt,
  };
}

function formatBytes(value: number) {
  if (!value) return "0 KB";
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function fileIcon(kind: AgentAttachmentKind) {
  return (
    {
      image: ImageIcon,
      video: Video,
      audio: Music2,
      pdf: FileText,
      document: FileText,
      spreadsheet: FileSpreadsheet,
      presentation: Presentation,
      file: FileArchive,
    }[kind] || FileArchive
  );
}

function fileKindLabel(kind: AgentAttachmentKind) {
  return (
    {
      image: "图片",
      video: "视频",
      audio: "音频",
      pdf: "PDF 文档",
      document: "文档",
      spreadsheet: "表格",
      presentation: "演示文稿",
      file: "其他文件",
    }[kind] || "文件"
  );
}

function canPreview(file: AgentAttachment) {
  return ["image", "pdf", "document", "spreadsheet", "presentation"].includes(
    file.kind,
  );
}

function isExternalMedia(file: AgentAttachment) {
  return file.kind === "video" || file.kind === "audio";
}

async function loadFiles() {
  if (projectId.value <= 0) return;
  loading.value = true;
  try {
    const remoteFiles = await agentApi.listAttachments(
      workspaceId.value,
      projectId.value,
    );
    files.value = remoteFiles.map(normalizeFile);
  } catch (error) {
    notify(error instanceof Error ? error.message : "文件库加载失败");
  } finally {
    loading.value = false;
  }
}

async function openPreview(file: AgentAttachment) {
  if (!canPreview(file) || !file.url) return;
  previewFile.value = file;
  previewContent.value = "";
  previewOpen.value = true;
  if (file.kind === "image" || file.kind === "pdf") return;

  previewLoading.value = true;
  try {
    const result = await agentApi.previewAttachment(
      workspaceId.value,
      projectId.value,
      String(file.uploadId || file.id),
    );
    previewContent.value = result.content || "该文档没有可提取的文本预览。";
  } catch {
    previewContent.value =
      "该格式暂时无法生成文本预览，请使用“在线打开”查看原文件。";
  } finally {
    previewLoading.value = false;
  }
}

function closePreview() {
  previewOpen.value = false;
  previewFile.value = null;
  previewContent.value = "";
}

onMounted(loadFiles);
watch(projectId, loadFiles);
</script>

<template>
  <div class="file-library-page">
    <PageHeader
      eyebrow="PROJECT FILES"
      title="文件库"
      subtitle="保存聊天附件和生成文件，支持预览或打开原文件。"
    >
      <button class="button button-secondary" type="button" @click="loadFiles">
        刷新文件
      </button>
    </PageHeader>

    <StorageUsageCard />

    <section class="panel file-library-panel">
      <div class="file-library-toolbar">
        <div>
          <h2>项目文件</h2>
          <p>视频和音频不在对话内嵌播放，点击外置链接打开。</p>
        </div>
        <input
          v-model="searchQuery"
          type="search"
          placeholder="搜索文件名"
          aria-label="搜索文件名"
        />
      </div>

      <div v-if="loading" class="file-library-empty">
        <LoaderCircle class="spin" :size="22" />
        <span>正在加载文件库…</span>
      </div>
      <div v-else-if="!visibleFiles.length" class="file-library-empty">
        <FileArchive :size="24" />
        <strong>{{ searchQuery ? "没有匹配的文件" : "文件库暂时为空" }}</strong>
        <span>在 Agent 对话中粘贴或选择附件后，文件会出现在这里。</span>
      </div>
      <div v-else class="file-library-grid">
        <article
          v-for="file in visibleFiles"
          :key="file.id"
          class="file-library-card"
        >
          <div class="file-library-preview" :class="`kind-${file.kind}`">
            <img
              v-if="file.kind === 'image' && file.url"
              :src="file.url"
              :alt="file.name"
            />
            <component :is="fileIcon(file.kind)" v-else :size="28" />
          </div>
          <div class="file-library-copy">
            <strong :title="file.name">{{ file.name }}</strong>
            <small
              >{{ fileKindLabel(file.kind) }} ·
              {{ file.size || "未知大小" }}</small
            >
            <small>{{ formatDateTime(file.createdAt, "刚刚") }}</small>
          </div>
          <div class="file-library-actions">
            <button
              v-if="canPreview(file)"
              type="button"
              class="file-action-primary"
              @click="openPreview(file)"
            >
              预览
            </button>
            <a
              v-if="file.url"
              :href="file.url"
              target="_blank"
              rel="noreferrer"
            >
              {{ isExternalMedia(file) ? "外置播放" : "在线打开" }}
            </a>
            <span
              v-if="!canPreview(file) && !isExternalMedia(file)"
              class="file-action-muted"
              >暂不预览</span
            >
          </div>
        </article>
      </div>
    </section>

    <Dialog
      v-model:open="previewOpen"
      @update:open="(open) => !open && closePreview()"
    >
      <DialogContent class="file-preview-dialog">
        <DialogHeader>
          <DialogTitle>{{ previewFile?.name || "文件预览" }}</DialogTitle>
          <DialogDescription>
            {{ fileKindLabel(previewFile?.kind || "file") }} ·
            文件库附件，不参与知识库索引
          </DialogDescription>
        </DialogHeader>
        <div class="file-preview-stage">
          <img
            v-if="previewIsImage && previewFile?.url"
            :src="previewFile.url"
            :alt="previewFile.name"
          />
          <iframe
            v-else-if="previewIsPdf && previewFile?.url"
            :src="previewFile.url"
            :title="previewFile.name"
          />
          <div v-else-if="previewIsDocument" class="file-text-preview">
            <LoaderCircle v-if="previewLoading" class="spin" :size="22" />
            <pre v-else>{{ previewContent }}</pre>
          </div>
          <div v-else class="file-preview-fallback">
            <X :size="22" />
            <p>该文件类型不提供内嵌预览，请在线打开原文件。</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

<style scoped>
.file-library-page {
  display: grid;
  align-content: start;
  gap: 0.875rem;
  min-height: 0;
  padding-bottom: 0.5rem;
}

.file-library-panel {
  min-height: 0;
  padding: 1.25rem;
}

.file-library-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.875rem;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}

.file-library-toolbar h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 1rem;
  font-weight: 680;
  line-height: 1.3;
}

.file-library-toolbar p {
  max-width: 42rem;
  margin: 0.375rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.55;
}

.file-library-toolbar input {
  width: min(15rem, 42vw);
  padding: 0.5rem 0.625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;
  background: var(--surface-raised);
  color: var(--workspace-text);
}

.file-library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
  gap: 0.75rem;
}

.file-library-card {
  display: grid;
  grid-template-columns: 3.25rem minmax(0, 1fr);
  gap: 0.875rem;
  padding: 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.6875rem;
  background: var(--surface-raised);
}

.file-library-preview {
  display: grid;
  width: 3.25rem;
  height: 3.25rem;
  place-items: center;
  overflow: hidden;
  border-radius: 0.5rem;
  background: #edf5ff;
  color: #6076c5;
}

.file-library-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.file-library-preview.kind-video {
  background: #fff0ea;
  color: #bb6c52;
}
.file-library-preview.kind-audio {
  background: #f3ecff;
  color: #8c68bf;
}
.file-library-preview.kind-pdf {
  background: #fff0ea;
  color: #b45b49;
}

.file-library-copy {
  display: grid;
  min-width: 0;
  align-content: center;
  gap: 0.1875rem;
}

.file-library-copy strong,
.file-library-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-library-copy strong {
  display: -webkit-box;
  color: var(--workspace-text);
  font-size: 0.8125rem;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.file-library-copy small {
  display: block;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.4;
  white-space: nowrap;
}

.file-library-actions {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.25rem;
  padding-top: 0.625rem;
  border-top: 0.0625rem solid var(--workspace-border);
}

.file-library-actions button,
.file-library-actions a {
  padding: 0.3125rem 0.5rem;
  border: 0;
  border-radius: 0.375rem;
  background: transparent;
  color: var(--teal-dark);
  font-size: 0.75rem;
  text-decoration: none;
  cursor: pointer;
}

.file-library-actions button:hover,
.file-library-actions a:hover {
  background: #e6f7f3;
}
.file-action-muted {
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.file-library-empty {
  display: grid;
  min-height: 12rem;
  place-items: center;
  align-content: center;
  gap: 0.5rem;
  color: var(--workspace-muted);
  text-align: center;
}

.file-library-empty strong {
  color: var(--workspace-text);
}
.spin {
  animation: file-library-spin 1s linear infinite;
}
@keyframes file-library-spin {
  to {
    transform: rotate(360deg);
  }
}

.file-preview-dialog {
  max-width: min(72rem, calc(100vw - 2rem));
}
.file-preview-stage {
  display: grid;
  min-height: min(64vh, 38rem);
  place-items: center;
  overflow: hidden;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface-raised);
}
.file-preview-stage > img {
  max-width: 100%;
  max-height: 62vh;
  object-fit: contain;
}
.file-preview-stage > iframe {
  width: 100%;
  height: min(64vh, 38rem);
  border: 0;
}
.file-text-preview {
  width: 100%;
  height: min(64vh, 38rem);
  overflow: auto;
  padding: 1rem;
}
.file-text-preview pre {
  margin: 0;
  color: var(--workspace-text);
  font: inherit;
  white-space: pre-wrap;
  line-height: 1.65;
}
.file-preview-fallback {
  display: grid;
  gap: 0.5rem;
  place-items: center;
  color: var(--workspace-muted);
}
.file-preview-fallback p {
  margin: 0;
}

@media (max-width: 42rem) {
  .file-library-toolbar {
    flex-direction: column;
  }
  .file-library-toolbar input {
    width: 100%;
  }
}
</style>
