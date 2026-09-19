import { computed, onMounted, reactive, ref, watch } from "vue";
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
  MessageCircle,
  Network,
  Search,
  Settings2,
  ShieldCheck,
  UserRound,
  Users,
} from "@lucide/vue";
import type { AssetStatus } from "@/data/options";
import { projectApi } from "@/api/projects";
import { assetsApi } from "@/api/assets";
import { actionItemsApi } from "@/api/action-items";
import { runsApi } from "@/api/runs";
import { reportsApi } from "@/api/reports";
import { evaluationApi } from "@/api/evaluation";
import { authApi } from "@/api/auth";
import { workspaceApi } from "@/api/workspace";
import { statisticsApi } from "@/api/statistics";
import {
  getLastProjectId,
  rememberLastProject,
} from "@/utils/lastProject";
import { formatDateTime } from "@/lib/utils";
import type {
  AuthUser,
  KnowledgeAsset,
  Project,
  ResearchRun,
  StatisticsResponse,
  Workspace,
} from "@/api";

/* 侧边栏开关状态：true = 展开，false = 收起（默认展开） */
const mobileOpen = ref(true);
type ProjectCard = Project & {
  assets: number;
  runs: number;
  reports: number;
  color: string;
};
const projectList = reactive<ProjectCard[]>([]);
type AssetRow = {
  id: string;
  name: string;
  type: string;
  size: string;
  uploader: string;
  updated: string;
  chunks: number;
  progress: number;
  status: AssetStatus;
  reason: string;
};
type ActionItemRow = {
  id: string;
  title: string;
  ownerId?: number;
  owner: string;
  due: string;
  priority: string;
  status: string;
};
type RecentRunRow = {
  id: string;
  projectId?: number;
  project: string;
  title: string;
  status: string;
  statusLabel: string;
  time: string;
  duration: string;
  tokens: string;
};
type ReportRow = {
  id: string;
  projectId?: number;
  title: string;
  project: string;
  version: string;
  updated: string;
  status: string;
  citations: number | null;
  lead: string;
  summary: string;
  recommendation: string;
  recommendationDetail: string;
};
type EvaluationCaseRow = {
  id: string;
  projectId?: number;
  query: string;
  recall: string;
  citation: string;
  json: string;
  status: string;
};
const assets = reactive<AssetRow[]>([]);
const actionItems = reactive<ActionItemRow[]>([]);
const recentRuns = reactive<RecentRunRow[]>([]);
const reports = reactive<ReportRow[]>([]);
const evaluationCases = reactive<EvaluationCaseRow[]>([]);
const statistics = ref<StatisticsResponse | null>(null);
/* 当前登录用户与工作区信息：只在后端返回后填充，避免用演示数据伪造状态。 */
const currentUser = ref<AuthUser | null>(null);
const workspace = reactive({
  name: "",
  slug: "",
  currentRole: "",
  description: "",
  plan: "",
  initials: "",
  usagePercent: "",
});
const availableWorkspaces = reactive<Workspace[]>([]);
const searchQuery = ref("");
const assetTab = ref("全部");
const uploadInput = ref<HTMLInputElement | null>(null);
const toast = ref("");
const playgroundQuery = ref("");
const retrievalMode = ref("HYBRID");
const topK = ref(5);
const rerank = ref(true);
const allowWeb = ref(false);
const outputLanguage = ref("zh-CN");
let toastTimer: number | undefined;

const workspaceNav = [
  { label: "概览", icon: LayoutDashboard, name: "workspace-dashboard" },
  { label: "项目", icon: FolderKanban, name: "workspace-projects" },
  { label: "成员与权限", icon: Users, name: "workspace-members" },
];
const projectNav = [
  { label: "项目概览", icon: Gauge, name: "project-overview" },
  { label: "项目启动", icon: MessageCircle, name: "project-agent-chat" },
  { label: "知识库", icon: Database, name: "project-assets" },
  { label: "检索 Playground", icon: Search, name: "project-playground" },
  { label: "Agent 任务队列", icon: Activity, name: "project-runs" },
  { label: "报告", icon: FileText, name: "project-reports" },
  { label: "行动项", icon: ListChecks, name: "project-action-items" },
  { label: "评估", icon: BarChart3, name: "project-evaluation" },
];
const settingsNav = [
  { label: "个人设置", icon: UserRound, name: "user-settings" },
  { label: "工作区设置", icon: Settings2, name: "workspace-settings" },
  { label: "模型配置", icon: Cpu, name: "settings-models" },
  { label: "工具与连接器", icon: Network, name: "settings-tools" },
  { label: "联网搜索", icon: Search, name: "settings-web-search" },
  { label: "安全审计", icon: ShieldCheck, name: "settings-security" },
];

/* 后端 KnowledgeAsset → 页面展示结构 */
function mapRemoteAsset(asset: KnowledgeAsset) {
  const status: AssetStatus =
    asset.indexStatus === "SUCCESS"
      ? "indexed"
      : asset.indexStatus === "FAILED"
        ? "failed"
        : "indexing";
  return {
    id: String(asset.id),
    name: asset.name,
    type: String(asset.assetType || "FILE"),
    size: asset.fileSize ? `${Math.round(Number(asset.fileSize) / 1024)} KB` : "—",
    uploader: "—",
    updated: formatDateTime(asset.updatedAt, "—"),
    chunks: Number(asset.chunkCount || 0),
    progress: Number(asset.progress ?? (status === "indexed" ? 100 : 0)),
    status,
    reason: String(asset.errorMessage || ""),
  };
}

/* 状态文案映射（知识库/运行共用） */
const statusLabelMap: Record<string, string> = {
  indexed: "已索引",
  indexing: "索引中",
  failed: "失败",
  completed: "已完成",
  running: "运行中",
  pending: "等待执行",
  cancelled: "已取消",
};
function statusLabel(status: string) {
  return statusLabelMap[status] || status;
}

function runDisplayFields(run: ResearchRun) {
  const durationSeconds = Number(run.durationSeconds);
  const tokenCount = Number(run.tokenCount);
  return {
    duration: Number.isFinite(durationSeconds) && durationSeconds >= 0
      ? `${Math.floor(durationSeconds / 60)}m ${durationSeconds % 60}s`
      : "暂无",
    tokens: Number.isFinite(tokenCount) ? tokenCount.toLocaleString() : "暂无",
  };
}

function reportDisplayFields(report: Record<string, unknown>) {
  return {
    version: report.versionNo != null ? `v${String(report.versionNo)}` : "暂无",
    lead: String(report.lead || ""),
    summary: String(report.summary ?? report.markdownContent ?? report.content ?? ""),
    recommendation: String(report.recommendation || ""),
    recommendationDetail: String(report.recommendationDetail || ""),
  };
}

/* 后端 ResearchRun → 页面展示结构 */
function mapRemoteRun(run: ResearchRun, projectName = "", owningProjectId?: number): RecentRunRow {
  const status = String(run.status || "PENDING").toLowerCase();
  return {
    id: String(run.id ?? "—"),
    projectId: owningProjectId,
    project: projectName,
    title: String(run.title || run.goal || "未命名运行"),
    status,
    statusLabel: statusLabel(status),
    time: formatDateTime(run.updatedAt || run.createdAt, "—"),
    duration: runDisplayFields(run).duration,
    tokens: runDisplayFields(run).tokens,
  };
}

function mapRemoteActionItem(item: Record<string, unknown>): ActionItemRow {
  const rawStatus = String(item.status || "TODO").toUpperCase();
  const rawPriority = String(item.priority || "MEDIUM").toUpperCase();
  return {
    id: String(item.id ?? "—"),
    title: String(item.title || "未命名行动项"),
    ownerId: item.ownerId == null ? undefined : Number(item.ownerId),
    owner: String(item.owner || "未分配"),
    due: String(item.dueAt || "待安排"),
    priority: rawPriority === "HIGH" ? "高" : rawPriority === "LOW" ? "低" : "中",
    status:
      rawStatus === "DONE"
        ? "done"
        : rawStatus === "IN_PROGRESS"
          ? "in-progress"
          : rawStatus === "REJECTED"
            ? "rejected"
            : "todo",
  };
}

function mapRemoteReport(report: Record<string, unknown>, projectName = "", owningProjectId?: number): ReportRow {
  const status = String(report.status || "DRAFT").toUpperCase();
  return {
    id: String(report.id ?? "—"),
    projectId: owningProjectId,
    title: String(report.title || "未命名报告"),
    project: projectName,
    updated: formatDateTime(report.updatedAt || report.createdAt, "—"),
    status: status === "PUBLISHED" ? "已发布" : "草稿",
    citations: report.citations == null ? null : Number(report.citations),
    ...reportDisplayFields(report),
  };
}

function mapRemoteEvaluationCase(item: Record<string, unknown>): EvaluationCaseRow {
  return {
    id: String(item.id ?? "—"),
    projectId: item.projectId == null ? undefined : Number(item.projectId),
    query: String(item.query || ""),
    recall: item.recall == null ? "—" : `${String(item.recall)}%`,
    citation: item.citation == null ? "—" : `${String(item.citation)}%`,
    json: item.jsonScore == null ? "—" : `${String(item.jsonScore)}%`,
    status: String(item.status || "review").toLowerCase(),
  };
}

export function useWorkspace() {
  const route = useRoute();
  const router = useRouter();
  const workspaceId = computed(() => {
    const raw = route.params.workspaceId;
    if (raw === undefined || Array.isArray(raw)) return "";

    /* 工作区主键为雪花 ID（long），超出 JS 安全整数，全程按字符串处理 */
    const id = String(raw).trim();
    return /^\d+$/.test(id) ? id : "";
  });
  const projectId = computed(() => {
    const raw = route.params.projectId;
    if (raw === undefined || Array.isArray(raw)) return -1;

    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : -1;
  });
  const workspaceBase = computed(() => `/workspaces/${workspaceId.value}`);
  const projectBase = computed(
    () => `${workspaceBase.value}/projects/${projectId.value}`,
  );
  const currentName = computed(() =>
    String(route.name || "workspace-dashboard"),
  );
  const isProject = computed(() => currentName.value.startsWith("project-"));
  const selectedProject = computed(
    () =>
      projectId.value > 0
        ? projectList.find((item) => item.id === projectId.value)
        : projectList.find(
            (item) => item.id === getLastProjectId(workspaceId.value),
          ) || projectList[0],
  );
  const filteredAssets = computed(() =>
    assets.filter((asset) => {
      const queryMatches = asset.name
        .toLowerCase()
        .includes(searchQuery.value.toLowerCase());
      const tabMatches =
        assetTab.value === "全部" ||
        (assetTab.value === "已索引" && asset.status === "indexed") ||
        (assetTab.value === "处理中" && asset.status === "indexing") ||
        (assetTab.value === "失败" && asset.status === "failed");
      return queryMatches && tabMatches;
    }),
  );
  const pageTitle = computed(
    () =>
      (
        ({
          "workspace-dashboard": "工作区概览",
          "workspace-projects": "项目",
          "workspace-members": "成员与权限",
          notifications: "通知中心",
          "workspace-settings": "工作区设置",
          "user-settings": "个人信息设置",
          "settings-models": "模型配置",
          "settings-tools": "工具与连接器",
          "settings-web-search": "联网搜索",
          "settings-security": "安全审计",
          "project-overview": "项目概览",
          "project-planning": "规划与审查 · 规划",
          "project-agent-chat": "项目启动 / Agent",
          "project-assets": "知识库",
          "project-asset-detail": "知识库详情",
          "project-playground": "检索 Playground",
          "project-runs": "Agent 任务队列",
          "project-run-detail": "运行工作台",
          "project-reports": "报告",
          "project-action-items": "行动项",
          "project-evaluation": "评估",
          "project-review": "规划与审查 · 审查",
        }) as Record<string, string>
      )[currentName.value] || "工作台",
  );

  async function loadWorkspaceData() {
    if (!workspaceId.value) return;

    try {
      const statisticsRequest =
        projectId.value > 0
          ? statisticsApi.project(workspaceId.value, projectId.value)
          : statisticsApi.workspace(workspaceId.value);
      const [me, remoteWorkspace, remoteWorkspaces, remoteProjects, remoteEvaluations, remoteStatistics] =
        await Promise.all([
          authApi.me(),
          workspaceApi.detail(workspaceId.value),
          workspaceApi.list(),
          projectApi.list(workspaceId.value),
          evaluationApi.list(workspaceId.value),
          statisticsRequest,
        ]);

      currentUser.value = me;
      statistics.value = remoteStatistics;
      availableWorkspaces.splice(
        0,
        availableWorkspaces.length,
        ...remoteWorkspaces,
      );
      workspace.name = String(remoteWorkspace.name || "");
      workspace.description = String(remoteWorkspace.description || "");
      workspace.slug = String(remoteWorkspace.code || "");
      workspace.currentRole = String(remoteWorkspace.currentRole || "").toUpperCase();
      workspace.plan = String(remoteWorkspace.plan || "");
      workspace.initials =
        String(remoteWorkspace.initials || "").trim() ||
        workspace.name.trim().slice(0, 2).toUpperCase();

      const projectData = await Promise.all(
        remoteProjects.map(async (project: Project) => {
          const [assetsResult, runsResult, reportsResult, actionsResult] =
            await Promise.allSettled([
              assetsApi.list(workspaceId.value, project.id),
              runsApi.list(workspaceId.value, project.id),
              reportsApi.list(workspaceId.value, project.id),
              actionItemsApi.list(workspaceId.value, project.id),
            ]);
          return {
            project,
            assets: assetsResult.status === "fulfilled" ? assetsResult.value : [],
            runs: runsResult.status === "fulfilled" ? runsResult.value : [],
            reports: reportsResult.status === "fulfilled" ? reportsResult.value : [],
            actions: actionsResult.status === "fulfilled" ? actionsResult.value : [],
          };
        }),
      );

      projectList.splice(
        0,
        projectList.length,
        ...projectData.map(({ project, assets: projectAssets, runs, reports: projectReports }) => ({
          ...project,
          description: project.description || "",
          assets: projectAssets.length,
          runs: runs.length,
          reports: projectReports.length,
          color: String(project.color || "#15b8a6"),
        })),
      );

      // Project pages must always carry a real project ID. When navigation
      // starts from a workspace-level page, prefer the remembered project and
      // only fall back to the first available project. This also prevents the
      // sentinel -1 from reaching project-scoped requests.
      const lastProjectId = getLastProjectId(workspaceId.value);
      const projectToOpen =
        projectData.find(({ project }) => project.id === lastProjectId)?.project ||
        projectData[0]?.project;
      if (isProject.value && projectId.value <= 0 && projectToOpen) {
        await router.replace({
          name: currentName.value,
          params: {
            workspaceId: workspaceId.value,
            projectId: projectToOpen.id,
          },
        });
        return;
      }

      if (
        projectId.value > 0 &&
        projectList.some((project) => project.id === projectId.value)
      ) {
        rememberLastProject(workspaceId.value, projectId.value);
      }

      const currentProjectData = projectData.find(
        ({ project }) => project.id === projectId.value,
      );
      const dashboardRuns = projectData.flatMap(({ project, runs }) =>
        runs.map((run) => mapRemoteRun(run, project.name, project.id)),
      );
      const dashboardReports = projectData.flatMap(({ project, reports: projectReports }) =>
        projectReports.map((report) => mapRemoteReport(report, project.name, project.id)),
      );
      const selectedAssets = currentProjectData?.assets || [];
      const selectedActions = currentProjectData?.actions || [];
      const selectedRuns = currentProjectData?.runs || [];
      const selectedReports = currentProjectData?.reports || [];

      assets.splice(0, assets.length, ...selectedAssets.map(mapRemoteAsset));
      actionItems.splice(
        0,
        actionItems.length,
        ...selectedActions.map(mapRemoteActionItem),
      );
      recentRuns.splice(
        0,
        recentRuns.length,
        ...(projectId.value > 0
          ? selectedRuns.map((run) => mapRemoteRun(run, currentProjectData?.project.name, projectId.value))
          : dashboardRuns),
      );
      reports.splice(
        0,
        reports.length,
        ...(projectId.value > 0
          ? selectedReports.map((report) =>
              mapRemoteReport(report, currentProjectData?.project.name, projectId.value),
            )
          : dashboardReports),
      );
      evaluationCases.splice(
        0,
        evaluationCases.length,
        ...remoteEvaluations
          .filter(
            (item) =>
              projectId.value <= 0 ||
              item.projectId == null ||
              Number(item.projectId) === projectId.value,
          )
          .map(mapRemoteEvaluationCase),
      );
    } catch {
      /* 后端无数据或请求失败时保留空集合，由页面展示对应空状态。 */
    }
  }

  onMounted(loadWorkspaceData);
  watch(workspaceId, (next, previous) => {
    if (next && next !== previous) void loadWorkspaceData();
  });
  watch(projectId, (next, previous) => {
    if (next > 0) rememberLastProject(workspaceId.value, next);
    if (next !== previous && next > 0) void loadWorkspaceData();
  });

  function routeTo(name: string) {
    return name.startsWith("project-")
      ? {
          name,
          params: {
            workspaceId: workspaceId.value,
            projectId:
              projectId.value > 0
                ? projectId.value
                : (selectedProject.value?.id ?? -1),
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
  async function onFilesSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    const selectedFiles = Array.from(input.files || []);
    if (!selectedFiles.length) return;
    input.value = "";
    try {
      const uploaded = await Promise.all(
        selectedFiles.map((file) =>
          assetsApi.upload(workspaceId.value, projectId.value, file),
        ),
      );
      assets.unshift(...uploaded.map(mapRemoteAsset));
      notify(`已添加 ${uploaded.length} 个文件，正在建立索引`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "资料上传失败");
    }
  }
  async function retryAsset(name: string) {
    const asset = assets.find((item) => item.name === name);
    if (!asset) return;

    asset.status = "indexing";
    asset.progress = Math.max(asset.progress || 0, 8);
    asset.reason = "";
    notify(`已重新开始索引「${name}」`);
    try {
      const remote = await assetsApi.reindex(
        workspaceId.value,
        projectId.value,
        asset.id,
      );
      Object.assign(asset, mapRemoteAsset(remote));
    } catch (error) {
      asset.status = "failed";
      asset.reason =
        error instanceof Error ? error.message : "索引重建失败，请再次重试";
      notify(`「${name}」重新索引失败`);
    }
  }
  function statusLabel(status: string) {
    return statusLabelMap[status] || status;
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

  const stats = computed(() => {
    const sum = (pick: (project: ProjectCard) => number) =>
      projectList.reduce((total, project) => total + (pick(project) || 0), 0);
    const summary = statistics.value?.summary;
    return [
      {
        label: "活跃项目",
        value: String(summary?.activeProjectCount ?? projectList.length),
        trend: summary ? "后端实时汇总" : "数据加载中",
        icon: "folder",
        tone: "teal",
      },
      {
        label: "知识库",
        value: String(summary?.assetCount ?? sum((project) => Number(project.assets))),
        trend: summary ? `${summary.indexedAssetCount} 个已索引` : "数据加载中",
        icon: "layers",
        tone: "violet",
      },
      {
        label: "调研运行",
        value: String(summary?.runCount ?? sum((project) => Number(project.runs))),
        trend: summary ? `${summary.runningRunCount} 个运行中` : "数据加载中",
        icon: "activity",
        tone: "amber",
      },
      {
        label: "调研报告",
        value: String(summary?.reportCount ?? sum((project) => Number(project.reports))),
        trend: summary ? `${summary.publishedReportCount} 份已发布` : "数据加载中",
        icon: "check",
        tone: "blue",
      },
    ];
  });

  const displayName = computed(
    () =>
      currentUser.value?.userName ||
      currentUser.value?.phoneNumber ||
      "当前用户",
  );
  const currentWorkspaceRole = computed(
    () =>
      String(
        availableWorkspaces.find(
          (item) => String(item.id) === workspaceId.value,
        )?.currentRole ||
          workspace.currentRole ||
          "MEMBER",
      ).toUpperCase(),
  );
  const isWorkspaceAdmin = computed(() =>
    ["OWNER", "ADMIN"].includes(currentWorkspaceRole.value),
  );
  const roleLabel = computed(() => {
    const role = currentWorkspaceRole.value;
    if (role === "OWNER") return "工作区所有者";
    if (role === "ADMIN") return "工作区管理员";
    return "工作区成员";
  });

  function switchWorkspace(targetId: number | string) {
    const nextWorkspaceId = String(targetId).trim();
    if (!/^\d+$/.test(nextWorkspaceId) || nextWorkspaceId === workspaceId.value) {
      return;
    }
    void router.push({
      name: "workspace-dashboard",
      params: { workspaceId: nextWorkspaceId },
    });
  }

  return {
    workspace,
    availableWorkspaces,
    currentUser,
    currentWorkspaceRole,
    isWorkspaceAdmin,
    displayName,
    roleLabel,
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
    assetTab,
    uploadInput,
    toast,
    playgroundQuery,
    retrievalMode,
    topK,
    rerank,
    allowWeb,
    outputLanguage,
    stats,
    statistics,
    assets,
    projects: projectList,
    recentRuns,
    reports,
    actionItems,
    evaluationCases,
    routeTo,
    notify,
    openUpload,
    onFilesSelected,
    retryAsset,
    statusLabel,
    statusClass,
    iconForStat,
    switchWorkspace,
  };
}
