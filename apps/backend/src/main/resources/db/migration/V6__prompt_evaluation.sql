CREATE TABLE IF NOT EXISTS prompt_versions (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    scene VARCHAR(100) NOT NULL,
    version_no VARCHAR(30) NOT NULL,
    system_prompt TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(workspace_id, scene, version_no)
);
CREATE TABLE IF NOT EXISTS evaluation_cases (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    expected_answer TEXT,
    recall NUMERIC(5,2),
    citation NUMERIC(5,2),
    json_score NUMERIC(5,2),
    status VARCHAR(20) NOT NULL DEFAULT 'REVIEW',
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_workspace ON prompt_versions(workspace_id, scene, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluation_cases_workspace ON evaluation_cases(workspace_id, updated_at DESC);