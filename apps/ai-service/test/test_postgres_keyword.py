"""Opt-in SQL regression tests; only connection-local temporary tables are written.

Set TEST_POSTGRES_URL to a disposable/test PostgreSQL connection string.
"""

import os
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from rag.keyword import fetch_keyword_rows
from rag.retriever import PostgresKeywordRetriever
from rag.milvus_store import MilvusKnowledgeStore
from embeddings.providers import HashEmbeddingProvider


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


@pytest.mark.asyncio
async def test_short_document_context_enforces_project_workspace_and_index_scope(postgres_pool):
    store = object.__new__(MilvusKnowledgeStore)
    rows = await store._fetch_short_document_rows(postgres_pool, 7, 8, [12,14,15,16,17])
    assert {row[1] for row in rows} == {12,17}
    assert await store._fetch_short_document_rows(postgres_pool, 99, 8, [12]) == []


@pytest.mark.asyncio
async def test_short_document_context_does_not_expand_a_large_document(postgres_pool):
    async with postgres_pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("UPDATE asset_chunks SET content=%s WHERE asset_id=%s", ["长"*4001,12])
    store = object.__new__(MilvusKnowledgeStore)
    assert await store._fetch_short_document_rows(postgres_pool, 7, 8, [12]) == []


@pytest.mark.asyncio
async def test_actual_multi_need_queries_recall_cost_dates_measurements_and_rollout_conditions(postgres_pool):
    data=json.loads((Path(__file__).parent/'fixtures/research_stop_run12.json').read_text(encoding='utf-8'))
    evidence=[*data['evidence'],data['additional']]
    async with postgres_pool.connection() as connection:
        async with connection.cursor() as cursor:
            for asset in {item['asset_id']:item['source_name'] for item in evidence}.items():
                await cursor.execute("INSERT INTO knowledge_assets VALUES (%s,%s,%s,%s)",
                                     [100000+asset[0],8,asset[1],'SUCCESS'])
            for index,item in enumerate(evidence):
                await cursor.execute("INSERT INTO asset_chunks(id,asset_id,chunk_index,content,section_title) VALUES (%s,%s,%s,%s,%s)",
                                     [1000000+index,100000+item['asset_id'],index,item['content'],item.get('section_title')])
    store=MilvusKnowledgeStore('unused','unused',HashEmbeddingProvider(dimension=8))
    store.pool,store.client=postgres_pool,object()
    results=[]
    for query in [
        '星桥六周试点 样本数 准确率 资料可定位覆盖率 平均检索耗时 严重错误率 周活跃率 含税成本 XQ-05 推广前置条件 2026-08-31 2026-10-11',
        '星桥试点 六周含税成本 总成本 XQ-05 推广前置条件 权限撤销 运行责任 新增样本复测',
    ]:
        results.extend(await store.retrieve(workspace_id=7,project_id=8,question=query,top_k=8))
    text='\n'.join(item.content for item in results)
    assert all(term in text for term in ['139000','权限撤销','50 条','2026-08-31','120 秒','66 秒'])
