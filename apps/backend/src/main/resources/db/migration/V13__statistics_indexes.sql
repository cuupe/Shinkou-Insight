-- 趋势统计按项目和创建时间过滤；复合索引覆盖等值连接与时间范围。
CREATE INDEX IF NOT EXISTS idx_knowledge_assets_project_created
    ON knowledge_assets(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_runs_project_created
    ON research_runs(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_project_created
    ON reports(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_items_project_created
    ON action_items(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evaluation_cases_workspace_project
    ON evaluation_cases(workspace_id, project_id, updated_at DESC);
