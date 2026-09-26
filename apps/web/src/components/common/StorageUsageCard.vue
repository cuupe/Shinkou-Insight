<script setup lang="ts">
import { HardDrive, LoaderCircle } from "@lucide/vue";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { storageApi } from "@/api/storage";
import type { StorageQuota } from "@/api/types";
import { useWorkspace } from "@/composables/useWorkspace";

const { workspaceId, projectId } = useWorkspace();
const quota = ref<StorageQuota | null>(null);
const loading = ref(false);

const progressStyle = computed(() => ({
  width: `${Math.min(100, Math.max(0, quota.value?.usagePercent || 0))}%`,
}));

function formatBytes(bytes: number) {
  if (!bytes) return "0 MB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(bytes >= 100 * 1024 * 1024 ? 0 : 1)} MB`;
}

async function loadQuota() {
  if (projectId.value <= 0 || !workspaceId.value) return;
  loading.value = true;
  try {
    quota.value = await storageApi.quota(workspaceId.value, projectId.value);
  } catch {
    quota.value = null;
  } finally {
    loading.value = false;
  }
}

function handleQuotaChanged() {
  void loadQuota();
}

onMounted(() => {
  void loadQuota();
  window.addEventListener("storage-quota-changed", handleQuotaChanged);
});
onUnmounted(() => {
  window.removeEventListener("storage-quota-changed", handleQuotaChanged);
});
watch([workspaceId, projectId], loadQuota);
</script>

<template>
  <section class="storage-usage-card" aria-label="用户存储空间使用情况">
    <div class="storage-usage-heading">
      <div class="storage-usage-title">
        <span class="storage-usage-icon"><HardDrive :size="16" /></span>
        <div>
          <strong>存储空间</strong>
          <p>文件库与知识库共用，每个用户最多 512 MB</p>
        </div>
      </div>
      <div v-if="loading" class="storage-usage-loading">
        <LoaderCircle class="storage-usage-spin" :size="14" />
      </div>
      <strong v-else-if="quota" class="storage-usage-total">
        {{ formatBytes(quota.usedBytes) }} / {{ formatBytes(quota.maxBytes) }}
      </strong>
    </div>

    <template v-if="quota">
      <div class="storage-usage-track" role="progressbar" :aria-valuenow="quota.usagePercent" aria-valuemin="0" aria-valuemax="100">
        <i :style="progressStyle" />
      </div>
      <div class="storage-usage-facts">
        <span><i class="storage-dot file-dot" />文件库 <strong>{{ formatBytes(quota.fileBytes) }}</strong></span>
        <span><i class="storage-dot knowledge-dot" />知识库 <strong>{{ formatBytes(quota.knowledgeBytes) }}</strong></span>
        <span class="storage-remaining">剩余 {{ formatBytes(quota.remainingBytes) }}</span>
      </div>
    </template>
  </section>
</template>

<style scoped>
.storage-usage-card {
  display: grid;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;
  background: color-mix(in oklab, var(--teal) 5%, var(--surface));
}

.storage-usage-heading,
.storage-usage-title,
.storage-usage-facts {
  display: flex;
  align-items: center;
}

.storage-usage-heading {
  justify-content: space-between;
  gap: 1rem;
}

.storage-usage-title {
  min-width: 0;
  gap: 0.625rem;
}

.storage-usage-title > div {
  min-width: 0;
}

.storage-usage-icon {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.5625rem;
  background: color-mix(in oklab, var(--teal) 14%, var(--surface));
  color: var(--teal-dark);
}

.storage-usage-title strong {
  color: var(--workspace-text);
  font-size: 0.8125rem;
}

.storage-usage-title p {
  margin: 0.1875rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.75rem;
  line-height: 1.4;
}

.storage-usage-total {
  flex: 0 0 auto;
  color: var(--teal-dark);
  font-size: 0.8125rem;
}

.storage-usage-track {
  height: 0.375rem;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in oklab, var(--teal) 12%, var(--surface));
}

.storage-usage-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--teal);
  transition: width 180ms ease;
}

.storage-usage-facts {
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  color: var(--workspace-muted);
  font-size: 0.75rem;
}

.storage-usage-facts span {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
}

.storage-usage-facts strong {
  color: var(--workspace-text);
  font-weight: 650;
}

.storage-dot {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 50%;
}

.file-dot { background: #5c8bea; }
.knowledge-dot { background: var(--teal); }
.storage-remaining { margin-left: auto; color: var(--teal-dark); }
.storage-usage-loading { color: var(--teal-dark); }
.storage-usage-spin { animation: storage-usage-spin 1s linear infinite; }
@keyframes storage-usage-spin { to { transform: rotate(360deg); } }

@media (max-width: 42rem) {
  .storage-usage-heading { align-items: flex-start; flex-direction: column; }
  .storage-usage-total { align-self: flex-end; }
  .storage-remaining { margin-left: 0; }
}
</style>
