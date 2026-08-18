export const workspacePath = (workspaceId: number | string) =>
  `/workspaces/${encodeURIComponent(String(workspaceId))}`;

export const projectPath = (
  workspaceId: number | string,
  projectId: number | string,
) =>
  `${workspacePath(workspaceId)}/projects/${encodeURIComponent(String(projectId))}`;
