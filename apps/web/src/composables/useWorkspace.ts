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
  Users,
} from "@lucide/vue";
import {
  actionItems,
  assets,
  evaluationCases,
  projects,
  recentRuns,
  reports,
  retrievalResults,
  stats,
  workspace,
} from "@/data/mock";

const mobileOpen = ref(false);
const searchQuery = ref("");
const assetFilter = ref("全部");
const assetTab = ref("全部");
const uploadInput = ref<HTMLInputElement | null>(null);
const toast = ref("");
const playgroundQuery = ref("消息队列在峰值流量下如何保证可靠投递？");
const retrievalMode = ref("Hybrid");
const topK = ref(5);
const rerank = ref(true);
const newRunGoal = ref(
  "结合内部业务约束，比较 Kafka、RabbitMQ 和 RocketMQ，给出当前阶段的推荐方案、风险和待确认问题。",
);
const allowWeb = ref(true);
const maxRounds = ref(5);
const runStarted = ref(false);
const copied = ref(false);
const selectedEvidence = ref(0);

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
    window.setTimeout(() => {
      toast.value = "";
    }, 2600);
  }
  function openUpload() {
    uploadInput.value?.click();
  }
  function onFilesSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files?.length)
      notify(`已选择 ${input.files.length} 个文件，等待接入上传接口`);
  }
  function retryAsset(name: string) {
    notify(`已准备重试「${name}」，请在 API 层接入实际任务`);
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
    notify("已创建本地演示运行，等待接入调研接口");
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
