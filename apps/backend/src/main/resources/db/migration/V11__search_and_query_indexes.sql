-- PostgreSQL remains the source of truth. This generated vector is only the
-- first-stage lexical index; a later search service can consume the same chunks.
ALTER TABLE asset_chunks
    ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', COALESCE(content, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_asset_chunks_search_vector
    ON asset_chunks USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_asset_chunks_asset_order
    ON asset_chunks(asset_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_knowledge_assets_project_status
    ON knowledge_assets(project_id, index_status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_runs_project_status
    ON research_runs(project_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_project_status
    ON reports(project_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_items_project_status_due
    ON action_items(project_id, status, due_at, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluation_cases_project_updated
    ON evaluation_cases(project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON notifications(recipient_user_id, workspace_id, created_at DESC)
    WHERE read_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_agent_threads_owner_project
    ON agent_threads(created_by, project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_thread_status
    ON agent_runs(thread_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_attachments_owner_project
    ON agent_attachments(uploaded_by, project_id, created_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'knowledge_assets_file_size_nonnegative'
    ) THEN
        ALTER TABLE knowledge_assets
            ADD CONSTRAINT knowledge_assets_file_size_nonnegative CHECK (file_size >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'research_runs_progress_range'
    ) THEN
        ALTER TABLE research_runs
            ADD CONSTRAINT research_runs_progress_range CHECK (progress BETWEEN 0 AND 100);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'agent_attachments_file_size_nonnegative'
    ) THEN
        ALTER TABLE agent_attachments
            ADD CONSTRAINT agent_attachments_file_size_nonnegative CHECK (file_size >= 0);
    END IF;
END $$;
