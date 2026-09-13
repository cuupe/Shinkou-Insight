ALTER TABLE projects ADD COLUMN IF NOT EXISTS chunking_config JSONB NOT NULL DEFAULT '{"strategy":"natural","chunkSize":1200,"chunkOverlap":180,"preserveSections":true}'::jsonb;
