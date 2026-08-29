<script setup lang="ts">
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  CheckCircle2,
  Database,
  FileText,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  X,
} from "@lucide/vue";
import { computed, ref } from "vue";
import { onMounted } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import SearchField from "@/components/common/SearchField.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";
import { assetTabs } from "@/data/options";
import type { AssetStatus } from "@/data/options";
import { assetsApi } from "@/api/assets";

const {
  filteredAssets,
  assets,
  searchQuery,
  assetTab,
  uploadInput,
  openUpload,
  retryAsset,
  statusLabel,
  statusClass,
  router,
  routeTo,
  notify,
  workspaceId,
  projectId,
} = useWorkspace();

function mapAsset(asset: Awaited<ReturnType<typeof assetsApi.detail>>) {
  const status =
    asset.indexStatus === "SUCCESS"
      ? "indexed"
      : asset.indexStatus === "FAILED"
        ? "failed"
        : "indexing";
  return {
    id: String(asset.id),
    name: asset.name,
    type: asset.assetType,
    size: asset.fileSize ? `${Math.round(Number(asset.fileSize) / 1024)} KB` : "—",
    uploader: "—",
    updated: asset.updatedAt || "—",
    chunks: asset.chunkCount || 0,
    progress: Number(asset.progress || (status === "indexed" ? 100 : 0)),
    status: status as AssetStatus,
    reason: asset.errorMessage || "",
  };
}

async function loadAssets() {
  try {
    const remoteAssets = await assetsApi.list(
      workspaceId.value,
      projectId.value,
    );
    assets.splice(0, assets.length, ...remoteAssets.map(mapAsset));
  } catch (error) {
    notify(error instanceof Error ? error.message : "知识库加载失败");
  }
}

async function onFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  try {
    const uploaded = await Promise.all(
      files.map((file) =>
        assetsApi.upload(workspaceId.value, projectId.value, file),
      ),
    );
    assets.unshift(...uploaded.map(mapAsset));
    notify(`已上传 ${uploaded.length} 个资料`);
  } catch (error) {
    notify(error instanceof Error ? error.message : "资料上传失败");
  } finally {
    input.value = "";
  }
}

const sortBy = ref("updated");
const actionableOnly = ref(false);
const selectedIds = ref<Set<string>>(new Set());
const deleteDialogOpen = ref(false);
const deleteTargetId = ref<string | null>(null);

const assetCounts = computed(() => ({
  全部: assets.length,
  已索引: assets.filter((asset) => asset.status === "indexed").length,
  处理中: assets.filter((asset) => asset.status === "indexing").length,
  失败: assets.filter((asset) => asset.status === "failed").length,
}));
const indexedCount = computed(
  () => assets.filter((asset) => asset.status === "indexed").length,
);
const indexingCount = computed(
  () => assets.filter((asset) => asset.status === "indexing").length,
);
const failedCount = computed(
  () => assets.filter((asset) => asset.status === "failed").length,
);
const completionRate = computed(() =>
  assets.length ? Math.round((indexedCount.value / assets.length) * 100) : 0,
);
const selectedAssets = computed(() =>
  assets.filter((asset) => selectedIds.value.has(asset.id)),
);
const visibleAssets = computed(() => {
  const list = filteredAssets.value.filter((asset) =>
    actionableOnly.value ? asset.status !== "indexed" : true,
  );

  return [...list].sort((left, right) => {
    if (sortBy.value === "name")
      return left.name.localeCompare(right.name, "zh-CN");
    if (sortBy.value === "chunks") return right.chunks - left.chunks;
    if (sortBy.value === "progress") return right.progress - left.progress;
    return updatedRank(left.updated) - updatedRank(right.updated);
  });
});
const allVisibleSelected = computed(
  () =>
    visibleAssets.value.length > 0 &&
    visibleAssets.value.every((asset) => selectedIds.value.has(asset.id)),
);
const someVisibleSelected = computed(
  () =>
    !allVisibleSelected.value &&
    visibleAssets.value.some((asset) => selectedIds.value.has(asset.id)),
);
const deleteTarget = computed(() =>
  deleteTargetId.value
    ? assets.find((asset) => asset.id === deleteTargetId.value)
    : undefined,
);

function updatedRank(value: string) {
  if (value === "—") return 4;
  if (value.startsWith("今天")) return 1;
  if (value.startsWith("昨天")) return 2;
  return 3;
}

function openAsset(assetId: string) {
  router.push({
    name: "project-asset-detail",
    params: { ...routeTo("project-asset-detail").params, assetId },
  });
}

function toggleSelected(assetId: string, checked?: boolean) {
  const next = new Set(selectedIds.value);
  const shouldSelect = checked ?? !next.has(assetId);
  if (shouldSelect) next.add(assetId);
  else next.delete(assetId);
  selectedIds.value = next;
}

function toggleAllVisible() {
  const next = new Set(selectedIds.value);
  if (allVisibleSelected.value) {
    visibleAssets.value.forEach((asset) => next.delete(asset.id));
  } else {
    visibleAssets.value.forEach((asset) => next.add(asset.id));
  }
  selectedIds.value = next;
}

function clearSelection() {
  selectedIds.value = new Set();
}

function retrySelected() {
  const targets = selectedAssets.value.filter(
    (asset) => asset.status !== "indexed",
  );
  if (!targets.length) {
    notify("当前选中的资料都已完成索引");
    return;
  }
  targets.forEach((asset) => retryAsset(asset.name));
  notify(`已提交 ${targets.length} 个资料的重新索引`);
  clearSelection();
}

function requestDelete(assetId?: string) {
  deleteTargetId.value = assetId || null;
  deleteDialogOpen.value = true;
}

async function confirmDelete() {
  const ids = deleteTargetId.value
    ? [deleteTargetId.value]
    : Array.from(selectedIds.value);
  const removeIds = new Set(ids);
  try {
    await Promise.all(
      ids.map((id) =>
        assetsApi.remove(workspaceId.value, projectId.value, id),
      ),
    );
  } catch (error) {
    notify(error instanceof Error ? error.message : "资料移除失败");
    return;
  }
  const removeCount = assets.filter((asset) => removeIds.has(asset.id)).length;
  for (let index = assets.length - 1; index >= 0; index -= 1) {
    const asset = assets[index];
    if (asset && removeIds.has(asset.id)) assets.splice(index, 1);
  }
  clearSelection();
  deleteTargetId.value = null;
  deleteDialogOpen.value = false;
  if (removeCount) notify(`已移除 ${removeCount} 个知识库资料`);
}

onMounted(loadAssets);
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / KNOWLEDGE"
    title="知识库"
    subtitle="统一管理项目资料、索引状态和 Agent 可引用内容"
  >
    <template #action>
      <button class="button button-primary" type="button" @click="openUpload">
        <Upload :size="17" />上传资料
      </button>
    </template>
  </PageHeader>

  <input
    ref="uploadInput"
    class="sr-only"
    type="file"
    multiple
    accept=".pdf,.md,.markdown,.txt,.doc,.docx"
    @change="onFilesSelected"
  />

  <section class="knowledge-health-grid" aria-label="知识库状态概览">
    <article class="health-card health-card-primary">
      <div class="health-card-icon"><Database :size="17" /></div>
      <div>
        <span>资料总量</span><strong>{{ assets.length }}</strong
        ><small>当前项目知识库</small>
      </div>
      <div class="health-ring">
        <strong>{{ completionRate }}%</strong><small>索引完成</small>
      </div>
    </article>
    <article class="health-card">
      <div class="health-card-icon is-success"><CheckCircle2 :size="17" /></div>
      <div>
        <span>已就绪</span><strong>{{ indexedCount }}</strong
        ><small>可被 Agent 检索</small>
      </div>
    </article>
    <article class="health-card">
      <div class="health-card-icon is-warning"><RefreshCw :size="17" /></div>
      <div>
        <span>处理中</span><strong>{{ indexingCount }}</strong
        ><small>正在解析或建立索引</small>
      </div>
    </article>
    <article class="health-card">
      <div class="health-card-icon is-danger"><AlertTriangle :size="17" /></div>
      <div>
        <span>需要处理</span><strong>{{ failedCount }}</strong
        ><small>{{ failedCount ? "建议尽快重新索引" : "当前没有异常" }}</small>
      </div>
    </article>
  </section>

  <section class="panel asset-table-panel">
    <div class="library-toolbar">
      <div class="toolbar-topline">
        <div>
          <h2>项目资料</h2>
          <p>选择资料后可以批量重新索引或移除。</p>
        </div>
        <label class="actionable-toggle">
          <input v-model="actionableOnly" type="checkbox" />
          <span>仅看需要处理</span>
        </label>
      </div>
      <div class="toolbar-controls">
        <SearchField
          v-model="searchQuery"
          placeholder="搜索文件名…"
          aria-label="搜索知识库文件名"
        />
        <div class="segmented-tabs" role="tablist" aria-label="知识库状态">
          <button
            v-for="tab in assetTabs"
            :key="tab"
            type="button"
            :class="{ active: assetTab === tab }"
            :aria-pressed="assetTab === tab"
            @click="assetTab = tab"
          >
            {{ tab
            }}<span>{{ assetCounts[tab as keyof typeof assetCounts] }}</span>
          </button>
        </div>
        <label class="sort-control">
          <span>排序</span>
          <select v-model="sortBy" aria-label="知识库排序方式">
            <option value="updated">最近更新</option>
            <option value="name">文件名称</option>
            <option value="chunks">Chunk 数量</option>
            <option value="progress">索引进度</option>
          </select>
        </label>
      </div>
    </div>

    <div v-if="selectedAssets.length" class="selection-bar">
      <div>
        <button
          class="clear-selection"
          type="button"
          aria-label="清除选择"
          @click="clearSelection"
        >
          <X :size="14" /></button
        ><strong>已选择 {{ selectedAssets.length }} 项</strong
        ><span>批量操作只会影响当前选择</span>
      </div>
      <div class="selection-actions">
        <button
          class="button button-secondary button-compact"
          type="button"
          @click="retrySelected"
        >
          <RefreshCw :size="14" />重新索引
        </button>
        <button
          class="button button-danger button-compact"
          type="button"
          @click="requestDelete()"
        >
          <Trash2 :size="14" />移除资料
        </button>
      </div>
    </div>

    <div class="table-meta">
      <label class="select-all-control">
        <input
          type="checkbox"
          :checked="allVisibleSelected"
          :indeterminate="someVisibleSelected"
          aria-label="选择当前列表资料"
          @change="toggleAllVisible"
        />
        <span>{{ visibleAssets.length }} 个资料</span>
      </label>
      <span
        v-if="searchQuery || assetTab !== '全部' || actionableOnly"
        class="filter-hint"
        >已应用筛选</span
      >
    </div>

    <div v-if="visibleAssets.length" class="data-table">
      <div class="table-row table-header">
        <span class="table-check" aria-hidden="true" />
        <span>资料</span><span>状态</span><span>切片</span><span>索引进度</span
        ><span>更新时间</span><span>操作</span>
      </div>
      <div
        v-for="asset in visibleAssets"
        :key="asset.id"
        class="table-row asset-row"
        :class="{ selected: selectedIds.has(asset.id) }"
        role="button"
        tabindex="0"
        @click="openAsset(asset.id)"
        @keydown.enter.self="openAsset(asset.id)"
        @keydown.space.self.prevent="openAsset(asset.id)"
      >
        <span class="table-check" @click.stop>
          <input
            type="checkbox"
            :checked="selectedIds.has(asset.id)"
            :aria-label="`选择 ${asset.name}`"
            @change="
              toggleSelected(
                asset.id,
                ($event.target as HTMLInputElement).checked,
              )
            "
          />
        </span>
        <div class="asset-title">
          <span class="file-type" :class="asset.type.toLowerCase()"
            ><FileText :size="16"
          /></span>
          <span
            ><strong :title="asset.name">{{ asset.name }}</strong
            ><small :title="`${asset.type} · ${asset.size} · ${asset.uploader}`"
              >{{ asset.type }} · {{ asset.size }} · {{ asset.uploader }}</small
            ></span
          >
        </div>
        <span class="status-badge" :class="statusClass(asset.status)"
          ><i />{{ statusLabel(asset.status) }}</span
        >
        <span class="muted-cell">{{ asset.chunks || "—" }}</span>
        <div class="progress-cell">
          <div class="progress-track">
            <i
              :class="statusClass(asset.status)"
              :style="{ width: `${asset.progress}%` }"
            />
          </div>
          <small>{{ asset.progress }}%</small>
        </div>
        <span class="muted-cell">{{ asset.updated }}</span>
        <div class="row-actions" @click.stop>
          <button
            class="icon-button small"
            type="button"
            :aria-label="`查看 ${asset.name}`"
            title="查看详情"
            @click="openAsset(asset.id)"
          >
            <ArrowUpRight :size="15" />
          </button>
          <button
            v-if="asset.status !== 'indexed'"
            class="icon-button small"
            type="button"
            :aria-label="`重新索引 ${asset.name}`"
            title="重新索引"
            @click="retryAsset(asset.name)"
          >
            <RefreshCw :size="15" />
          </button>
          <button
            class="icon-button small danger-icon"
            type="button"
            :aria-label="`移除 ${asset.name}`"
            title="移除资料"
            @click="requestDelete(asset.id)"
          >
            <Trash2 :size="15" />
          </button>
          <Check
            v-if="asset.status === 'indexed'"
            class="teal-text row-status-icon"
            :size="15"
          />
        </div>
      </div>
    </div>
    <div v-else class="empty-library-state">
      <span><Search :size="20" /></span>
      <strong>{{
        searchQuery || actionableOnly
          ? "没有符合当前条件的资料"
          : "知识库还没有资料"
      }}</strong>
      <p>
        {{
          searchQuery || actionableOnly
            ? "尝试清除搜索或筛选条件。"
            : "上传 PDF、Markdown 或 TXT 文件，让 Agent 有可引用的内容。"
        }}
      </p>
      <button
        v-if="!searchQuery && !actionableOnly"
        class="button button-primary"
        type="button"
        @click="openUpload"
      >
        <Upload :size="15" />上传第一份资料
      </button>
      <button
        v-else
        class="button button-secondary"
        type="button"
        @click="
          searchQuery = '';
          actionableOnly = false;
          assetTab = '全部';
        "
      >
        清除筛选
      </button>
    </div>
  </section>

  <Dialog v-model:open="deleteDialogOpen">
    <DialogContent class="delete-dialog sm:max-w-md">
      <DialogHeader>
        <DialogTitle>{{
          deleteTarget
            ? "移除这份资料？"
            : `移除 ${selectedAssets.length} 份资料？`
        }}</DialogTitle>
        <DialogDescription
          >移除后资料不会再参与 Agent
          检索。已上传的原文件不会被下载到本地演示环境，后端接入后可改为软删除。</DialogDescription
        >
      </DialogHeader>
      <div class="delete-warning">
        <AlertTriangle :size="17" /><span
          >这是一个不可逆的本地演示操作，请确认选择范围。</span
        >
      </div>
      <DialogFooter>
        <button
          class="button button-secondary"
          type="button"
          @click="deleteDialogOpen = false"
        >
          取消
        </button>
        <button
          class="button button-danger"
          type="button"
          @click="confirmDelete"
        >
          <Trash2 :size="15" />确认移除
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.knowledge-health-grid {
  display: grid;
  grid-template-columns: 1.45fr repeat(3, 1fr);
  gap: 0.875rem;
  margin-bottom: 1rem;
}
.health-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-height: 5.5rem;
  padding: 1rem 1.125rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: 0 0.4375rem 1.4375rem rgb(21 53 52 / 3.5%);
}
.health-card-primary {
  background: linear-gradient(
    135deg,
    color-mix(in oklab, var(--teal) 8%, var(--surface)),
    var(--surface)
  );
}
.health-card-icon {
  display: grid;
  width: 2.25rem;
  height: 2.25rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.625rem;
  color: var(--teal-dark);
  background: #e0f6f2;
}
.health-card-icon.is-success {
  color: #3d936b;
  background: #eaf7ef;
}
.health-card-icon.is-warning {
  color: #b7791f;
  background: #fff4dc;
}
.health-card-icon.is-danger {
  color: #b65353;
  background: #fff0f0;
}
.health-card > div:nth-child(2) {
  display: grid;
  min-width: 0;
  gap: 0.125rem;
}
.health-card span {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.health-card strong {
  color: var(--workspace-text);
  font-size: 1.25rem;
  line-height: 1.15;
}
.health-card small {
  overflow: hidden;
  color: var(--workspace-subtle);
  font-size: 0.5rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.health-ring {
  display: grid;
  width: 3.25rem;
  height: 3.25rem;
  flex: 0 0 auto;
  place-content: center;
  margin-left: auto;
  border: 0.25rem solid #dff4ef;
  border-right-color: var(--teal);
  border-radius: 50%;
  text-align: center;
}
.health-ring strong {
  font-size: 0.6875rem;
}
.health-ring small {
  font-size: 0.4375rem;
}
.asset-table-panel {
  overflow: visible;
}
.library-toolbar {
  padding: 1.25rem 1.5rem 0;
}
.toolbar-topline,
.toolbar-controls,
.selection-bar,
.table-meta,
.selection-bar > div,
.selection-actions,
.actionable-toggle,
.select-all-control {
  display: flex;
  align-items: center;
}
.toolbar-topline {
  justify-content: space-between;
  gap: 1rem;
}
.toolbar-topline h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.9375rem;
}
.toolbar-topline p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.actionable-toggle {
  gap: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  cursor: pointer;
}
.actionable-toggle input,
.table-check input,
.select-all-control input {
  width: 0.875rem;
  height: 0.875rem;
  accent-color: var(--teal);
  cursor: pointer;
}
.toolbar-controls {
  justify-content: space-between;
  gap: 0.875rem;
  margin-top: 1.25rem;
  padding-bottom: 0.875rem;
}
.toolbar-controls :deep(.search-field) {
  min-width: 13rem;
}
.segmented-tabs {
  display: flex;
  gap: 0.1875rem;
}
.segmented-tabs button {
  padding: 0.5rem 0.625rem;
  border: 0;
  border-radius: 0.4375rem;
  background: transparent;
  color: #91a0a4;
  font: inherit;
  font-size: 0.625rem;
  cursor: pointer;
  transition:
    color 160ms ease,
    background-color 160ms ease;
}
.segmented-tabs button:hover {
  color: var(--workspace-text);
  background: color-mix(in oklab, var(--teal) 8%, var(--surface));
}
.segmented-tabs button.active {
  color: var(--teal-dark);
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
  font-weight: 650;
}
.segmented-tabs button span {
  margin-left: 0.3125rem;
  font-size: 0.5rem;
  opacity: 0.75;
}
.sort-control {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  white-space: nowrap;
}
.sort-control select {
  min-width: 6.75rem;
  padding: 0.5rem 0.5625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  outline: 0;
  background: var(--surface);
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.5625rem;
}
.sort-control select:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 12%, transparent);
}
.selection-bar {
  justify-content: space-between;
  gap: 0.875rem;
  margin: 0 1.5rem 0.75rem;
  padding: 0.625rem 0.75rem;
  border: 0.0625rem solid
    color-mix(in oklab, var(--teal) 20%, var(--workspace-border));
  border-radius: 0.5rem;
  background: #f0faf8;
  color: var(--teal-dark);
}
.selection-bar > div {
  gap: 0.5rem;
}
.selection-bar strong {
  font-size: 0.625rem;
}
.selection-bar span {
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.clear-selection {
  display: grid;
  width: 1.5rem;
  height: 1.5rem;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 0.375rem;
  background: transparent;
  color: var(--workspace-muted);
  cursor: pointer;
}
.clear-selection:hover {
  background: rgb(255 255 255 / 70%);
  color: var(--workspace-text);
}
.button-compact {
  min-height: 1.875rem;
  padding: 0.4375rem 0.625rem;
  font-size: 0.5625rem;
}
.button-danger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  border: 0.0625rem solid #e8bcbc;
  border-radius: 0.4375rem;
  background: #fff5f5;
  color: #b65353;
  cursor: pointer;
  font: inherit;
  font-size: 0.625rem;
}
.button-danger:hover {
  border-color: #d98b8b;
  background: #ffeded;
}
.selection-actions {
  gap: 0.4375rem;
}
.table-meta {
  justify-content: space-between;
  min-height: 2.5rem;
  padding: 0.625rem 1.5rem;
  border-top: 0.0625rem solid var(--workspace-divider);
  border-bottom: 0.0625rem solid var(--workspace-divider);
}
.select-all-control {
  gap: 0.4375rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
  cursor: pointer;
}
.filter-hint {
  padding: 0.25rem 0.4375rem;
  border-radius: 0.25rem;
  background: #edf8f6;
  color: var(--teal-dark);
  font-size: 0.5rem;
}
.asset-table-panel .table-row {
  position: relative;
  grid-template-columns:
    2rem minmax(14rem, 2.15fr)
    0.85fr 0.65fr 1.15fr 0.95fr 7rem;
}
.table-check {
  display: grid;
  place-items: center;
}
.asset-row {
  min-height: 4.5rem;
  gap: 0.75rem;
  cursor: pointer;
  transition: background-color 160ms ease;
}
.asset-row:hover,
.asset-row.selected {
  background: color-mix(in oklab, var(--teal) 6%, var(--surface));
}
.asset-row:focus-visible {
  z-index: 1;
  outline: 0.125rem solid color-mix(in oklab, var(--teal) 68%, white);
  outline-offset: -0.125rem;
}
.asset-title {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 0.75rem;
}
.asset-title > span:last-child {
  display: grid;
  flex: 1 1 auto;
  min-width: 0;
  width: 0;
  gap: 0.25rem;
}
.asset-title strong,
.asset-title small {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.asset-title strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
  font-weight: 680;
}
.asset-title small {
  color: var(--workspace-muted);
  font-size: 0.625rem;
  line-height: 1.4;
}
.asset-row > .status-badge,
.asset-row > .muted-cell,
.progress-cell,
.row-actions {
  white-space: nowrap;
}
.file-type {
  display: grid;
  width: 1.75rem;
  height: 2.0625rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.375rem;
  color: #b45b49;
  background: #fff0ea;
  font-size: 0.5rem;
  font-weight: 800;
}
.file-type.markdown,
.file-type.md {
  color: #6371c8;
  background: #edf0ff;
}
.file-type.text {
  color: #769348;
  background: #eff7e8;
}
.progress-cell {
  display: flex;
  align-items: center;
  gap: 0.4375rem;
}
.progress-track {
  width: 4.375rem;
  height: 0.3125rem;
  background: #edf1f1;
}
.progress-track i {
  display: block;
  height: 100%;
  background: var(--teal);
}
.progress-track i.status-indexing {
  background: #efa92e;
}
.progress-track i.status-failed {
  background: #dc6a6a;
}
.progress-cell small {
  color: #98a5a8;
  font-size: 0.5625rem;
}
.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.1875rem;
}
.row-actions .icon-button {
  width: 1.625rem;
  height: 1.625rem;
}
.danger-icon:hover {
  color: #b65353;
  border-color: #e3b5b5;
  background: #fff5f5;
}
.row-status-icon {
  margin-left: 0.125rem;
}
.empty-library-state {
  display: grid;
  justify-items: center;
  gap: 0.5rem;
  min-height: 15rem;
  padding: 3rem 1rem;
  color: var(--workspace-muted);
  text-align: center;
}
.empty-library-state > span {
  display: grid;
  width: 2.75rem;
  height: 2.75rem;
  place-items: center;
  border-radius: 0.75rem;
  background: #edf8f6;
  color: var(--teal);
}
.empty-library-state strong {
  color: var(--workspace-text);
  font-size: 0.75rem;
}
.empty-library-state p {
  max-width: 22rem;
  margin: 0 0 0.5rem;
  color: var(--workspace-muted);
  font-size: 0.625rem;
  line-height: 1.5;
}
.delete-dialog {
  max-width: 30rem !important;
}
.delete-warning {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 0.0625rem solid #f0cccc;
  border-radius: 0.4375rem;
  background: #fff7f7;
  color: #a95757;
  font-size: 0.625rem;
  line-height: 1.5;
}
@media (max-width: 72rem) {
  .knowledge-health-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .health-card-primary {
    grid-column: span 2;
  }
  .toolbar-controls {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
@media (max-width: 47.5rem) {
  .library-toolbar {
    padding-inline: 1.125rem;
  }
  .toolbar-topline {
    align-items: flex-start;
    flex-direction: column;
  }
  .toolbar-controls {
    align-items: stretch;
    flex-direction: column;
  }
  .toolbar-controls :deep(.search-field) {
    min-width: 0;
  }
  .segmented-tabs {
    overflow-x: auto;
  }
  .sort-control {
    justify-content: space-between;
  }
  .selection-bar {
    align-items: flex-start;
    flex-direction: column;
    margin-inline: 1.125rem;
  }
  .selection-bar > div {
    width: 100%;
  }
  .selection-actions .button {
    flex: 1;
  }
  .table-meta {
    padding-inline: 1.125rem;
  }
  .asset-table-panel {
    overflow-x: auto;
  }
  .asset-table-panel .data-table {
    min-width: 59rem;
  }
}
@media (max-width: 30rem) {
  .knowledge-health-grid {
    grid-template-columns: 1fr;
  }
  .health-card-primary {
    grid-column: auto;
  }
  .health-ring {
    display: none;
  }
}
</style>
