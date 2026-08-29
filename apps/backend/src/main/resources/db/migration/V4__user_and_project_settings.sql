ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai';
ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_preferences JSONB NOT NULL DEFAULT '{"activity":true,"weeklyDigest":false}'::jsonb;

CREATE TABLE IF NOT EXISTS project_model_configs (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(150) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    auth_type VARCHAR(30) NOT NULL DEFAULT 'API_KEY',
    credential_ciphertext TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS project_tool_configs (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    connector_type VARCHAR(50) NOT NULL DEFAULT 'REST_API',
    endpoint VARCHAR(500) NOT NULL,
    auth_type VARCHAR(30) NOT NULL DEFAULT 'API_KEY',
    credential_ciphertext TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_project_model_configs_project ON project_model_configs(project_id);
CREATE INDEX IF NOT EXISTS idx_project_tool_configs_project ON project_tool_configs(project_id);