CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT REFERENCES workspaces(id) ON DELETE SET NULL,
    project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    actor_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(80) NOT NULL,
    resource_type VARCHAR(40) NOT NULL,
    resource_id VARCHAR(80),
    outcome VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace_created
    ON audit_logs(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_project_created
    ON audit_logs(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_created
    ON audit_logs(actor_user_id, created_at DESC);
