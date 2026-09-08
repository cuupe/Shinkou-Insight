ALTER TABLE asset_chunks
    ADD COLUMN IF NOT EXISTS start_offset INTEGER,
    ADD COLUMN IF NOT EXISTS end_offset INTEGER,
    ADD COLUMN IF NOT EXISTS parser_version VARCHAR(40),
    ADD COLUMN IF NOT EXISTS chunking_version VARCHAR(40),
    ADD COLUMN IF NOT EXISTS checksum VARCHAR(128),
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(120);

CREATE INDEX IF NOT EXISTS idx_asset_chunks_checksum
    ON asset_chunks(asset_id, checksum);
