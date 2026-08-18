/**
 * 前端接口入口。
 *
 * 具体接口按业务域放在独立文件中；这里仅负责统一导出和保持旧的
 * api.auth / api.workspace / api.project 调用方式，页面无需关心文件拆分。
 */
import { actionItemsApi } from "./action-items";
import { assetsApi } from "./assets";
import { authApi } from "./auth";
import { evaluationApi } from "./evaluation";
import { projectApi } from "./projects";
import { reportsApi } from "./reports";
import { retrievalApi } from "./retrieval";
import { runsApi } from "./runs";
import { workspaceApi } from "./workspace";

export * from "./core";
export * from "./types";

export const api = {
  auth: authApi,
  workspace: workspaceApi,
  project: projectApi,
  assets: assetsApi,
  retrieval: retrievalApi,
  runs: runsApi,
  reports: reportsApi,
  actionItems: actionItemsApi,
  evaluation: evaluationApi,
};
