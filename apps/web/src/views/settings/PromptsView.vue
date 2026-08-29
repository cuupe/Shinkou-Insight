<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  CheckCircle2,
  Edit3,
  FileCode2,
  Plus,
  Search,
  Sparkles,
} from "@lucide/vue";
import Layout from "@/components/settings/Layout.vue";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useWorkspace } from "@/composables/useWorkspace";
import { settingsApi } from "@/api/settings";

type PromptRecord = {
  id?: number | string;
  name: string;
  version: string;
  updated: string;
  status: string;
  content: string;
};

const { notify, workspaceId } = useWorkspace();
const prompts = ref<PromptRecord[]>([]);
const searchQuery = ref("");
const statusFilter = ref("全部");
const promptOpen = ref(false);
const editingPromptName = ref<string | null>(null);
const promptForm = reactive({
  name: "",
  version: "v0.1",
  status: "草稿",
  content: "",
});
const statuses = ["全部", "生产中", "草稿"];
function mapPrompt(item: Record<string, unknown>, fallback?: PromptRecord): PromptRecord {
  return {
    id: item.id as number | string | undefined ?? fallback?.id,
    name: String(item.scene || fallback?.name || ""),
    version: String(item.versionNo || fallback?.version || ""),
    updated: String(item.updatedAt || fallback?.updated || "—"),
    status: item.status === "ACTIVE" ? "生产中" : item.status === "DRAFT" ? "草稿" : fallback?.status || "草稿",
    content: String(item.systemPrompt || fallback?.content || ""),
  };
}
onMounted(async () => {
  try {
    const remote = await settingsApi.prompts.list(workspaceId.value);
    prompts.value = remote.map((item) => mapPrompt(item));
  } catch {
    notify("Prompt 配置加载失败");
  }
});
const filteredPrompts = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return prompts.value.filter(
    (prompt) =>
      (statusFilter.value === "全部" || prompt.status === statusFilter.value) &&
      (!query || prompt.name.toLowerCase().includes(query)),
  );
});
const dialogTitle = computed(() =>
  editingPromptName.value ? "编辑 Prompt 版本" : "新建 Prompt",
);

function openCreate() {
  editingPromptName.value = null;
  Object.assign(promptForm, {
    name: "",
    version: "v0.1",
    status: "草稿",
    content: "",
  });
  promptOpen.value = true;
}

function openEdit(prompt: (typeof prompts.value)[number]) {
  editingPromptName.value = prompt.name;
  Object.assign(promptForm, {
    name: prompt.name,
    version: prompt.version,
    status: prompt.status,
    content: prompt.content,
  });
  promptOpen.value = true;
}

async function savePrompt() {
  if (
    !promptForm.name.trim() ||
    !promptForm.version.trim() ||
    !promptForm.content.trim()
  ) {
    notify("请填写 Prompt 名称、版本和内容");
    return;
  }
  if (editingPromptName.value) {
    const prompt = prompts.value.find(
      (item) => item.name === editingPromptName.value,
    );
    if (!prompt) return;
    let updated: Record<string, unknown> = {};
    try {
      updated = await settingsApi.prompts.update(
        workspaceId.value,
        prompt.id ?? editingPromptName.value,
        {
          scene: promptForm.name.trim(),
          versionNo: promptForm.version.trim(),
          status: promptForm.status === "生产中" ? "ACTIVE" : "DRAFT",
          systemPrompt: promptForm.content.trim(),
        },
      );
    } catch {
      notify("Prompt 保存失败");
      return;
    }
    Object.assign(prompt, mapPrompt(updated, {
      ...prompt,
      name: promptForm.name.trim(),
      version: promptForm.version.trim(),
      status: promptForm.status,
      content: promptForm.content.trim(),
    }));
    notify(`${prompt.name} 已更新`);
  } else {
    try {
      const created = await settingsApi.prompts.create(workspaceId.value, {
        scene: promptForm.name.trim(),
        versionNo: promptForm.version.trim(),
        status: promptForm.status === "生产中" ? "ACTIVE" : "DRAFT",
        systemPrompt: promptForm.content.trim(),
      });
      prompts.value.push(mapPrompt(created, {
        name: promptForm.name.trim(),
        version: promptForm.version.trim(),
        updated: "—",
        status: promptForm.status,
        content: promptForm.content.trim(),
      }));
    } catch {
      notify("Prompt 保存失败");
      return;
    }
    notify("Prompt 已创建");
  }
  promptOpen.value = false;
}

async function togglePromptStatus(prompt: PromptRecord) {
  const nextStatus = prompt.status === "生产中" ? "草稿" : "生产中";
  let updated: Record<string, unknown> = {};
  if (prompt.id) {
    try {
      updated = await settingsApi.prompts.update(workspaceId.value, prompt.id, {
        scene: prompt.name,
        versionNo: prompt.version,
        status: nextStatus === "生产中" ? "ACTIVE" : "DRAFT",
        systemPrompt: prompt.content,
      });
    } catch {
      notify("Prompt 状态更新失败");
      return;
    }
  }
  Object.assign(prompt, mapPrompt(updated, { ...prompt, status: nextStatus }));
  notify(
    `${prompt.name} 已${prompt.status === "生产中" ? "发布" : "移回草稿"}`,
  );
}
</script>

<template>
  <Layout
    eyebrow="WORKSPACE / SETTINGS"
    title="Prompt 版本"
    subtitle="配置工作区的提示词模板、版本状态和发布流程"
  >
    <div class="settings-section prompt-overview">
      <div class="overview-copy">
        <span class="overview-icon"><Sparkles :size="18" /></span>
        <div>
          <h2>Prompt 工作台</h2>
          <p>
            当前管理 {{ prompts.length }} 个 Agent
            Prompt，发布前可以在编辑器中校验内容。
          </p>
        </div>
      </div>
      <button
        class="button button-primary button-sm"
        type="button"
        @click="openCreate"
      >
        <Plus :size="15" />新建 Prompt
      </button>
    </div>
    <div class="settings-section">
      <div class="section-intro">
        <div>
          <h2>Prompt 版本列表</h2>
          <p>
            每个 Prompt 都有独立版本和发布状态，生产版本会被 Agent 默认使用。
          </p>
        </div>
      </div>
      <div class="prompt-toolbar">
        <label class="search-control"
          ><Search :size="14" /><input
            v-model="searchQuery"
            type="search"
            placeholder="搜索 Prompt 名称"
            aria-label="搜索 Prompt 名称" /></label
        ><select v-model="statusFilter" aria-label="筛选 Prompt 状态">
          <option v-for="status in statuses" :key="status">{{ status }}</option>
        </select>
      </div>
      <div class="prompt-list">
        <div
          v-for="prompt in filteredPrompts"
          :key="prompt.name"
          class="prompt-row"
        >
          <span class="prompt-icon"><FileCode2 :size="16" /></span
          ><span class="prompt-copy"
            ><code>{{ prompt.name }}</code
            ><small
              >{{ prompt.updated }} · {{ prompt.content.slice(0, 42)
              }}{{ prompt.content.length > 42 ? "…" : "" }}</small
            ></span
          ><span class="prompt-version">{{ prompt.version }}</span
          ><span
            class="status-badge"
            :class="
              prompt.status === '生产中' ? 'status-indexed' : 'status-muted'
            "
            ><i />{{ prompt.status }}</span
          ><button
            class="text-button"
            type="button"
            @click="togglePromptStatus(prompt)"
          >
            {{ prompt.status === "生产中" ? "移回草稿" : "发布" }}</button
          ><button
            class="icon-button small"
            type="button"
            :aria-label="`编辑${prompt.name}`"
            @click="openEdit(prompt)"
          >
            <Edit3 :size="14" />
          </button>
        </div>
        <p v-if="!filteredPrompts.length" class="empty-state">
          {{ prompts.length ? "没有匹配的 Prompt。" : "暂无 Prompt 配置，创建后会显示后端保存的版本。" }}
        </p>
      </div>
    </div>
    <div class="settings-section version-note">
      <CheckCircle2 :size="16" />
      <div>
        <strong>发布建议</strong>
        <p>
          先保存为草稿并完成评估，再将版本切换为生产中，避免影响正在运行的调研。
        </p>
      </div>
    </div>

    <Dialog v-model:open="promptOpen"
      ><DialogContent class="prompt-dialog sm:max-w-3xl"
        ><DialogHeader
          ><DialogTitle>{{ dialogTitle }}</DialogTitle
          ><DialogDescription
            >保存后可以继续编辑，只有状态为“生产中”的版本会被 Agent
            调用。</DialogDescription
          ></DialogHeader
        >
        <div class="form-stack">
          <label class="field-label"
            >Prompt 名称<input
              v-model="promptForm.name"
              :disabled="Boolean(editingPromptName)"
              placeholder="例如：research-planner"
          /></label>
          <div class="form-grid">
            <label class="field-label"
              >版本号<input
                v-model="promptForm.version"
                placeholder="v0.1" /></label
            ><label class="field-label"
              >发布状态<select v-model="promptForm.status">
                <option>草稿</option>
                <option>生产中</option>
              </select></label
            >
          </div>
          <label class="field-label"
            >Prompt 内容<textarea
              v-model="promptForm.content"
              rows="9"
              placeholder="输入系统提示词内容"
            />
          </label>
        </div>
        <DialogFooter
          ><button
            class="button button-secondary"
            type="button"
            @click="promptOpen = false"
          >
            取消</button
          ><button
            class="button button-primary"
            type="button"
            @click="savePrompt"
          >
            保存版本
          </button></DialogFooter
        ></DialogContent
      ></Dialog
    >
  </Layout>
</template>

<style scoped>
.section-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.prompt-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: linear-gradient(
    110deg,
    color-mix(in oklab, var(--violet) 6%, var(--surface)),
    var(--surface)
  );
}
.overview-copy {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.overview-icon {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.5625rem;
  color: #6e62d6;
  background: #eeebff;
}
.overview-copy h2 {
  margin: 0;
  color: var(--workspace-text);
  font-size: 0.875rem;
}
.overview-copy p {
  margin: 0.3125rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.625rem;
}
.prompt-toolbar {
  display: flex;
  gap: 0.5rem;
  max-width: 48.75rem;
  margin-bottom: 1rem;
}
.search-control {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  min-width: 0;
  flex: 1;
  padding: 0 0.625rem;
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  color: var(--workspace-muted);
  background: var(--surface-soft);
}
.search-control:focus-within {
  border-color: var(--teal);
  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 16%, transparent);
}
.search-control input {
  width: 100%;
  border: 0;
  outline: 0;
  padding: 0.5rem 0;
  background: transparent;
  color: var(--workspace-text);
  font: inherit;
  font-size: 0.625rem;
}
.prompt-toolbar > select {
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;
  padding: 0.5rem 0.625rem;
  color: var(--workspace-text);
  background: var(--surface);
  font: inherit;
  font-size: 0.625rem;
}
.prompt-list {
  max-width: 48.75rem;
  border: 0.0625rem solid #e7eeee;
  border-radius: 0.5rem;
  overflow: hidden;
}
.prompt-row {
  min-height: 4rem;
  padding: 0.625rem 0.8125rem;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  border-bottom: 0.0625rem solid #edf1f1;
}
.prompt-row:last-child {
  border-bottom: 0;
}
.prompt-icon {
  display: grid;
  place-items: center;
  width: 1.875rem;
  height: 1.875rem;
  flex: 0 0 auto;
  border-radius: 0.5rem;
  color: #6e62d6;
  background: #f0eeff;
}
.prompt-copy {
  min-width: 0;
  flex: 1;
}
.prompt-copy code,
.prompt-copy small {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.prompt-copy code {
  color: #4e5ece;
  font-size: 0.625rem;
}
.prompt-copy small {
  margin-top: 0.25rem;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.prompt-version {
  min-width: 2.5rem;
  color: var(--workspace-text);
  font-size: 0.625rem;
}
.empty-state {
  padding: 1rem;
  color: var(--workspace-muted);
  font-size: 0.625rem;
  text-align: center;
}
.version-note {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  color: #6e62d6;
  background: #faf9ff;
}
.version-note strong {
  display: block;
  color: var(--workspace-text);
  font-size: 0.625rem;
}
.version-note p {
  margin: 0.25rem 0 0;
  color: var(--workspace-muted);
  font-size: 0.5625rem;
}
.prompt-dialog {
  max-width: 42rem !important;
}
.form-stack {
  display: grid;
  gap: 0.875rem;
}
.field-label textarea {
  resize: vertical;
}
@media (max-width: 47.5rem) {
  .prompt-overview {
    align-items: flex-start;
    flex-direction: column;
  }
  .prompt-overview .button {
    width: 100%;
  }
  .prompt-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .prompt-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .prompt-row .status-badge {
    margin-left: 2.5rem;
  }
  .prompt-row .text-button {
    margin-left: auto;
  }
}
</style>
