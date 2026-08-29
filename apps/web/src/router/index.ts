import { createRouter, createWebHistory } from "vue-router";
import { authApi } from "@/api/auth";
import { isSessionLocallyInvalid } from "@/utils/request";
import { workspaceApi } from "@/api/workspace";
import AuthLayout from "@/layouts/AuthLayout.vue";
import WorkspaceLayout from "@/layouts/WorkspaceLayout.vue";
import LoginView from "@/views/auth/LoginView.vue";
import RegisterView from "@/views/auth/RegisterView.vue";
import DashboardView from "@/views/workspace/DashboardView.vue";
import ProjectsView from "@/views/workspace/ProjectsView.vue";
import MembersView from "@/views/workspace/MembersView.vue";
import GeneralSettingsView from "@/views/settings/GeneralView.vue";
import UserSettingsView from "@/views/settings/UserSettingsView.vue";
import ModelsSettingsView from "@/views/settings/ModelsView.vue";
import ToolsSettingsView from "@/views/settings/ToolsView.vue";
import PromptsSettingsView from "@/views/settings/PromptsView.vue";
import OverviewView from "@/views/project/OverviewView.vue";
import AssetsView from "@/views/project/AssetsView.vue";
import AssetDetailView from "@/views/project/AssetDetailView.vue";
import PlaygroundView from "@/views/project/PlaygroundView.vue";
import NewResearchView from "@/views/project/NewResearchView.vue";
import RunsView from "@/views/project/RunsView.vue";
import RunDetailView from "@/views/project/RunDetailView.vue";
import ReportsView from "@/views/project/ReportsView.vue";
import ActionItemsView from "@/views/project/ActionItemsView.vue";
import EvaluationView from "@/views/project/EvaluationView.vue";
import AgentWorkspaceView from "@/views/project/AgentWorkspaceView.vue";
import HelpCenterView from "@/views/help/HelpCenterView.vue";
import NotificationsView from "@/views/workspace/NotificationsView.vue";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      redirect: { name: "login" },
    },
    {
      path: "/login",
      component: AuthLayout,
      children: [{ path: "", name: "login", component: LoginView }],
    },
    {
      path: "/register",
      component: AuthLayout,
      children: [{ path: "", name: "register", component: RegisterView }],
    },
    {
      path: "/workspaces/:workspaceId",
      component: WorkspaceLayout,
      children: [
        { path: "", redirect: { name: "workspace-dashboard" } },
        {
          path: "dashboard",
          name: "workspace-dashboard",
          component: DashboardView,
        },
        {
          path: "projects",
          name: "workspace-projects",
          component: ProjectsView,
        },
        {
          path: "members",
          name: "workspace-members",
          component: MembersView,
        },
        {
          path: "help",
          name: "help-center",
          component: HelpCenterView,
        },
        {
          path: "notifications",
          name: "notifications",
          component: NotificationsView,
        },
        {
          path: "settings",
          name: "workspace-settings",
          component: GeneralSettingsView,
        },
        {
          path: "account/settings",
          name: "user-settings",
          component: UserSettingsView,
        },
        {
          path: "settings/models",
          name: "settings-models",
          component: ModelsSettingsView,
        },
        {
          path: "settings/tools",
          name: "settings-tools",
          component: ToolsSettingsView,
        },
        {
          path: "settings/prompts",
          name: "settings-prompts",
          component: PromptsSettingsView,
        },
        {
          path: "projects/:projectId/overview",
          name: "project-overview",
          component: OverviewView,
        },
        {
          path: "projects/:projectId/agent",
          name: "project-agent-chat",
          component: AgentWorkspaceView,
        },
        {
          path: "projects/:projectId/knowledge/assets",
          name: "project-assets",
          component: AssetsView,
        },
        {
          path: "projects/:projectId/knowledge/assets/:assetId",
          name: "project-asset-detail",
          component: AssetDetailView,
        },
        {
          path: "projects/:projectId/knowledge/playground",
          name: "project-playground",
          component: PlaygroundView,
        },
        {
          path: "projects/:projectId/research/new",
          name: "project-new-run",
          component: NewResearchView,
        },
        {
          path: "projects/:projectId/research/runs",
          name: "project-runs",
          component: RunsView,
        },
        {
          path: "projects/:projectId/research/runs/:runId",
          name: "project-run-detail",
          component: RunDetailView,
        },
        {
          path: "projects/:projectId/reports",
          name: "project-reports",
          component: ReportsView,
        },
        {
          path: "projects/:projectId/action-items",
          name: "project-action-items",
          component: ActionItemsView,
        },
        {
          path: "projects/:projectId/evaluation",
          name: "project-evaluation",
          component: EvaluationView,
        },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: { name: "login" },
    },
  ],
});

/* 工作区路由守卫：
 * 1. 未登录跳转登录页；
 * 2. URL 中的 workspaceId 必须是当前用户真实的工作区雪花 ID，
 *    非法/过期时重定向到第一个可用工作区；
 * 3. 用户没有任何工作区时自动创建默认工作区。 */
let workspaceCache: string[] | null = null;

async function loadWorkspaceIds(force = false): Promise<string[]> {
  if (workspaceCache && !force) return workspaceCache;
  let list = await workspaceApi.list();
  if (!list.length) {
    const me = await authApi.me().catch(() => null);
    const created = await workspaceApi.create({
      name: `${me?.userName || "我的"} 的工作区`,
    });
    list = [created];
  }
  workspaceCache = list.map((workspace) => String(workspace.id));
  return workspaceCache;
}

router.beforeEach(async (to) => {
  if (!to.matched.length || !String(to.params.workspaceId ?? "")) {
    return true;
  }
  if (isSessionLocallyInvalid()) {
    return { name: "login" };
  }
  try {
    await authApi.me();
  } catch {
    return { name: "login" };
  }
  const requested = String(to.params.workspaceId);
  try {
    let ids = await loadWorkspaceIds();
    if (!ids.includes(requested)) {
      // 缓存可能已过期，强制刷新一次再判断
      ids = await loadWorkspaceIds(true);
    }
    if (!ids.includes(requested)) {
      return {
        path: to.fullPath.replace(
          `/workspaces/${requested}`,
          `/workspaces/${ids[0]}`,
        ),
      };
    }
  } catch {
    return { name: "login" };
  }
  return true;
});

export default router;
