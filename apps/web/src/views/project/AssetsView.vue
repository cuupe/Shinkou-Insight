<script setup lang="ts">
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Upload,
} from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { assetFilterOptions, assetTabs } from "@/data/mock";
const {
  filteredAssets,
  searchQuery,
  assetFilter,
  assetTab,
  uploadInput,
  openUpload,
  onFilesSelected,
  retryAsset,
  statusLabel,
  statusClass,
  router,
  routeTo,
} = useWorkspace();
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / KNOWLEDGE"
    title="知识资产"
    subtitle="管理项目资料、索引状态和可引用内容"
    ><template #action
      ><button class="button button-primary" type="button" @click="openUpload">
        <Upload :size="17" />上传资料
      </button></template
    ></PageHeader
  >
  <input
    ref="uploadInput"
    class="sr-only"
    type="file"
    multiple
    @change="onFilesSelected"
  />
  <section class="panel asset-table-panel">
    <div class="asset-toolbar">
      <label class="global-search asset-search"
        ><Search :size="16" /><input
          v-model="searchQuery"
          placeholder="搜索文件名…"
      /></label>
      <div class="filter-tabs">
        <button
          v-for="tab in assetTabs"
          :key="tab"
          type="button"
          :class="{ active: assetTab === tab }"
          @click="assetTab = tab"
        >
          {{ tab }}
        </button>
      </div>
      <select v-model="assetFilter">
        <option v-for="option in assetFilterOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </div>
    <div class="data-table">
      <div class="table-row table-header">
        <span>资料</span><span>状态</span><span>切片</span><span>更新时间</span
        ><span />
      </div>
      <div
        v-for="asset in filteredAssets"
        :key="asset.id"
        class="table-row asset-row"
        role="button"
        tabindex="0"
        @click="
          router.push({
            name: 'project-asset-detail',
            params: { ...routeTo('project-asset-detail').params, assetId: asset.id },
          })
        "
        @keydown.enter="
          router.push({
            name: 'project-asset-detail',
            params: { ...routeTo('project-asset-detail').params, assetId: asset.id },
          })
        "
      >
        <div class="asset-title">
          <span class="file-type"><FileText :size="16" /></span
          ><span
            ><strong>{{ asset.name }}</strong
            ><small
              >{{ asset.type }} · {{ asset.size }} · {{ asset.uploader }}</small
            ></span
          >
        </div>
        <span class="status-badge" :class="statusClass(asset.status)"
          ><i />{{ statusLabel(asset.status) }}</span
        ><span class="muted-cell">{{ asset.chunks || "—" }}</span
        ><span class="muted-cell">{{ asset.updated }}</span
        ><button
          v-if="asset.status === 'failed'"
          class="icon-button small"
          type="button"
          @click.stop="retryAsset(asset.name)"
        >
          <RefreshCw :size="16" /></button
        ><CheckCircle2
          v-else-if="asset.status === 'indexed'"
          class="teal-text"
          :size="17"
        /><AlertTriangle v-else class="amber-text" :size="17" />
      </div>
    </div>
    <p v-if="!filteredAssets.length" class="empty-state">没有匹配的知识资产</p>
  </section>
</template>
