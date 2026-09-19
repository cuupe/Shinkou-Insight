const LAST_PROJECT_KEY = "shinkou-last-project";

export type LastProjectLocation = {
  workspaceId: string;
  projectId: number;
};

export function getLastProject(): LastProjectLocation | null {
  try {
    const raw = localStorage.getItem(LAST_PROJECT_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<LastProjectLocation>;
    const workspaceId = String(parsed.workspaceId || "").trim();
    const projectId = Number(parsed.projectId);

    if (!workspaceId || !Number.isInteger(projectId) || projectId <= 0) {
      return null;
    }

    return { workspaceId, projectId };
  } catch {
    return null;
  }
}

export function getLastProjectId(workspaceId: string | number): number | null {
  const lastProject = getLastProject();
  return lastProject && lastProject.workspaceId === String(workspaceId)
    ? lastProject.projectId
    : null;
}

export function rememberLastProject(
  workspaceId: string | number,
  projectId: string | number,
) {
  const normalizedWorkspaceId = String(workspaceId).trim();
  const normalizedProjectId = Number(projectId);
  if (
    !normalizedWorkspaceId ||
    !Number.isInteger(normalizedProjectId) ||
    normalizedProjectId <= 0
  ) {
    return;
  }

  try {
    localStorage.setItem(
      LAST_PROJECT_KEY,
      JSON.stringify({
        workspaceId: normalizedWorkspaceId,
        projectId: normalizedProjectId,
      } satisfies LastProjectLocation),
    );
  } catch {
    // Storage can be unavailable in private browsing or restricted webviews.
  }
}
