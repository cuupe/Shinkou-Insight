ALTER TABLE project_model_configs
    ADD COLUMN IF NOT EXISTS scope VARCHAR(20);

ALTER TABLE project_tool_configs
    ADD COLUMN IF NOT EXISTS scope VARCHAR(20);

UPDATE project_model_configs
SET scope = CASE
    WHEN UPPER(COALESCE(config ->> 'scope', 'TEAM')) = 'PERSONAL' THEN 'PERSONAL'
    ELSE 'TEAM'
END
WHERE scope IS NULL;

UPDATE project_tool_configs
SET scope = CASE
    WHEN UPPER(COALESCE(config ->> 'sharingScope', config ->> 'scope', 'TEAM')) = 'PERSONAL' THEN 'PERSONAL'
    ELSE 'TEAM'
END
WHERE scope IS NULL;

ALTER TABLE project_model_configs
    ALTER COLUMN scope SET DEFAULT 'TEAM',
    ALTER COLUMN scope SET NOT NULL;

ALTER TABLE project_tool_configs
    ALTER COLUMN scope SET DEFAULT 'TEAM',
    ALTER COLUMN scope SET NOT NULL;

ALTER TABLE project_model_configs
    DROP CONSTRAINT IF EXISTS project_model_configs_scope_check;
ALTER TABLE project_model_configs
    ADD CONSTRAINT project_model_configs_scope_check CHECK (scope IN ('PERSONAL', 'TEAM'));

ALTER TABLE project_tool_configs
    DROP CONSTRAINT IF EXISTS project_tool_configs_scope_check;
ALTER TABLE project_tool_configs
    ADD CONSTRAINT project_tool_configs_scope_check CHECK (scope IN ('PERSONAL', 'TEAM'));

CREATE INDEX IF NOT EXISTS idx_project_model_configs_runtime
    ON project_model_configs(project_id, enabled, scope, created_by, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_tool_configs_runtime
    ON project_tool_configs(project_id, enabled, scope, created_by, updated_at DESC);
