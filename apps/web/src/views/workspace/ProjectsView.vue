<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ArrowRight, FolderKanban, MoreHorizontal, Plus } from "@lucide/vue";

import PageHeader from "@/components/common/PageHeader.vue";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { useWorkspace } from "@/composables/useWorkspace";
import { projectApi } from "@/api/projects";
import { getApiErrorMessage } from "@/api/core";

const { projects, workspaceId, router, notify } = useWorkspace();

const createOpen = ref(false);
const creating = ref(false);
const formError = ref("");

const menuProjectId = ref<number | string | null>(null);

const editOpen = ref(false);
const editingProject = ref<(typeof projects)[number] | null>(null);

const deleteOpen = ref(false);
const deletingProject = ref<(typeof projects)[number] | null>(null);

/**
 * 项目分页
 *
 * 桌面端：
 * 3 列 × 2 行 = 6 个项目 / 页
 *
 * 小屏虽然列数会减少，但仍然保持每页 6 个项目。
 */
const currentPage = ref(1);
const pageSize = 6;

const totalPages = computed(() =>
  Math.max(1, Math.ceil(projects.length / pageSize)),
);

const paginatedProjects = computed(() => {
  const start = (currentPage.value - 1) * pageSize;

  return projects.slice(start, start + pageSize);
});

const form = reactive({
  name: "",
  description: "",
  visibility: "workspace",
  color: "#14b8a6",
});

const canSubmit = computed(
  () => form.name.trim().length >= 2 && !creating.value,
);

async function loadProjects() {
  try {
    const remoteProjects = await projectApi.list(workspaceId.value);

    projects.splice(
      0,
      projects.length,
      ...remoteProjects.map((project) => ({
        ...project,
        id: project.id,
        description: project.description || "",
        color: String(project.color || form.color),
        assets: Number(project.assets || 0),
        runs: Number(project.runs || 0),
        reports: Number(project.reports || 0),
      })),
    );

    // 重新加载项目以后，从第一页开始。
    currentPage.value = 1;
  } catch (error) {
    notify(getApiErrorMessage(error, "项目列表加载失败"));
  }
}

/**
 * 跳转到指定页。
 */
function goToPage(page: number) {
  currentPage.value = Math.min(Math.max(page, 1), totalPages.value);

  // 切换页面以后关闭已经打开的项目菜单。
  menuProjectId.value = null;
}

/**
 * 上一页。
 */
function previousPage() {
  if (currentPage.value <= 1) return;

  goToPage(currentPage.value - 1);
}

/**
 * 下一页。
 */
function nextPage() {
  if (currentPage.value >= totalPages.value) return;

  goToPage(currentPage.value + 1);
}

/**
 * 创建项目。
 */
function openCreateProject() {
  formError.value = "";
  createOpen.value = true;
}

function resetProjectForm() {
  form.name = "";
  form.description = "";
  form.visibility = "workspace";
  form.color = "#14b8a6";
  formError.value = "";
}

async function createProject() {
  const name = form.name.trim();

  if (name.length < 2) {
    formError.value = "项目名称至少需要 2 个字符";
    return;
  }

  creating.value = true;
  formError.value = "";

  try {
    const created = await projectApi.create(workspaceId.value, {
      name,
      description: form.description.trim(),
      visibility: form.visibility,
      color: form.color,
    });

    const project = {
      ...created,
      description: created.description || "",
      color: String(created.color || form.color),
      assets: Number(created.assets ?? 0),
      runs: Number(created.runs ?? 0),
      reports: Number(created.reports ?? 0),
    };

    projects.unshift(project);

    createOpen.value = false;
    resetProjectForm();

    notify("项目已创建，正在打开项目启动工作台");

    await router.push({
      name: "project-agent-chat",
      params: {
        workspaceId: workspaceId.value,
        projectId: project.id,
      },
    });
  } catch (error) {
    formError.value =
      error instanceof Error ? error.message : "项目创建失败，请稍后重试";
  } finally {
    creating.value = false;
  }
}

/**
 * 项目菜单。
 */
function openProjectMenu(project: (typeof projects)[number]) {
  menuProjectId.value = menuProjectId.value === project.id ? null : project.id;
}

/**
 * 编辑项目。
 */
function openEditProject(project: (typeof projects)[number]) {
  menuProjectId.value = null;
  editingProject.value = project;

  form.name = String(project.name || "");
  form.description = String(project.description || "");
  form.visibility = String(project.visibility || "workspace");
  form.color = String(project.color || "#14b8a6");

  formError.value = "";
  editOpen.value = true;
}

async function saveProjectEdit() {
  const project = editingProject.value;

  if (!project) return;

  const name = form.name.trim();

  if (name.length < 2) {
    formError.value = "项目名称至少需要 2 个字符";
    return;
  }

  creating.value = true;
  formError.value = "";

  try {
    const updated = await projectApi.update(workspaceId.value, project.id, {
      name,
      description: form.description.trim(),
      visibility: form.visibility,
      color: form.color,
    });

    Object.assign(project, {
      name: updated.name || name,
      description: updated.description || "",
      visibility: form.visibility,
      color: String(updated.color || form.color),
    });

    editOpen.value = false;
    editingProject.value = null;

    notify(`项目「${name}」已保存`);
  } catch (error) {
    formError.value =
      error instanceof Error ? error.message : "项目保存失败，请稍后重试";
  } finally {
    creating.value = false;
  }
}

/**
 * 归档 / 恢复项目。
 */
async function toggleProjectArchive(project: (typeof projects)[number]) {
  menuProjectId.value = null;

  const archived = project.status === "ARCHIVED";

  try {
    const updated = archived
      ? await projectApi.restore(workspaceId.value, project.id)
      : await projectApi.archive(workspaceId.value, project.id);

    project.status = updated.status || (archived ? "ACTIVE" : "ARCHIVED");

    notify(
      archived
        ? `项目「${project.name}」已恢复`
        : `项目「${project.name}」已归档`,
    );
  } catch (error) {
    notify(getApiErrorMessage(error, "项目状态更新失败"));
  }
}

/**
 * 删除项目。
 */
function requestDeleteProject(project: (typeof projects)[number]) {
  menuProjectId.value = null;
  deletingProject.value = project;
  deleteOpen.value = true;
}

async function confirmDeleteProject() {
  const project = deletingProject.value;

  if (!project) return;

  try {
    await projectApi.remove(workspaceId.value, project.id);

    const index = projects.findIndex((item) => item.id === project.id);

    if (index >= 0) {
      projects.splice(index, 1);
    }

    /**
     * 删除以后，如果当前页已经不存在，
     * 自动退回最后一页。
     */
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value;
    }

    notify(`项目「${project.name}」已删除`);
  } catch (error) {
    notify(getApiErrorMessage(error, "项目删除失败"));
  } finally {
    deleteOpen.value = false;
    deletingProject.value = null;
  }
}

onMounted(loadProjects);
</script>

<template>
  <PageHeader
    eyebrow="WORKSPACE / PROJECTS"
    title="项目"
    subtitle="管理团队正在进行的知识调研"
  >
    <template #action>
      <button
        class="button button-primary"
        type="button"
        @click="openCreateProject"
      >
        <Plus :size="17" />
        新建项目
      </button>
    </template>
  </PageHeader>

  <!-- 项目 Grid -->
  <div class="project-grid">
    <article
      v-for="project in paginatedProjects"
      :key="project.id"
      class="project-card"
    >
      <div class="project-card-top">
        <span class="project-color" :style="{ background: project.color }" />

        <div class="project-menu-wrap">
          <button
            class="icon-button small"
            type="button"
            :aria-label="`打开项目菜单：${project.name}`"
            @click.stop="openProjectMenu(project)"
          >
            <MoreHorizontal :size="17" />
          </button>

          <div v-if="menuProjectId === project.id" class="project-menu">
            <button type="button" @click.stop="openEditProject(project)">
              编辑项目
            </button>

            <button type="button" @click.stop="toggleProjectArchive(project)">
              {{ project.status === "ARCHIVED" ? "恢复项目" : "归档项目" }}
            </button>

            <button
              class="project-menu-danger"
              type="button"
              @click.stop="requestDeleteProject(project)"
            >
              删除项目
            </button>
          </div>
        </div>
      </div>

      <h2>{{ project.name }}</h2>

      <p>{{ project.description }}</p>

      <div class="project-metrics">
        <span>
          <strong>{{ project.assets }}</strong>
          资产
        </span>

        <span>
          <strong>{{ project.runs }}</strong>
          运行
        </span>

        <span>
          <strong>{{ project.reports }}</strong>
          报告
        </span>
      </div>

      <RouterLink
        class="project-card-link"
        :to="{
          name: 'project-agent-chat',
          params: {
            workspaceId,
            projectId: project.id,
          },
        }"
      >
        启动项目
        <ArrowRight :size="15" />
      </RouterLink>
    </article>
  </div>
  <div v-if="!projects.length" class="empty-state project-empty">
    <FolderKanban :size="22" />
    <strong>暂无项目</strong>
    <span>创建项目后，这里会显示后端返回的项目数据。</span>
  </div>

  <!-- 分页 -->
  <div v-if="totalPages > 1" class="project-pagination" aria-label="项目分页">
    <button
      class="pagination-button"
      type="button"
      :disabled="currentPage === 1"
      @click="previousPage"
    >
      上一页
    </button>

    <div class="pagination-pages">
      <button
        v-for="page in totalPages"
        :key="page"
        class="pagination-page"
        :class="{ active: currentPage === page }"
        type="button"
        :aria-current="currentPage === page ? 'page' : undefined"
        @click="goToPage(page)"
      >
        {{ page }}
      </button>
    </div>

    <button
      class="pagination-button"
      type="button"
      :disabled="currentPage === totalPages"
      @click="nextPage"
    >
      下一页
    </button>
  </div>

  <!-- 创建项目 -->
  <Dialog
    v-model:open="createOpen"
    @update:open="(open) => !open && resetProjectForm()"
  >
    <DialogContent class="create-project-dialog sm:max-w-xl">
      <DialogHeader>
        <DialogTitle>创建新项目</DialogTitle>

        <DialogDescription>
          先定义一个清晰的研究空间，之后可以继续添加知识库资料、调研运行和 Agent
          对话。
        </DialogDescription>
      </DialogHeader>

      <form class="create-project-form" @submit.prevent="createProject">
        <p v-if="formError" class="form-error" role="alert">
          {{ formError }}
        </p>

        <label class="field-label">
          项目名称

          <input
            v-model="form.name"
            autofocus
            maxlength="60"
            placeholder="例如：客服知识库质量评估"
          />

          <small> 用于项目列表、导航和调研记录中识别项目。 </small>
        </label>

        <label class="field-label">
          项目简介

          <textarea
            v-model="form.description"
            rows="4"
            maxlength="240"
            placeholder="说明这个项目要解决的问题或预期产出"
          />

          <small> 可选，后续还可以在项目设置中补充。 </small>
        </label>

        <div class="create-project-options">
          <label class="field-label">
            可见范围

            <select v-model="form.visibility">
              <option value="workspace">工作区成员可见</option>

              <option value="private">仅自己可见</option>
            </select>

            <small> 项目创建后仍可在设置中调整成员权限。 </small>
          </label>

          <label class="field-label">
            项目颜色

            <span class="color-picker-row">
              <input
                v-model="form.color"
                type="color"
                aria-label="选择项目颜色"
              />

              <span>{{ form.color }}</span>
            </span>

            <small> 用于项目列表和左侧导航中的快速识别。 </small>
          </label>
        </div>

        <DialogFooter>
          <button
            class="button button-secondary"
            type="button"
            @click="createOpen = false"
          >
            取消
          </button>

          <button
            class="button button-primary"
            type="submit"
            :disabled="!canSubmit"
          >
            {{ creating ? "创建中…" : "创建项目" }}
          </button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>

  <!-- 编辑项目 -->
  <Dialog
    v-model:open="editOpen"
    @update:open="(open) => !open && (editingProject = null)"
  >
    <DialogContent class="create-project-dialog sm:max-w-xl">
      <DialogHeader>
        <DialogTitle>编辑项目</DialogTitle>

        <DialogDescription>
          更新项目名称和简介，保存后立即生效。
        </DialogDescription>
      </DialogHeader>

      <form class="create-project-form" @submit.prevent="saveProjectEdit">
        <p v-if="formError" class="form-error" role="alert">
          {{ formError }}
        </p>

        <label class="field-label">
          项目名称

          <input v-model="form.name" autofocus maxlength="60" />
        </label>

        <label class="field-label">
          项目简介

          <textarea v-model="form.description" rows="4" maxlength="240" />
        </label>

        <DialogFooter>
          <button
            class="button button-secondary"
            type="button"
            @click="editOpen = false"
          >
            取消
          </button>

          <button
            class="button button-primary"
            type="submit"
            :disabled="!canSubmit"
          >
            {{ creating ? "保存中…" : "保存修改" }}
          </button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>

  <!-- 删除项目确认 -->
  <Dialog v-model:open="deleteOpen">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>删除项目</DialogTitle>

        <DialogDescription>
          删除后「{{
            deletingProject?.name
          }}」的知识资产、调研运行和报告将不可访问，该操作无法撤销。
        </DialogDescription>
      </DialogHeader>

      <DialogFooter>
        <button
          class="button button-secondary"
          type="button"
          @click="deleteOpen = false"
        >
          取消
        </button>

        <button
          class="button button-danger"
          type="button"
          @click="confirmDeleteProject"
        >
          确认删除
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.project-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  align-items: stretch;
  align-content: start;
  overflow: visible;
}

:global(.page-content) > .project-grid {
  flex: 0 0 auto;
  overflow: visible;
}

.project-card {
  min-width: 0;
  min-height: 11.75rem;
  height: auto;
  box-sizing: border-box;

  display: flex;
  flex-direction: column;

  background: var(--surface);
  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.75rem;

  padding: 1.25rem 1.5rem 1.125rem;

  box-shadow: 0 0.4375rem 1.4375rem rgba(21, 53, 52, 0.035);

  text-align: left;

  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.project-card:not(.project-create-card):hover {
  border-color: color-mix(in oklab, var(--teal) 38%, var(--workspace-border));

  box-shadow: 0 0.8125rem 1.75rem rgba(21, 53, 52, 0.09);
}

.project-card:focus-within {
  border-color: var(--teal);

  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 15%, transparent);
}

/* =========================================================
   Card Header
   ========================================================= */

.project-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.project-color {
  width: 0.625rem;
  height: 0.625rem;

  border-radius: 0.25rem;

  display: inline-block;
}

.project-color.large {
  width: 0.75rem;
  height: 0.75rem;
}

/* =========================================================
   Project Menu
   ========================================================= */

.project-menu-wrap {
  position: relative;
}

.project-menu {
  position: absolute;

  top: calc(100% + 0.375rem);
  right: 0;

  z-index: 15;

  display: grid;

  min-width: 7.5rem;
  padding: 0.3125rem;

  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;

  background: var(--surface);

  box-shadow: 0 0.5rem 1.5rem rgb(21 53 52 / 12%);
}

.project-menu button {
  border: 0;
  border-radius: 0.375rem;

  padding: 0.4375rem 0.625rem;

  background: transparent;
  color: var(--workspace-text);

  font: inherit;
  font-size: 0.75rem;

  text-align: left;

  cursor: pointer;
}

.project-menu button:hover {
  background: var(--surface-soft);
}

.project-menu-danger {
  color: var(--red, #d14343);
}

.project-menu-danger:hover {
  background: #fff0f0;
}

/* =========================================================
   Card Content
   ========================================================= */

.project-card h2 {
  color: var(--workspace-text);

  font-size: 1rem;
  line-height: 1.4;
  letter-spacing: -0.03em;

  margin: 0.875rem 0 0.375rem;

  min-height: 1.4em;

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-card p {
  color: var(--workspace-muted);

  font-size: 0.8125rem;
  line-height: 1.6;

  height: auto;
  min-height: 2.75rem;
  max-height: 2.75rem;

  margin: 0;

  overflow: hidden;

  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

/* =========================================================
   Metrics
   ========================================================= */

.project-metrics {
  display: flex;
  gap: 1.25rem;

  padding: 0.75rem 0 0.625rem;
  margin-top: auto;

  border-bottom: 0.0625rem solid #edf1f1;

  color: var(--workspace-muted);

  font-size: 0.75rem;
}

.project-metrics strong {
  color: var(--workspace-text);

  font-size: 0.8125rem;

  margin-right: 0.25rem;
}

/* =========================================================
   Open Project
   ========================================================= */

.project-card-link {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;

  width: fit-content;

  color: var(--teal-dark);

  font-size: 0.75rem;
  font-weight: 650;

  text-decoration: none;

  min-height: 1.25rem;
  margin-top: 0.75rem;
  padding-bottom: 0.125rem;
}

.project-card-link:hover {
  gap: 0.5rem;
}

/* =========================================================
   Pagination
   ========================================================= */

.project-pagination {
  display: flex;
  align-items: center;
  justify-content: center;

  gap: 0.75rem;

  margin-top: 1.5rem;
  padding-bottom: 1rem;
}

.pagination-pages {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.pagination-button,
.pagination-page {
  height: 2rem;
  min-width: 2rem;

  padding: 0 0.625rem;

  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;

  background: var(--surface);
  color: var(--workspace-text);

  font: inherit;
  font-size: 0.75rem;

  cursor: pointer;

  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    opacity 0.15s ease;
}

.pagination-button:hover:not(:disabled),
.pagination-page:hover:not(.active) {
  background: var(--surface-soft);
}

.pagination-page.active {
  border-color: var(--teal);
  background: var(--teal);
  color: #fff;
}

.pagination-button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

/* =========================================================
   Danger Button
   ========================================================= */

.button-danger {
  background: #d14343;
  border-color: #d14343;
  color: #fff;
}

.button-danger:hover {
  background: #b83a3a;
}

/* =========================================================
   Dialog
   ========================================================= */

.create-project-dialog {
  max-width: 38rem !important;
}

.create-project-form {
  display: grid;
  gap: 1rem;
}

.create-project-form .field-label {
  display: grid;
  gap: 0.375rem;
}

.create-project-form .field-label small {
  color: var(--workspace-subtle);

  font-size: 0.75rem;
  line-height: 1.4;
}

.create-project-form input:not([type="color"]),
.create-project-form textarea,
.create-project-form select {
  width: 100%;
  box-sizing: border-box;

  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.4375rem;

  padding: 0.625rem 0.6875rem;

  outline: 0;

  color: var(--workspace-text);
  background: var(--surface);

  font: inherit;
  font-size: 0.8125rem;
}

.create-project-form textarea {
  min-height: 6rem;

  resize: vertical;

  line-height: 1.55;
}

.create-project-form input:focus,
.create-project-form textarea:focus,
.create-project-form select:focus {
  border-color: var(--teal);

  box-shadow: 0 0 0 0.1875rem color-mix(in oklab, var(--teal) 12%, transparent);
}

.create-project-options {
  display: grid;

  grid-template-columns: 1fr 1fr;

  gap: 0.875rem;
}

.color-picker-row {
  display: flex;
  align-items: center;

  gap: 0.625rem;

  min-height: 2.25rem;

  color: var(--workspace-muted);

  font-size: 0.75rem;
}

.color-picker-row input[type="color"] {
  width: 2.25rem;
  height: 2.25rem;

  padding: 0.1875rem;

  border: 0.0625rem solid var(--workspace-border);
  border-radius: 0.5rem;

  background: var(--surface);

  cursor: pointer;
}

.form-error {
  margin: 0;
  padding: 0.625rem 0.75rem;

  border: 0.0625rem solid #f0caca;
  border-radius: 0.4375rem;

  color: #a14d4d;
  background: #fff5f5;

  font-size: 0.75rem;
}

.create-project-form .button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* =========================================================
   Responsive
   ========================================================= */

@media (max-width: 68.75rem) {
  .project-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .project-card {
    min-height: 14rem;
    height: auto;
    padding: 1.25rem 1.5rem 1.125rem;
  }
}

@media (max-width: 30rem) {
  .project-grid {
    grid-template-columns: 1fr;
  }

  .project-card {
    min-height: 13.5rem;
    height: auto;
  }

  .project-pagination {
    gap: 0.5rem;
  }

  .pagination-button {
    padding: 0 0.5rem;
  }

  .pagination-pages {
    gap: 0.25rem;
  }

  .pagination-page {
    min-width: 1.875rem;
    padding: 0;
  }

  .create-project-options {
    grid-template-columns: 1fr;
  }
}
</style>
