<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileSearch,
  FileText,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldCheck,
} from "@lucide/vue";
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { assetDetailCopy } from "@/data/options";
import { useWorkspace } from "@/composables/useWorkspace";
import PageHeader from "@/components/common/PageHeader.vue";
import { assetsApi } from "@/api/assets";

const route = useRoute();
const {
  assets,
  router,
  routeTo,
  notify,
  retryAsset,
  statusClass,
  statusLabel,
  workspaceId,
  projectId,
} = useWorkspace();

const asset = computed(() =>
  assets.find((item) => item.id === String(route.params.assetId)) ?? {
    id: "",
    name: "",
    type: "",
    size: "—",
    uploader: "—",
    updated: "—",
    chunks: 0,
    progress: 0,
    status: "indexing" as const,
    reason: "",
  },
);
const hasAsset = computed(() => Boolean(asset.value.id));
const activeSection = ref<"preview" | "chunks" | "citations">("preview");
const activeChunk = ref(0);
const citationQuery = ref("");
const reindexing = ref(false);
const remoteContent = ref("");
const remoteChunks = ref<Record<string, unknown>[]>([]);

onMounted(async () => {
  try {
    const [content, chunks] = await Promise.all([
      assetsApi.content(
        workspaceId.value,
        projectId.value,
        String(route.params.assetId),
      ),
      assetsApi.chunks(
        workspaceId.value,
        projectId.value,
        String(route.params.assetId),
      ),
    ]);
    remoteContent.value = content;
    remoteChunks.value = chunks;
  } catch {
    notify("资产详情加载失败");
  }
});

const previewParagraphs = computed(() =>
  remoteContent.value
    ? [remoteContent.value]
    : [
        remoteChunks.value.length
          ? String(remoteChunks.value[0]?.content || "")
          : "暂无内容预览，资料完成解析后会展示原文内容。",
      ],
);
const previewTitle = computed(() =>
  asset.value?.name.replace(/\.[^.]+$/, "") || "",
);
const chunkRows = computed(() =>
  remoteChunks.value.map((chunk, index) => ({
    index,
    label: `Chunk ${String(index + 1).padStart(2, "0")}`,
    title: String(chunk.sectionTitle || `资料片段 ${index + 1}`),
    snippet: String(chunk.content || ""),
  })),
);
const activeChunkRow = computed(
  () => chunkRows.value[activeChunk.value] ?? chunkRows.value[0],
);
type AssetCitation = { title: string; source: string; text: string; score: string };
const assetCitations = computed<AssetCitation[]>(() => []);
const visibleCitations = computed(() => {
  const query = citationQuery.value.trim().toLowerCase();
  if (!query) return assetCitations.value;
  return assetCitations.value.filter((item) =>
    `${item.title} ${item.source} ${item.text}`.toLowerCase().includes(query),
  );
});
const statusDescription = computed(() => {
  if (asset.value.status === "indexed")
    return "资料已经完成解析和向量索引，可供 Agent 检索。";
  if (asset.value.status === "indexing")
    return "正在处理资料，完成后会自动开放给 Agent 检索。";
  return asset.value.reason || "索引失败，请重新提交处理。";
});
const indexSteps = computed(() => [
  { label: "上传原文件", state: "done" },
  {
    label: "解析文本内容",
    state:
      asset.value.status === "failed"
        ? "error"
        : asset.value.progress > 0
          ? "done"
          : "pending",
  },
  {
    label: "切片并建立索引",
    state:
      asset.value.status === "indexed"
        ? "done"
        : asset.value.status === "indexing"
          ? "active"
          : asset.value.status === "failed"
            ? "error"
            : "pending",
  },
]);

function goBack() {
  router.push(routeTo("project-assets"));
}

async function reindex() {
  if (!asset.value) return;
  if (reindexing.value) return;
  reindexing.value = true;
  try {
    await assetsApi.reindex(
      workspaceId.value,
      projectId.value,
      String(asset.value.id),
    );
  } catch (error) {
    notify(error instanceof Error ? error.message : "重新索引失败");
    reindexing.value = false;
    return;
  }
  activeSection.value = "preview";
  window.setTimeout(() => {
    reindexing.value = false;
  }, 900);
}

function downloadOriginal() {
  if (!asset.value) return;
  const text = remoteContent.value;
  if (!text) {
    notify("暂无可下载的原文内容，等资料解析完成后再试");
    return;
  }
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = previewTitle.value || asset.value.name;
  link.click();
  URL.revokeObjectURL(url);
}

function locateCitation(source: string) {
  activeSection.value = "citations";
  notify(`已定位到引用片段：${source}`);
}
</script>

<template>
  <button class="text-button back-button" type="button" @click="goBack">
    <ArrowLeft :size="15" />返回知识库
  </button>

  <template v-if="hasAsset">
    <PageHeader
    eyebrow="KNOWLEDGE / LIBRARY DETAIL"
    :title="asset.name"
    :subtitle="`${asset.type} · ${asset.size} · 上传者 ${asset.uploader}`"
  >
    <template #action>
      <div class="heading-actions">
        <button
          class="button button-secondary"
          type="button"
          @click="downloadOriginal"
        >
          <Download :size="15" />下载原文件
        </button>
        <button
          class="button button-primary"
          type="button"
          :disabled="reindexing"
          @click="reindex"
        >
          <RefreshCw :size="15" :class="{ 'spin-icon': reindexing }" />
          {{ reindexing ? "提交中" : "重新索引" }}
        </button>
      </div>
    </template>
    </PageHeader>
  <div v-if="false" class="detail-heading">
    <div class="asset-title">
      <span class="file-type large" :class="asset.type.toLowerCase()">
        <FileText :size="24" />
      </span>
      <div>
        <p class="eyebrow">KNOWLEDGE / LIBRARY DETAIL</p>
        <h1>{{ asset.name }}</h1>
        <p>{{ asset.type }} · {{ asset.size }} · 上传者 {{ asset.uploader }}</p>
      </div>
    </div>
    <div class="heading-actions">
      <button
        class="button button-secondary"
        type="button"
        @click="downloadOriginal"
      >
        <Download :size="15" />下载原文件
      </button>
      <button
        class="button button-primary"
        type="button"
        :disabled="reindexing"
        @click="reindex"
      >
        <RefreshCw :size="15" :class="{ 'spin-icon': reindexing }" />
        {{ reindexing ? "提交中…" : "重新索引" }}
      </button>
    </div>
  </div>

    <div class="asset-status-strip">
    <div class="status-overview">
      <span class="status-badge" :class="statusClass(asset.status)">
        <CheckCircle2 v-if="asset.status === 'indexed'" :size="13" />
        <AlertTriangle v-else-if="asset.status === 'failed'" :size="13" />
        <LoaderCircle v-else :size="13" class="spin-icon" />
        {{ statusLabel(asset.status) }}
      </span>
      <p>{{ statusDescription }}</p>
    </div>
    <div class="detail-facts">
      <div>
        <span>{{ assetDetailCopy.chunksLabel }}</span
        ><strong>{{ asset.chunks || "—" }}</strong>
      </div>
      <div>
        <span>{{ assetDetailCopy.progressLabel }}</span
        ><strong>{{ asset.progress }}%</strong>
      </div>
      <div>
        <span>{{ assetDetailCopy.updatedLabel }}</span
        ><strong>{{ asset.updated }}</strong>
      </div>
    </div>
    </div>

    <div v-if="asset.status === 'failed'" class="asset-error-banner">
    <AlertTriangle :size="17" />
    <div>
      <strong>索引未完成</strong><span>{{ asset.reason }}</span>
    </div>
    <button class="button button-secondary" type="button" @click="reindex">
      重新处理
    </button>
    </div>

    <div class="asset-detail-layout">
    <main class="asset-main-column">
      <section class="panel document-panel">
        <div class="panel-heading document-heading">
          <div>
            <h2>知识库内容</h2>
            <p>查看原文片段、切片结构和 Agent 可引用内容。</p>
          </div>
          <FileSearch :size="18" class="panel-heading-icon" />
        </div>
        <div class="workspace-tabs" role="tablist" aria-label="知识库详情视图">
          <button
            type="button"
            :class="{ active: activeSection === 'preview' }"
            @click="activeSection = 'preview'"
          >
            内容预览
          </button>
          <button
            type="button"
            :class="{ active: activeSection === 'chunks' }"
            @click="activeSection = 'chunks'"
          >
            Chunk 列表 <span>{{ asset.chunks || 0 }}</span>
          </button>
          <button
            type="button"
            :class="{ active: activeSection === 'citations' }"
            @click="activeSection = 'citations'"
          >
            引用片段 <span>{{ assetCitations.length }}</span>
          </button>
        </div>

        <div v-if="activeSection === 'preview'" class="document-preview-wrap">
          <div class="document-toolbar">
            <span>{{ asset.type }} 文档预览</span
            ><span>最后更新 {{ asset.updated }}</span>
          </div>
          <article class="document-preview">
            <p class="document-kicker">PROJECT KNOWLEDGE BASE</p>
            <h3>{{ previewTitle }}</h3>
            <p v-for="paragraph in previewParagraphs" :key="paragraph">
              {{ paragraph }}
            </p>
            <div class="quote-highlight">
              <span>“</span>
              <p>
                {{
                  assetCitations[0]?.text ||
                  "完成索引后，这里会展示可被 Agent 直接引用的证据片段。"
                }}
              </p>
            </div>
            <p class="preview-footnote">
              预览内容用于确认解析结果；真实项目可通过后端内容接口返回分页、页码和原文定位信息。
            </p>
          </article>
        </div>

        <div v-else-if="activeSection === 'chunks'" class="chunk-workspace">
          <div class="chunk-list">
            <button
              v-for="chunk in chunkRows"
              :key="chunk.index"
              class="chunk-row"
              :class="{ active: activeChunk === chunk.index }"
              type="button"
              @click="activeChunk = chunk.index"
            >
              <span>{{ String(chunk.index + 1).padStart(2, "0") }}</span
              ><strong>{{ chunk.title }}</strong
              ><small>{{ chunk.label }}</small>
            </button>
          </div>
          <div class="chunk-reader">
            <div class="chunk-reader-heading">
              <span>{{ activeChunkRow?.label }}</span
              ><small>可引用片段</small>
            </div>
            <h3>{{ activeChunkRow?.title }}</h3>
            <p>{{ activeChunkRow?.snippet }}</p>
            <div class="chunk-reader-meta">
              <span>来源：{{ asset.name }}</span
              ><button type="button" @click="notify('Chunk 标识已复制')">
                复制标识
              </button>
            </div>
          </div>
        </div>

        <div v-else class="citation-workspace">
          <div class="citation-search">
            <Search :size="15" /><input
              v-model="citationQuery"
              type="search"
              placeholder="在当前资料的引用中搜索…"
              aria-label="搜索当前资料引用"
            />
          </div>
          <div v-if="visibleCitations.length" class="citation-list">
            <article
              v-for="citation in visibleCitations"
              :key="citation.source"
              class="citation-card"
            >
              <div class="citation-card-heading">
                <strong>{{ citation.title }}</strong
                ><span>相关度 {{ citation.score }}</span>
              </div>
              <p>{{ citation.text }}</p>
              <button type="button" @click="locateCitation(citation.source)">
                {{ citation.source }} · 定位
              </button>
            </article>
          </div>
          <div v-else class="empty-detail-state">
            <FileSearch :size="22" /><strong>暂无引用片段</strong
            ><span>完成索引并被 Agent 检索后，引用会显示在这里。</span>
          </div>
        </div>
      </section>
    </main>

    <aside class="asset-meta-column">
      <section class="panel metadata-panel">
        <div class="panel-heading">
          <div>
            <h2>资料信息</h2>
            <p>用于后端详情接口的字段预览。</p>
          </div>
        </div>
        <dl>
          <div>
            <dt>文件名</dt>
            <dd :title="asset.name">{{ asset.name }}</dd>
          </div>
          <div>
            <dt>文件类型</dt>
            <dd>{{ asset.type }}</dd>
          </div>
          <div>
            <dt>文件大小</dt>
            <dd>{{ asset.size }}</dd>
          </div>
          <div>
            <dt>上传者</dt>
            <dd>{{ asset.uploader }}</dd>
          </div>
          <div>
            <dt>Chunk 数量</dt>
            <dd class="mono">{{ asset.chunks }}</dd>
          </div>
          <div>
            <dt>索引状态</dt>
            <dd>{{ statusLabel(asset.status) }}</dd>
          </div>
        </dl>
      </section>

      <section class="panel index-status-panel">
        <div class="panel-heading">
          <div>
            <h2>处理进度</h2>
            <p>{{ assetDetailCopy.subtitle }}</p>
          </div>
        </div>
        <div class="index-timeline">
          <div
            v-for="step in indexSteps"
            :key="step.label"
            class="index-step"
            :class="`is-${step.state}`"
          >
            <span class="index-step-dot" />
            <div>
              <strong>{{ step.label }}</strong
              ><small>{{
                step.state === "done"
                  ? "已完成"
                  : step.state === "active"
                    ? "进行中"
                    : step.state === "error"
                      ? "需要处理"
                      : "等待中"
              }}</small>
            </div>
          </div>
        </div>
      </section>

      <div class="security-note">
        <ShieldCheck :size="17" /><span>{{
          assetDetailCopy.securityNote
        }}</span>
      </div>
    </aside>
    </div>
  </template>
  <div v-else class="empty-detail-state asset-detail-empty">
    <FileSearch :size="24" />
    <strong>暂无资料详情</strong>
    <span>该资料不存在、尚未加载完成，或当前项目还没有知识库资料。</span>
    <button class="button button-secondary button-sm" type="button" @click="goBack">
      返回知识库
    </button>
  </div>
</template>

<style scoped>
.back-button {
  margin-bottom: 1.25rem;
}
.detail-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.375rem;
  margin-bottom: 1.25rem;
}
.asset-title {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  min-width: 0;
}
.asset-title > div {
  min-width: 0;
}
.asset-title h1 {
  overflow: hidden;
  margin: 0.25rem 0 0;
  color: var(--workspace-text);
  font-size: clamp(1.15rem, 2vw, 1.5rem);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.asset-title p:last-child {
  margin: 0.5rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.625rem;
}
.file-type.large {
  width: 2.75rem;
  height: 3.125rem;
  border-radius: 0.625rem;
}
.heading-actions {
  display: flex;
  gap: 0.5rem;
  flex: 0 0 auto;
}
.heading-actions .button {
  white-space: nowrap;
}
.asset-status-strip {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(26rem, 1.3fr);
  align-items: stretch;
  gap: 1rem;
  margin-bottom: 1rem;
}
.status-overview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
  padding: 0.875rem 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface);
}
.status-overview p {
  margin: 0;
  color: var(--workspace-muted);
  font-size: 0.625rem;
  line-height: 1.5;
}
.detail-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}
.detail-facts div {
  padding: 0.75rem 0.875rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.625rem;
  background: var(--surface-soft);
}
.detail-facts span,
.detail-facts strong {
  display: block;
}
.detail-facts span {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.detail-facts strong {
  margin-top: 0.375rem;
  color: var(--workspace-text);
  font-size: 0.875rem;
}
.asset-error-banner {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 1rem;
  padding: 0.75rem 0.875rem;
  border: 0.0625rem solid #f0cccc;
  border-radius: 0.625rem;
  background: #fff7f7;
  color: #b05555;
}
.asset-error-banner > div {
  display: grid;
  flex: 1;
  gap: 0.125rem;
}
.asset-error-banner strong {
  font-size: 0.6875rem;
}
.asset-error-banner span {
  font-size: 0.5625rem;
}
.asset-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(17.5rem, 0.75fr);
  gap: 1.125rem;
  align-items: start;
}
.asset-main-column,
.asset-meta-column {
  min-width: 0;
}
.asset-meta-column {
  display: grid;
  gap: 1.125rem;
  align-content: start;
}
.document-panel {
  overflow: hidden;
}
.document-heading {
  padding: 1.5rem 1.5rem 0;
}
.panel-heading-icon {
  color: var(--teal);
}
.workspace-tabs {
  display: flex;
  gap: 0.25rem;
  padding: 1.125rem 1.5rem 0;
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.workspace-tabs button {
  padding: 0.625rem 0.75rem 0.75rem;
  border: 0;
  border-bottom: 0.125rem solid transparent;
  background: transparent;
  color: var(--workspace-muted);
  font: inherit;
  font-size: 0.625rem;
  cursor: pointer;
}
.workspace-tabs button:hover {
  color: var(--workspace-text);
}
.workspace-tabs button.active {
  border-bottom-color: var(--teal);
  color: var(--teal-dark);
  font-weight: 650;
}
.workspace-tabs button span {
  margin-left: 0.25rem;
  opacity: 0.7;
}
.document-preview-wrap {
  min-height: 22rem;
}
.document-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1.5rem;
  border-bottom: 0.0625rem solid #f0f3f3;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.document-preview {
  max-width: 48.75rem;
  padding: 1.25rem 2.5rem 2.1875rem;
  color: #5b6c71;
  font-family: Georgia, "Songti SC", serif;
  font-size: 0.75rem;
  line-height: 2;
}
.document-kicker {
  margin: 0 0 0.75rem !important;
  color: var(--teal);
  font-family: "Geist", "Microsoft YaHei", sans-serif;
  font-size: 0.5rem;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.document-preview h3 {
  margin: 0 0 1rem;
  color: #29474b;
  font-family: "Geist", "Microsoft YaHei", sans-serif;
  font-size: 1.0625rem;
}
.document-preview p {
  margin: 0 0 1rem;
}
.quote-highlight {
  display: flex;
  gap: 0.625rem;
  margin: 1.25rem 0;
  padding: 0.75rem 0.9375rem;
  border-left: 0.1875rem solid var(--teal);
  border-radius: 0 0.4375rem 0.4375rem 0;
  background: #f0faf8;
  color: #356563;
}
.quote-highlight span {
  color: var(--teal);
  font-family: Georgia, serif;
  font-size: 1.6875rem;
  line-height: 1;
}
.quote-highlight p {
  margin: 0;
}
.preview-footnote {
  color: #96a5a8;
  font-family: "Geist", "Microsoft YaHei", sans-serif;
  font-size: 0.5625rem;
  line-height: 1.6;
}
.chunk-workspace {
  display: grid;
  grid-template-columns: minmax(11rem, 0.7fr) minmax(0, 1.3fr);
  min-height: 22rem;
}
.chunk-list {
  padding: 0.875rem;
  border-right: 0.0625rem solid var(--workspace-divider);
}
.chunk-row {
  display: grid;
  grid-template-columns: 1.5rem 1fr;
  gap: 0.125rem 0.5rem;
  width: 100%;
  margin-bottom: 0.25rem;
  padding: 0.625rem 0.5625rem;
  border: 0;
  border-radius: 0.4375rem;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.chunk-row > span {
  grid-row: span 2;
  align-self: start;
  color: #b0bbbd;
  font-size: 0.5625rem;
}
.chunk-row strong {
  overflow: hidden;
  color: #64767b;
  font-size: 0.625rem;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chunk-row small {
  color: #9aa8ab;
  font-size: 0.5rem;
}
.chunk-row.active,
.chunk-row:hover {
  background: #edf8f6;
}
.chunk-row.active strong {
  color: var(--teal-dark);
}
.chunk-reader {
  padding: 1.5rem;
}
.chunk-reader-heading {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  color: var(--teal-dark);
  font-size: 0.5625rem;
  font-weight: 700;
}
.chunk-reader-heading small {
  color: var(--workspace-muted);
  font-weight: 500;
}
.chunk-reader h3 {
  margin: 1rem 0 0.75rem;
  color: var(--workspace-text);
  font-size: 0.9375rem;
}
.chunk-reader p {
  margin: 0;
  color: var(--workspace-muted);
  font-size: 0.6875rem;
  line-height: 1.8;
}
.chunk-reader-meta {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 2rem;
  padding-top: 0.75rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.chunk-reader-meta button,
.citation-card button {
  border: 0;
  background: transparent;
  color: var(--teal-dark);
  font: inherit;
  font-size: 0.5625rem;
  cursor: pointer;
}
.citation-workspace {
  min-height: 22rem;
  padding: 1.25rem 1.5rem 1.5rem;
}
.citation-search {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 26rem;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  color: var(--workspace-muted);
}
.citation-search:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 12%, transparent);
}
.citation-search input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.625rem;
}
.citation-list {
  display: grid;
  gap: 0.625rem;
  margin-top: 1rem;
}
.citation-card {
  padding: 0.875rem 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5625rem;
  background: var(--surface-soft);
}
.citation-card-heading {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
}
.citation-card-heading strong {
  color: var(--workspace-text);
  font-size: 0.6875rem;
}
.citation-card-heading span {
  color: var(--teal-dark);
  font-size: 0.5625rem;
}
.citation-card p {
  margin: 0.5rem 0;
  color: var(--workspace-muted);
  font-size: 0.625rem;
  line-height: 1.6;
}
.empty-detail-state {
  display: grid;
  justify-items: center;
  gap: 0.375rem;
  padding: 4rem 1rem;
  color: var(--workspace-muted);
  text-align: center;
}
.empty-detail-state strong {
  color: var(--workspace-text);
  font-size: 0.6875rem;
}
.empty-detail-state span {
  font-size: 0.5625rem;
}
.metadata-panel {
  padding-bottom: 0.625rem;
}
.metadata-panel dl {
  margin: 0;
  padding: 0 1.5rem 0.625rem;
}
.metadata-panel dl div {
  display: flex;
  justify-content: space-between;
  gap: 0.625rem;
  padding: 0.625rem 0;
  border-top: 0.0625rem solid #edf1f1;
}
.metadata-panel dt {
  color: #98a6aa;
  font-size: 0.5625rem;
}
.metadata-panel dd {
  max-width: 11rem;
  overflow: hidden;
  margin: 0;
  color: #52666c;
  font-size: 0.5625rem;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono {
  font-family: ui-monospace, monospace;
}
.index-status-panel {
  padding-bottom: 1.25rem;
}
.index-timeline {
  display: grid;
  gap: 0.875rem;
  padding: 0 1.5rem;
}
.index-step {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
}
.index-step-dot {
  width: 0.5rem;
  height: 0.5rem;
  margin-top: 0.125rem;
  border: 0.125rem solid #cbd7d7;
  border-radius: 50%;
  background: var(--surface);
}
.index-step > div {
  display: grid;
  gap: 0.125rem;
}
.index-step strong {
  color: var(--workspace-muted);
  font-size: 0.625rem;
  font-weight: 550;
}
.index-step small {
  color: #a0adaf;
  font-size: 0.5rem;
}
.index-step.is-done .index-step-dot {
  border-color: var(--teal);
  background: var(--teal);
  box-shadow: 0 0 0 0.1875rem #e4f7f3;
}
.index-step.is-done strong,
.index-step.is-active strong {
  color: var(--workspace-text);
}
.index-step.is-active .index-step-dot {
  border-color: #e9a52e;
  background: #fff5d9;
}
.index-step.is-error .index-step-dot {
  border-color: #d96a6a;
  background: #fff0f0;
}
.security-note {
  display: flex;
  align-items: flex-start;
  gap: 0.5625rem;
  padding: 0.875rem 1rem;
  border: 0.0625rem solid
    color-mix(in oklab, var(--teal) 20%, var(--workspace-border));
  border-radius: 0.5625rem;
  background: color-mix(in oklab, var(--teal) 7%, var(--surface));
  color: var(--teal-dark);
  font-size: 0.625rem;
  line-height: 1.5;
}
.spin-icon {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 60rem) {
  .asset-status-strip {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 47.5rem) {
  .detail-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .heading-actions {
    width: 100%;
  }
  .heading-actions .button {
    flex: 1;
    justify-content: center;
  }
  .asset-detail-layout {
    grid-template-columns: 1fr;
  }
  .chunk-workspace {
    grid-template-columns: 1fr;
  }
  .chunk-list {
    max-height: 13rem;
    overflow-y: auto;
    border-right: 0;
    border-bottom: 0.0625rem solid var(--workspace-divider);
  }
}
@media (max-width: 30rem) {
  .asset-title h1 {
    white-space: normal;
  }
  .asset-status-strip .detail-facts {
    grid-template-columns: 1fr;
  }
  .document-preview {
    padding-inline: 1.25rem;
  }
  .workspace-tabs {
    overflow-x: auto;
    padding-inline: 1rem;
  }
  .workspace-tabs button {
    white-space: nowrap;
  }
  .document-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
  .asset-error-banner {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .asset-error-banner .button {
    margin-left: 1.5rem;
  }
}
</style>
