CREATE TABLE IF NOT EXISTS agent_token_usage (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    run_id BIGINT REFERENCES agent_runs(id) ON DELETE SET NULL,
    run_key VARCHAR(120) NOT NULL UNIQUE,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    compressed_context_tokens INTEGER NOT NULL DEFAULT 0,
    context_message_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_token_usage_project_date
    ON agent_token_usage(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_token_usage_workspace_user_date
    ON agent_token_usage(workspace_id, user_id, created_at DESC);
