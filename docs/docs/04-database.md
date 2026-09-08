# 04. 数据库设计

## 1. 设计原则

- PostgreSQL 保存业务数据和 AI 运行数据。
- `users` 与工作区、项目、调研和 Agent 数据共用同一个 PostgreSQL 数据库，统一由 Flyway 管理；不使用独立的用户数据库。
- Milvus 保存 Embedding；PostgreSQL 只保存 Chunk 原文、元数据和关键词检索索引。
- 所有项目级表包含 `workspace_id` 和 `project_id`。
- 核心业务使用外键；高频 Trace 表可根据清理策略决定是否使用强外键。
- JSONB 只保存可变结构，不替代核心关系字段。
- 使用 Flyway / Liquibase 管理迁移。

## 2. 扩展

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

`pg_trgm` 为可选项，用于模糊搜索；全文检索也可使用 PostgreSQL `tsvector`。

## 3. 保留的基础表

```text
users
workspaces
workspace_members
invitations
projects
audit_logs
model_configs
tool_configs
```

基础表延续旧项目的邀请激活、多工作区和软删除设计。

## 4. knowledge_assets

```sql
CREATE TABLE knowledge_assets (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,

    name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    mime_type VARCHAR(150),
    language VARCHAR(30),

    storage_path TEXT,
    source_url TEXT,
    file_size BIGINT,
    checksum VARCHAR(128),

    parse_status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    index_status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    chunk_count INTEGER NOT NULL DEFAULT 0,

    metadata JSONB,
    error_message TEXT,

    created_by BIGINT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
```

约束：

```sql
CREATE INDEX idx_assets_workspace_project
ON knowledge_assets(workspace_id, project_id)
WHERE deleted_at IS NULL;

CREATE INDEX idx_assets_checksum
ON knowledge_assets(workspace_id, project_id, checksum)
WHERE deleted_at IS NULL;
```

## 5. document_chunks

向量维度必须由实际 Embedding 模型决定，以下 `1024` 仅为设计示例。

```sql
CREATE TABLE document_chunks (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    asset_id BIGINT NOT NULL,

    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_tsv TSVECTOR,

    page_number INTEGER,
    section_title TEXT,
    start_offset INTEGER,
    end_offset INTEGER,
    token_count INTEGER,

    metadata JSONB,
    checksum VARCHAR(128),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uk_asset_chunk UNIQUE(asset_id, chunk_index)
);
```

索引：

```sql
CREATE INDEX idx_chunks_workspace_project
ON document_chunks(workspace_id, project_id);

CREATE INDEX idx_chunks_asset
ON document_chunks(asset_id);

CREATE INDEX idx_chunks_fts
ON document_chunks USING GIN(content_tsv);

-- 向量字段和 ANN 索引由 Milvus collection 管理。
```

开发早期数据量少时可以先使用精确检索，避免过早调参。

## 6. embedding_jobs

```sql
CREATE TABLE embedding_jobs (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    asset_id BIGINT NOT NULL,

    job_type VARCHAR(50) NOT NULL DEFAULT 'INDEX_ASSET',
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    total_chunks INTEGER NOT NULL DEFAULT 0,
    processed_chunks INTEGER NOT NULL DEFAULT 0,

    embedding_model VARCHAR(255),
    embedding_dimension INTEGER,
    chunking_version VARCHAR(50),

    error_code VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 7. research_runs

```sql
CREATE TABLE research_runs (
    id BIGSERIAL PRIMARY KEY,
    run_no VARCHAR(100) NOT NULL UNIQUE,

    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,

    goal TEXT NOT NULL,
    run_type VARCHAR(50) NOT NULL DEFAULT 'RESEARCH',
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    current_node VARCHAR(100),
    progress INTEGER NOT NULL DEFAULT 0,

    allow_web_search BOOLEAN NOT NULL DEFAULT FALSE,
    max_rounds INTEGER NOT NULL DEFAULT 3,
    current_round INTEGER NOT NULL DEFAULT 0,

    config_snapshot JSONB,
    plan JSONB,
    final_summary TEXT,

    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    estimated_cost NUMERIC(18,6) NOT NULL DEFAULT 0,

    error_code VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 8. run_steps

```sql
CREATE TABLE run_steps (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,

    node_name VARCHAR(100) NOT NULL,
    node_type VARCHAR(50) NOT NULL,
    sequence_no INTEGER NOT NULL,
    attempt_no INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',

    input_summary JSONB,
    output_summary JSONB,
    prompt_name VARCHAR(100),
    prompt_version VARCHAR(50),
    model_name VARCHAR(255),

    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    latency_ms INTEGER,

    error_code VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 9. agent_tool_calls

```sql
CREATE TABLE agent_tool_calls (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL,
    step_id BIGINT,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,

    tool_call_id VARCHAR(100),
    tool_name VARCHAR(100) NOT NULL,
    tool_version VARCHAR(50),
    arguments JSONB,
    result_summary JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',

    latency_ms INTEGER,
    error_code VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

大结果不要直接全部写进 `result_summary`，保存摘要和对象存储引用。

## 10. evidence_items

```sql
CREATE TABLE evidence_items (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,

    source_type VARCHAR(50) NOT NULL,
    support_type VARCHAR(50) NOT NULL,
    question_id VARCHAR(100),

    claim TEXT,
    quote TEXT NOT NULL,

    chunk_id BIGINT,
    source_title TEXT,
    source_url TEXT,
    page_number INTEGER,
    section_title TEXT,

    retrieval_score NUMERIC(10,6),
    rerank_score NUMERIC(10,6),
    confidence NUMERIC(5,4),
    metadata JSONB,

    created_by_step_id BIGINT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 11. research_findings 与关联表

```sql
CREATE TABLE research_findings (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,

    finding_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    confidence NUMERIC(5,4),
    severity VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE finding_evidences (
    finding_id BIGINT NOT NULL,
    evidence_id BIGINT NOT NULL,
    PRIMARY KEY(finding_id, evidence_id)
);
```

## 12. research_reports

```sql
CREATE TABLE research_reports (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    run_id BIGINT,

    title VARCHAR(255) NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    version_no INTEGER NOT NULL DEFAULT 1,

    markdown_content TEXT NOT NULL,
    structured_content JSONB,
    generation_snapshot JSONB,

    created_by BIGINT,
    generated_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE TABLE report_citations (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NOT NULL,
    section_key VARCHAR(100),
    statement_key VARCHAR(100),
    evidence_id BIGINT NOT NULL,
    citation_order INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 13. action_items

```sql
CREATE TABLE action_items (
    id BIGSERIAL PRIMARY KEY,
    workspace_id BIGINT NOT NULL,
    project_id BIGINT NOT NULL,
    run_id BIGINT,
    report_id BIGINT,

    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(50) NOT NULL DEFAULT 'MEDIUM',
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    owner_id BIGINT,
    due_at TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 14. Prompt 与评估

```text
prompt_templates
prompt_versions
evaluation_datasets
evaluation_cases
evaluation_runs
evaluation_case_results
human_feedback
```

重要字段：

```text
Prompt：scene / version / system_prompt / user_template / schema / status
Evaluation：dataset_version / config_snapshot / metrics / case_result
Feedback：run_id / report_id / rating / accepted / correction
```

## 15. 可选微调表

```text
training_datasets
training_samples
fine_tune_jobs
model_versions
```

只在 LoRA 阶段创建，避免 MVP 数据模型过度膨胀。

## 16. 数据清理

建议保留：

- 报告、引用、审计：长期。
- Run 和 Step：至少 90 天或项目周期。
- 完整工具结果：可缩短，保留摘要。
- 上传原文件：随资产生命周期。
- 文档 Chunk：随资产删除。

删除资产必须使用事务或可靠异步补偿，避免元数据删除而向量残留。
