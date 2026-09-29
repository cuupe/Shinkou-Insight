"""Opt-in SQL regression tests; only connection-local temporary tables are written.

Set TEST_POSTGRES_URL to a disposable/test PostgreSQL connection string.
"""

import os
from contextlib import asynccontextmanager

import pytest

from rag.keyword import fetch_keyword_rows
from rag.retriever import PostgresKeywordRetriever


@pytest.fixture
def postgres_pool():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is not set")
    import psycopg

    with psycopg.connect(url, connect_timeout=5, options="-c statement_timeout=5000") as connection:
        connection.execute("CREATE TEMP TABLE projects (id bigint, workspace_id bigint) ON COMMIT DROP")
        connection.execute("CREATE TEMP TABLE knowledge_assets (id bigint, project_id bigint, name text, index_status text) ON COMMIT DROP")
        connection.execute("""CREATE TEMP TABLE asset_chunks (
            id bigint, asset_id bigint, chunk_index int, content text, page_number int, section_title text,
            search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
        ) ON COMMIT DROP""")
        connection.execute("INSERT INTO projects VALUES (8,7),(9,7),(10,99)")
        connection.execute("""INSERT INTO knowledge_assets VALUES
            (12,8,'test.txt','SUCCESS'),(13,8,'noise.txt','SUCCESS'),(14,9,'other-project.txt','SUCCESS'),
            (15,10,'other-workspace.txt','SUCCESS'),(16,8,'failed.txt','FAILED'),(17,8,'indexed.txt','INDEXED')""")
        for chunk_id, asset_id, content in [
            (1, 13, "交通工程项目获得批准"),
            (2, 14, "2029年诺贝尔交通工程奖 谁获得了"),
            (3, 15, "2029年诺贝尔交通工程奖 谁获得了"),
            (4, 16, "2029年诺贝尔交通工程奖 谁获得了"),
            (5, 17, "PostgreSQL MODEL_42 configuration"),
            (6, 13, "MODELx42"),
            (100, 12, "艾伦·莫里斯博士被称为2029年诺贝尔交通工程奖得主。该专家和奖项均为虚构。"),
        ]:
            connection.execute("INSERT INTO asset_chunks(id,asset_id,chunk_index,content) VALUES (%s,%s,%s,%s)",
                               (chunk_id, asset_id, chunk_id, content))

        class Cursor:
            async def execute(self, sql, params):
                self.result = connection.execute(sql, params)

            async def fetchall(self):
                return self.result.fetchall()

        class Pool:
            @asynccontextmanager
            async def connection(self):
                yield self

            @asynccontextmanager
            async def cursor(self):
                yield Cursor()

        yield Pool()
        connection.rollback()


@pytest.mark.asyncio
async def test_sql_ranks_chinese_coverage_before_limit_and_enforces_scope(postgres_pool):
    rows = await fetch_keyword_rows(postgres_pool, 7, 8, "谁获得了2029年诺贝尔交通工程奖", [], 1)
    assert [row[1] for row in rows] == [12]
    assert "艾伦·莫里斯" in rows[0][5]
    assert await fetch_keyword_rows(postgres_pool, 88, 8, "诺贝尔交通工程奖", [], 1) == []
    filtered = await fetch_keyword_rows(postgres_pool, 7, 8, "诺贝尔交通工程奖", [13], 5)
    assert [row[1] for row in filtered] == [13]


@pytest.mark.asyncio
async def test_explicit_filename_query_filters_and_prioritizes_the_named_asset(postgres_pool):
    rows = await fetch_keyword_rows(postgres_pool, 7, 8, "test.txt 的主要内容是什么？", [], 5)

    assert [row[1] for row in rows] == [12]
    assert "艾伦·莫里斯" in rows[0][5]
    assert await fetch_keyword_rows(postgres_pool, 7, 8, "missing.txt 的内容是什么？", [], 5) == []


@pytest.mark.asyncio
async def test_sql_matches_literal_underscores_case_insensitively(postgres_pool):
    rows = await fetch_keyword_rows(postgres_pool, 7, 8, "model_42", [], 5)
    assert [row[1] for row in rows] == [17]
    assert await fetch_keyword_rows(postgres_pool, 7, 8, "unrelatedword", [], 5) == []


@pytest.mark.asyncio
async def test_postgres_adapter_uses_same_ranking(postgres_pool):
    retriever = PostgresKeywordRetriever("unused")
    retriever._pool = postgres_pool
    results = await retriever.retrieve(workspace_id=7, project_id=8, question="谁获得了2029年诺贝尔交通工程奖", top_k=1)
    assert results[0].asset_id == 12
    assert results[0].keyword_score > 0
