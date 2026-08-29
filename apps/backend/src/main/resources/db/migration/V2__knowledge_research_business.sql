CREATE TABLE IF NOT EXISTS knowledge_assets (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(30) NOT NULL,
    mime_type VARCHAR(120),
    language VARCHAR(20),
    file_size BIGINT NOT NULL DEFAULT 0,
    checksum VARCHAR(128),
    storage_key VARCHAR(500),
    content TEXT,
    parse_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    index_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    progress INTEGER NOT NULL DEFAULT 0,
    error_message VARCHAR(1000),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, checksum)
);
CREATE TABLE IF NOT EXISTS asset_chunks (
    id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES knowledge_assets(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    section_title VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset_id, chunk_index)
);
CREATE TABLE IF NOT EXISTS research_runs (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id),
    title VARCHAR(255) NOT NULL,
    goal TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message VARCHAR(1000),
    created_by BIGINT NOT NULL REFERENCES users(id),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id),
    run_id BIGINT REFERENCES research_runs(id),
    title VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    content TEXT NOT NULL DEFAULT '',
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS action_items (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id),
    title VARCHAR(255) NOT NULL,
    description VARCHAR(1000),
    owner_id BIGINT REFERENCES users(id),
    due_at DATE,
    priority VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_assets_project ON knowledge_assets(project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_project ON research_runs(project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_project ON reports(project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_items_project ON action_items(project_id, status, updated_at DESC);