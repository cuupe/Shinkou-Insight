ALTER TABLE knowledge_assets
    ADD COLUMN IF NOT EXISTS source_url VARCHAR(4000);

CREATE INDEX IF NOT EXISTS idx_knowledge_assets_project_source_url
    ON knowledge_assets(project_id, source_url)
    WHERE source_url IS NOT NULL;

-- The original file is already stored in object storage. Full text belongs to
-- asset_chunks for retrieval and new asset rows no longer write this legacy
-- column. Keep the old column during this migration so existing data remains
-- recoverable; it is no longer selected or used by the application.
