CREATE TABLE IF NOT EXISTS agent_threads (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_by BIGINT NOT NULL REFERENCES users(id),
    thread_key VARCHAR(120) NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT '新建对话',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, created_by, thread_key)
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id BIGINT NOT NULL REFERENCES agent_threads(id) ON DELETE CASCADE,
    client_message_id VARCHAR(120) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'STREAMING',
    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(thread_id, client_message_id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key VARCHAR(120) NOT NULL UNIQUE,
    thread_id BIGINT NOT NULL REFERENCES agent_threads(id) ON DELETE CASCADE,
    user_message_id BIGINT NOT NULL REFERENCES agent_messages(id),
    assistant_message_id BIGINT NOT NULL REFERENCES agent_messages(id),
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    error_message VARCHAR(1000),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_run_events (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    event_type VARCHAR(40) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_attachments (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    uploaded_by BIGINT NOT NULL REFERENCES users(id),
    file_name VARCHAR(255) NOT NULL,
    kind VARCHAR(30) NOT NULL,
    mime_type VARCHAR(120),
    file_size BIGINT NOT NULL DEFAULT 0,
    content BYTEA NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_threads_project ON agent_threads(project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_messages_thread ON agent_messages(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_events_run ON agent_run_events(run_id, id);
CREATE INDEX IF NOT EXISTS idx_agent_attachments_project ON agent_attachments(project_id, created_at DESC);
