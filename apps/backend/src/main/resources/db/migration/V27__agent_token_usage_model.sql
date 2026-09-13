ALTER TABLE agent_token_usage ADD COLUMN IF NOT EXISTS model_name VARCHAR(300);

CREATE INDEX IF NOT EXISTS idx_agent_token_usage_project_user_model
    ON agent_token_usage(project_id, user_id, model_name, created_at DESC);
