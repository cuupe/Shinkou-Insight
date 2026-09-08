CREATE TABLE IF NOT EXISTS security_harness_runs (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    mode VARCHAR(40) NOT NULL DEFAULT 'STANDARD',
    total_cases INTEGER NOT NULL DEFAULT 0,
    passed_cases INTEGER NOT NULL DEFAULT 0,
    failed_cases INTEGER NOT NULL DEFAULT 0,
    blocked_cases INTEGER NOT NULL DEFAULT 0,
    score NUMERIC(6,2) NOT NULL DEFAULT 0,
    error_message VARCHAR(1000),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS security_harness_results (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES security_harness_runs(id) ON DELETE CASCADE,
    case_code VARCHAR(100) NOT NULL,
    name VARCHAR(160) NOT NULL,
    category VARCHAR(80) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message VARCHAR(1000),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_harness_runs_workspace_created
    ON security_harness_runs(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_harness_results_run
    ON security_harness_results(run_id, id);
