import { computed, onMounted, reactive } from "vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { runsApi } from "@/api/runs";
import type {
  AgentQueuePriority,
  AgentQueueStatus,
  AgentQueueTask,
} from "@/api/types";

const statusLabels: Record<AgentQueueStatus, string> = {
  queued: "等待中",
  running: "运行中",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

function loadQueue() {
  return [];
}

const queueTasks = reactive<AgentQueueTask[]>(loadQueue());

function persistQueue() {
  // 任务状态以服务端 research_runs 为准，不在浏览器中伪造持久化记录。
}

export function queueStatusLabel(status: AgentQueueStatus) {
  return statusLabels[status];
}

export function useAgentQueue() {
  const { projectId, workspaceId, selectedProject, notify } = useWorkspace();
  const tasks = computed(() =>
    queueTasks.filter(
      (task) => String(task.projectId) === String(projectId.value),
    ),
  );

  async function loadTasks() {
    try {
      const runs = await runsApi.list(workspaceId.value, projectId.value);
      queueTasks.splice(
        0,
        queueTasks.length,
        ...runs.map((run) => ({
          id: String(run.id),
          runId: String(run.id),
          projectId: projectId.value,
          projectName: selectedProject.value?.name || "—",
          title: String(run.title || "未命名运行"),
          source: "research" as const,
          status: mapRunStatus(run.status),
          priority: "normal" as const,
          progress: Number(run.progress || 0),
          currentStep: String(run.currentStep || run.status),
          time: String(run.updatedAt || run.createdAt || ""),
          duration: String(run.duration || "-"),
          tokens: String(run.tokens || "—"),
        })),
      );
    } catch {
      notify("任务列表加载失败");
    }
  }

  onMounted(loadTasks);

  function enqueueTask(input: {
    title: string;
    source: AgentQueueTask["source"];
    threadId?: string;
    priority?: AgentQueuePriority;
  }) {
    const now = Date.now();
    const task: AgentQueueTask = {
      id: `run-local-${now}`,
      runId: `run-local-${now}`,
      projectId: projectId.value,
      projectName: selectedProject.value?.name || "—",
      title: input.title,
      source: input.source,
      threadId: input.threadId,
      status: "queued",
      priority: input.priority || "normal",
      progress: 0,
      currentStep: "等待执行",
      time: "—",
      duration: "—",
      tokens: "—",
    };
    // Agent 运行以服务端 research_runs 为准；在服务端确认前不把本地
    // 临时对象展示为一条真实任务记录。
    return task;
  }

  function updateTask(taskId: string, patch: Partial<AgentQueueTask>) {
    const task = queueTasks.find((item) => item.id === taskId);
    if (!task) return;
    Object.assign(task, patch);
    persistQueue();
  }

  function startTask(taskId: string) {
    const task = queueTasks.find((item) => item.id === taskId);
    if (!task || task.status === "cancelled" || task.status === "completed")
      return;
    task.status = "running";
    task.currentStep = task.currentStep || "等待服务端更新";
    persistQueue();
  }

  function pauseTask(taskId: string) {
    const task = queueTasks.find((item) => item.id === taskId);
    if (!task || task.status !== "running") return;
    task.status = "paused";
    task.currentStep = "已暂停，等待服务端更新";
    persistQueue();
  }

  function resumeTask(taskId: string) {
    const task = queueTasks.find((item) => item.id === taskId);
    if (!task || task.status !== "paused") return;
    task.status = "running";
    task.currentStep = "等待服务端更新";
    persistQueue();
  }

  function cancelTask(taskId: string) {
    const task = queueTasks.find((item) => item.id === taskId);
    if (!task || task.status === "completed" || task.status === "cancelled")
      return;
    task.status = "cancelled";
    task.currentStep = "已取消，不会继续消耗运行资源";
    persistQueue();
  }

  function retryTask(taskId: string) {
    const task = queueTasks.find((item) => item.id === taskId);
    if (!task || !["failed", "cancelled"].includes(task.status)) return;
    task.status = "queued";
    task.progress = 0;
    task.currentStep = "等待重试";
    task.errorMessage = undefined;
    persistQueue();
  }

  function failTask(
    taskId: string,
    message = "运行失败，请检查任务配置后重试",
  ) {
    const task = queueTasks.find((item) => item.id === taskId);
    if (!task) return;
    task.status = "failed";
    task.currentStep = "运行失败，需要重试";
    task.errorMessage = message;
    persistQueue();
  }

  return {
    tasks,
    allTasks: queueTasks,
    enqueueTask,
    updateTask,
    startTask,
    pauseTask,
    resumeTask,
    cancelTask,
    retryTask,
    failTask,
  };
}

function mapRunStatus(status: unknown): AgentQueueStatus {
  const value = String(status).toUpperCase();
  if (value === "RUNNING") return "running";
  if (["COMPLETED", "SUCCESS", "DONE"].includes(value)) return "completed";
  if (["FAILED", "ERROR"].includes(value)) return "failed";
  if (["CANCELLED", "CANCELED"].includes(value)) return "cancelled";
  return "queued";
}
