CREATE TABLE IF NOT EXISTS user_storage_usage (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    used_bytes BIGINT NOT NULL DEFAULT 0 CHECK (used_bytes >= 0),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

WITH usage_by_user AS (
    SELECT uploaded_by AS user_id, COALESCE(SUM(file_size), 0)::BIGINT AS used_bytes
    FROM agent_attachments
    GROUP BY uploaded_by
    UNION ALL
    SELECT created_by AS user_id, COALESCE(SUM(file_size), 0)::BIGINT AS used_bytes
    FROM knowledge_assets
    GROUP BY created_by
), totals AS (
    SELECT user_id, SUM(used_bytes)::BIGINT AS used_bytes
    FROM usage_by_user
    GROUP BY user_id
)
INSERT INTO user_storage_usage(user_id, used_bytes)
SELECT user_id, used_bytes FROM totals
ON CONFLICT (user_id) DO UPDATE
SET used_bytes = EXCLUDED.used_bytes,
    updated_at = CURRENT_TIMESTAMP;
