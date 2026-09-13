CREATE TABLE IF NOT EXISTS project_review_policies (
    project_id BIGINT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    require_citations BOOLEAN NOT NULL DEFAULT TRUE,
    verify_numbers BOOLEAN NOT NULL DEFAULT TRUE,
    escalate_conflicts BOOLEAN NOT NULL DEFAULT TRUE,
    label_external BOOLEAN NOT NULL DEFAULT TRUE,
    updated_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_review_runs (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    created_by BIGINT NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    indexed_asset_count INTEGER NOT NULL DEFAULT 0,
    asset_count INTEGER NOT NULL DEFAULT 0,
    research_run_count INTEGER NOT NULL DEFAULT 0,
    report_count INTEGER NOT NULL DEFAULT 0,
    evaluation_case_count INTEGER NOT NULL DEFAULT 0,
    action_item_count INTEGER NOT NULL DEFAULT 0,
    require_citations BOOLEAN NOT NULL DEFAULT TRUE,
    verify_numbers BOOLEAN NOT NULL DEFAULT TRUE,
    escalate_conflicts BOOLEAN NOT NULL DEFAULT TRUE,
    label_external BOOLEAN NOT NULL DEFAULT TRUE,
    detail TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_project_review_runs_project
    ON project_review_runs(project_id, created_at DESC);
