ALTER TABLE action_items
    ADD COLUMN source_report_id BIGINT REFERENCES reports(id),
    ADD COLUMN source_review_run_id BIGINT REFERENCES project_review_runs(id),
    ADD COLUMN source_key VARCHAR(80),
    ADD COLUMN source_report_version VARCHAR(100),
    ADD COLUMN source_excerpt TEXT,
    ADD COLUMN acceptance_criteria TEXT,
    ADD COLUMN blocks_release BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN completion_evidence TEXT,
    ADD COLUMN submitted_by BIGINT REFERENCES users(id),
    ADD COLUMN submitted_at TIMESTAMP,
    ADD COLUMN accepted_by BIGINT REFERENCES users(id),
    ADD COLUMN accepted_at TIMESTAMP,
    ADD COLUMN acceptance_comment TEXT;

CREATE UNIQUE INDEX uq_action_items_report_source ON action_items(source_report_id, source_key)
    WHERE source_report_id IS NOT NULL AND source_key IS NOT NULL;
CREATE INDEX idx_action_items_report_workflow ON action_items(project_id, source_report_id, status);
