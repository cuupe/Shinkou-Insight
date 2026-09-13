-- 联网搜索拥有独立的配置边界，不再复用通用工具/连接器配置。
CREATE TABLE IF NOT EXISTS project_web_search_configs (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL DEFAULT 'brave',
    base_url VARCHAR(1000) NOT NULL,
    language VARCHAR(30) NOT NULL DEFAULT 'zh-hans',
    credential_ciphertext TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, created_by)
);

CREATE INDEX IF NOT EXISTS idx_project_web_search_runtime
    ON project_web_search_configs(project_id, created_by, enabled, updated_at DESC);

-- 迁移历史上误放进通用工具表的 Brave 搜索配置，然后从通用连接器列表移除。
INSERT INTO project_web_search_configs(project_id, provider, base_url, language, credential_ciphertext, enabled, created_by)
SELECT
    project_id,
    COALESCE(NULLIF(config ->> 'provider', ''), 'brave'),
    COALESCE(NULLIF(config ->> 'baseUrl', ''), endpoint),
    COALESCE(NULLIF(config ->> 'language', ''), 'zh-hans'),
    credential_ciphertext,
    enabled,
    created_by
FROM project_tool_configs
WHERE connector_type = 'WEB_SEARCH'
   OR LOWER(COALESCE(config ->> 'purpose', '')) = 'web_search'
   OR LOWER(COALESCE(config ->> 'provider', '')) = 'brave'
ON CONFLICT (project_id, created_by) DO NOTHING;

DELETE FROM project_tool_configs
WHERE connector_type = 'WEB_SEARCH'
   OR LOWER(COALESCE(config ->> 'purpose', '')) = 'web_search'
   OR LOWER(COALESCE(config ->> 'provider', '')) = 'brave';
