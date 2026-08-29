ALTER TABLE agent_attachments
    ADD COLUMN IF NOT EXISTS storage_key VARCHAR(500);

ALTER TABLE agent_attachments
    ALTER COLUMN content DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_attachments_storage_key
    ON agent_attachments(storage_key)
    WHERE storage_key IS NOT NULL;
