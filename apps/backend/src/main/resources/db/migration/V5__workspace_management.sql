CREATE TABLE IF NOT EXISTS workspace_invitations (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    phone_number VARCHAR(11) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'MEMBER',
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    invited_by BIGINT NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_workspace_invitations_lookup ON workspace_invitations(workspace_id, phone_number, status);