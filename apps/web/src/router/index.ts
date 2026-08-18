import { createRouter, createWebHistory } from "vue-router";
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

export default router;
