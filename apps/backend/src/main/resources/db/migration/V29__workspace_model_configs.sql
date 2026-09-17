-- Model credentials belong to a workspace, not to an individual project.
-- Keep the old table as an archive so existing installations can be migrated
-- without losing encrypted credentials or historical rows.
CREATE TABLE IF NOT EXISTS workspace_model_configs (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(150) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    auth_type VARCHAR(30) NOT NULL DEFAULT 'API_KEY',
    credential_ciphertext TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    default_model BOOLEAN NOT NULL DEFAULT FALSE,
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO workspace_model_configs(
    id, workspace_id, name, provider, model_id, endpoint, auth_type,
    credential_ciphertext, config, enabled, default_model, created_by,
    created_at, updated_at
)
SELECT
    c.id, p.workspace_id, c.name, c.provider, c.model_id, c.endpoint,
    c.auth_type, c.credential_ciphertext, c.config, c.enabled, FALSE,
    c.created_by, c.created_at, c.updated_at
FROM project_model_configs c
JOIN projects p ON p.id = c.project_id
ON CONFLICT (id) DO NOTHING;

-- Existing configurations were previously the only project-local choices.
-- Promote the most recently updated one in each workspace so the migration
-- keeps a usable default while still preserving the original owner.
WITH ranked AS (
    SELECT id, ROW_NUMBER() OVER (
        PARTITION BY workspace_id ORDER BY updated_at DESC, id DESC
    ) AS rank_no
    FROM workspace_model_configs
)
UPDATE workspace_model_configs m
SET default_model = TRUE
FROM ranked r
WHERE m.id = r.id AND r.rank_no = 1;

SELECT setval(
    pg_get_serial_sequence('workspace_model_configs', 'id'),
    COALESCE((SELECT MAX(id) FROM workspace_model_configs), 1),
    TRUE
);

CREATE INDEX IF NOT EXISTS idx_workspace_model_configs_visibility
    ON workspace_model_configs(workspace_id, default_model, created_by, enabled, updated_at DESC);

-- The application no longer writes to or reads from this project-scoped table.
ALTER TABLE project_model_configs RENAME TO legacy_project_model_configs;
