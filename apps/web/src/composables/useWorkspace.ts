import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Activity,
  BarChart3,
  Cpu,
  Database,
  FileText,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Network,
  Search,
  Settings2,
  SlidersHorizontal,
  UserRound,
  Users,
} from "@lucide/vue";
import {
  actionItems,
  assets,
  evaluationCases,
  projects,
  playgroundDefaults,
  recentRuns,
  reports,
  retrievalResults,
  researchDefaults,
  stats,
  workspace,
  userProfile,
} from "@/data/mock";
import type { AssetStatus } from "@/data/mock";

const mobileOpen = ref(false);
const searchQuery = ref("");
const assetFilter = ref("全部");
const assetTab = ref("全部");
const uploadInput = ref<HTMLInputElement | null>(null);
const toast = ref("");
const playgroundQuery = ref(playgroundDefaults.query);
const retrievalMode = ref(playgroundDefaults.mode);
const topK = ref(playgroundDefaults.topK);
const rerank = ref(playgroundDefaults.rerank);
const newRunGoal = ref(researchDefaults.goal);
const allowWeb = ref(researchDefaults.allowWeb);
const maxRounds = ref(researchDefaults.maxRounds);
const runStarted = ref(false);
const copied = ref(false);
  const selectedEvidence = ref(0);
  let toastTimer: number | undefined;

const workspaceNav = [
  { label: "概览", icon: LayoutDashboard, name: "workspace-dashboard" },
  { label: "项目", icon: FolderKanban, name: "workspace-projects" },
  { label: "成员与权限", icon: Users, name: "workspace-members" },
];
const projectNav = [
  { label: "项目概览", icon: Gauge, name: "project-overview" },
  { label: "知识资产", icon: Database, name: "project-assets" },
  { label: "检索 Playground", icon: Search, name: "project-playground" },
  { label: "调研运行", icon: Activity, name: "project-runs" },
  { label: "报告", icon: FileText, name: "project-reports" },
  { label: "行动项", icon: ListChecks, name: "project-action-items" },
  { label: "评估", icon: BarChart3, name: "project-evaluation" },
];
const settingsNav = [
  { label: "个人设置", icon: UserRound, name: "user-settings" },
  { label: "工作区设置", icon: Settings2, name: "workspace-settings" },
  { label: "模型配置", icon: Cpu, name: "settings-models" },
  { label: "工具与连接器", icon: Network, name: "settings-tools" },
  { label: "Prompt 版本", icon: SlidersHorizontal, name: "settings-prompts" },
];

export function useWorkspace() {
  const route = useRoute();
  const router = useRouter();
  const workspaceId = computed(() =>
    String(route.params.workspaceId || "shinkou-labs"),
  );
  const projectId = computed(() =>
    String(route.params.projectId || "queue-selection"),
  );
  const workspaceBase = computed(() => `/workspaces/${workspaceId.value}`);
  const projectBase = computed(
    () => `${workspaceBase.value}/projects/${projectId.value}`,
  );
  const currentName = computed(() =>
    String(route.name || "workspace-dashboard"),
  );
  const isProject = computed(() => currentName.value.startsWith("project-"));
  const selectedProject = computed(
    () => projects.find((item) => item.id === projectId.value) || projects[0],
  );
  const filteredAssets = computed(() =>
    assets.filter((asset) => {
      const queryMatches = asset.name
        .toLowerCase()
        .includes(searchQuery.value.toLowerCase());
      const filterMatches =
        assetFilter.value === "全部" || asset.status === assetFilter.value;
      const tabMatches =
        assetTab.value === "全部" ||
        (assetTab.value === "已索引" && asset.status === "indexed") ||
        (assetTab.value === "处理中" && asset.status === "indexing") ||
        (assetTab.value === "失败" && asset.status === "failed");
      return queryMatches && filterMatches && tabMatches;
    }),
  );
  const pageTitle = computed(
    () =>
      (
        ({
          "workspace-dashboard": "工作区概览",
          "workspace-projects": "项目",
          "workspace-members": "成员与权限",
          "workspace-settings": "工作区设置",
          "user-settings": "个人信息设置",
          "settings-models": "模型配置",
          "settings-tools": "工具与连接器",
          "settings-prompts": "Prompt 版本",
          "project-overview": "项目概览",
          "project-assets": "知识资产",
          "project-asset-detail": "资产详情",
          "project-playground": "检索 Playground",
          "project-new-run": "创建调研",
          "project-runs": "调研运行",
          "project-run-detail": "运行工作台",
          "project-reports": "报告",
          "project-action-items": "行动项",
          "project-evaluation": "评估",
        }) as Record<string, string>
      )[currentName.value] || "工作台",
  );

  function routeTo(name: string) {
    mobileOpen.value = false;
    return name.startsWith("project-")
      ? {
          name,
          params: {
            workspaceId: workspaceId.value,
            projectId: projectId.value,
          },
        }
      : { name, params: { workspaceId: workspaceId.value } };
  }
  function notify(message: string) {
    toast.value = message;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.value = "";
    }, 2600);
  }
  function openUpload() {
    uploadInput.value?.click();
  }
  function onFilesSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    const selectedFiles = Array.from(input.files || []);
    if (!selectedFiles.length) return;

    const now = Date.now();
    selectedFiles.forEach((file, index) => {
      const asset = {
        id: `asset-local-${now}-${index}`,
        name: file.name,
        type: file.name.split(".").pop()?.toUpperCase() || "FILE",
        size: file.size > 1024 * 1024
          ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
          : `${Math.max(1, Math.round(file.size / 1024))} KB`,
        uploader: userProfile.name,
        updated: "刚刚",
        chunks: 0,
        progress: 12,
        status: "indexing" as AssetStatus,
        reason: "",
      };
      assets.unshift(asset);

      window.setTimeout(() => {
        asset.status = "indexed";
        asset.progress = 100;
        asset.chunks = Math.max(1, Math.ceil(file.size / 1800));
        asset.updated = "刚刚完成";
      }, 1100 + index * 250);
    });

    input.value = "";
    notify(`已添加 ${selectedFiles.length} 个文件，正在建立索引`);
  }
  function retryAsset(name: string) {
    const asset = assets.find((item) => item.name === name);
    if (!asset) return;

    asset.status = "indexing";
    asset.progress = 18;
    asset.reason = "";
    notify(`已重新开始索引「${name}」`);
    window.setTimeout(() => {
      asset.status = "indexed";
      asset.progress = 100;
      asset.chunks = Math.max(asset.chunks || 0, 12);
      asset.updated = "刚刚完成";
    }, 1200);
  }
  function copyEvidence() {
    copied.value = true;
    notify("证据片段已复制");
    window.setTimeout(() => {
      copied.value = false;
    }, 1800);
  }
  function startRun() {
    runStarted.value = true;
    const runId = `run-local-${Date.now()}`;
    recentRuns.unshift({
      id: runId,
      project: selectedProject.value?.name || "当前项目",
      title: newRunGoal.value.slice(0, 34) || "未命名调研",
      status: "running",
      statusLabel: "运行中",
      time: "刚刚",
      duration: "0m 00s",
      tokens: "0",
    });
    notify("调研任务已创建，正在运行");
    window.setTimeout(() => {
      const run = recentRuns.find((item) => item.id === runId);
      if (!run) return;
      run.status = "completed";
      run.statusLabel = "已完成";
      run.duration = "1m 24s";
      run.tokens = "12.6k";
      run.time = "刚刚完成";
      notify("调研已完成，可查看运行结果");
    }, 1800);
  }
  function statusLabel(status: string) {
    return (
      (
        {
          indexed: "已索引",
          indexing: "索引中",
          failed: "失败",
          completed: "已完成",
          running: "运行中",
        } as Record<string, string>
      )[status] || status
    );
  }
  function statusClass(status: string) {
    return `status-${status}`;
  }
  function iconForStat(icon: string) {
    return (
      (
        {
          folder: FolderKanban,
          layers: Database,
          activity: Activity,
          check: BarChart3,
        } as Record<string, typeof FolderKanban>
      )[icon] || FolderKanban
    );
  }

  return {
    workspace,
    router,
    workspaceId,
    projectId,
    workspaceBase,
    projectBase,
    currentName,
    isProject,
    selectedProject,
    filteredAssets,
    pageTitle,
    workspaceNav,
    projectNav,
    settingsNav,
    mobileOpen,
    searchQuery,
    assetFilter,
    assetTab,
    uploadInput,
    toast,
    playgroundQuery,
    retrievalMode,
    topK,
    rerank,
    newRunGoal,
    allowWeb,
    maxRounds,
    runStarted,
    copied,
    selectedEvidence,
    stats,
    assets,
    projects,
    recentRuns,
    reports,
    actionItems,
    evaluationCases,
    retrievalResults,
    routeTo,
    notify,
    openUpload,
    onFilesSelected,
    retryAsset,
    copyEvidence,
    startRun,
    statusLabel,
    statusClass,
    iconForStat,
  };
}
