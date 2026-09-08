-- Vector payloads live in Milvus. Keep PostgreSQL focused on metadata,
-- source text, citations and keyword search.
DROP INDEX IF EXISTS idx_asset_chunks_embedding_hnsw;

ALTER TABLE asset_chunks
    DROP COLUMN IF EXISTS embedding;

DROP EXTENSION IF EXISTS vector;
