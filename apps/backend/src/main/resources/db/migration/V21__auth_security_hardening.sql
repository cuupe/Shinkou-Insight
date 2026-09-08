-- Keep password-change time available for operational audits and future
-- session stores. Existing accounts are treated as having changed it at the
-- migration time; no password material is modified by this migration.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_users_status_phone
    ON users(status, phone_number);
