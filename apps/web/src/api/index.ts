/**
 * 前端接口入口。
 *
 * 具体接口按业务域放在独立文件中；这里仅负责统一导出和保持旧的
 * api.auth / api.workspace / api.project 调用方式，页面无需关心文件拆分。
 */
import { actionItemsApi } from "./action-items";
import { agentApi } from "./agent";
import { assetsApi } from "./assets";
import { authApi } from "./auth";
import { evaluationApi } from "./evaluation";
import { projectApi } from "./projects";
import { planningApi } from "./planning";
import { reviewApi } from "./review";
import { reportsApi } from "./reports";
import { retrievalApi } from "./retrieval";
import { runsApi } from "./runs";
import { workspaceApi } from "./workspace";
import { settingsApi } from "./settings";
import { notificationsApi } from "./notifications";
import { statisticsApi } from "./statistics";
import { securityApi } from "./security";
import { storageApi } from "./storage";

export * from "./core";
export * from "./types";

export const api = {
  agent: agentApi,
  auth: authApi,
  workspace: workspaceApi,
  project: projectApi,
  planning: planningApi,
  review: reviewApi,
  assets: assetsApi,
  retrieval: retrievalApi,
  runs: runsApi,
  reports: reportsApi,
  actionItems: actionItemsApi,
  evaluation: evaluationApi,
  settings: settingsApi,
  notifications: notificationsApi,
  statistics: statisticsApi,
  security: securityApi,
  storage: storageApi,
};
