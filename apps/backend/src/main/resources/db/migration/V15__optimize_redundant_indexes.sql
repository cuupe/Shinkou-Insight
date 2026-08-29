-- All application tables, including users, live in the same PostgreSQL database
-- and are managed by the same Flyway history.

-- V1 already creates the users.phone_number unique constraint. V14 added an
-- equivalent standalone index, which only increases write and storage cost.
DROP INDEX IF EXISTS uq_users_phone_number;

-- The unique constraint already indexes (asset_id, chunk_index).
DROP INDEX IF EXISTS idx_asset_chunks_asset_order;

-- The unique (project_id, name) indexes already cover project_id lookups.
-- Replace the redundant prefix indexes with indexes that also support the
-- existing ORDER BY updated_at DESC list queries.
DROP INDEX IF EXISTS idx_project_model_configs_project;
DROP INDEX IF EXISTS idx_project_tool_configs_project;

CREATE INDEX IF NOT EXISTS idx_workspace_members_workspace_status_created
    ON workspace_members (workspace_id, status, created_at);

CREATE INDEX IF NOT EXISTS idx_project_model_configs_project_updated
    ON project_model_configs (project_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_project_tool_configs_project_updated
    ON project_tool_configs (project_id, updated_at DESC);
