ALTER TABLE project_review_runs
    ADD COLUMN report_id BIGINT REFERENCES reports(id) ON DELETE SET NULL,
    ADD COLUMN report_title VARCHAR(255),
    ADD COLUMN report_version VARCHAR(80),
    ADD COLUMN snapshot_hash VARCHAR(64),
    ADD COLUMN report_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN checks JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN confirmations JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN decision_comment TEXT,
    ADD COLUMN decided_by BIGINT REFERENCES users(id),
    ADD COLUMN decided_at TIMESTAMP;

CREATE INDEX idx_review_runs_report ON project_review_runs(project_id, report_id, id DESC);
