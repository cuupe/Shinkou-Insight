CREATE TABLE IF NOT EXISTS project_plans (
    project_id BIGINT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    objective TEXT NOT NULL DEFAULT '',
    problem TEXT,
    success_metrics TEXT,
    constraints TEXT,
    owner VARCHAR(120),
    deadline DATE,
    updated_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_project_plans_workspace ON project_plans(workspace_id, updated_at DESC);
