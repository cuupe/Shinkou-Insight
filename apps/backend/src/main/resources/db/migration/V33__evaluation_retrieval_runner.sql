ALTER TABLE evaluation_cases
    ADD COLUMN IF NOT EXISTS expected_asset VARCHAR(500),
    ADD COLUMN IF NOT EXISTS expected_chunk_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS required_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS forbidden_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS evaluation_result JSONB,
    ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMP;
