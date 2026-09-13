-- Model credentials and routing choices are private to the user who created them.
-- Existing team-scoped rows are retained for their creator and normalized to PERSONAL.
UPDATE project_model_configs
SET scope = 'PERSONAL', updated_at = CURRENT_TIMESTAMP
WHERE scope IS DISTINCT FROM 'PERSONAL';

ALTER TABLE project_model_configs
    ALTER COLUMN scope SET DEFAULT 'PERSONAL',
    ALTER COLUMN scope SET NOT NULL;

ALTER TABLE project_model_configs
    DROP CONSTRAINT IF EXISTS project_model_configs_scope_check;

ALTER TABLE project_model_configs
    ADD CONSTRAINT project_model_configs_scope_check CHECK (scope = 'PERSONAL');

CREATE INDEX IF NOT EXISTS idx_project_model_configs_user_runtime
    ON project_model_configs(project_id, created_by, enabled, updated_at DESC);
