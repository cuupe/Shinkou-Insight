import pytest

from rag.retriever import InMemoryRetriever


@pytest.mark.asyncio
async def test_retriever_enforces_workspace_and_project_scope():
    retriever = InMemoryRetriever([
        {"workspace_id": 1, "project_id": 1, "chunk_id": 1, "content": "PostgreSQL in project one", "source_name": "one.md"},
        {"workspace_id": 2, "project_id": 1, "chunk_id": 2, "content": "PostgreSQL in another workspace", "source_name": "two.md"},
        {"workspace_id": 1, "project_id": 2, "chunk_id": 3, "content": "PostgreSQL in another project", "source_name": "three.md"},
    ])
    result = await retriever.retrieve(workspace_id=1, project_id=1, question="PostgreSQL", top_k=10)
    assert [item.chunk_id for item in result] == [1]


@pytest.mark.asyncio
async def test_retriever_ranks_matching_chunks():
    retriever = InMemoryRetriever([
        {"workspace_id": 1, "project_id": 1, "chunk_id": 1, "content": "TPS", "source_name": "weak.md"},
        {"workspace_id": 1, "project_id": 1, "chunk_id": 2, "content": "系统峰值 TPS 为 3500", "source_name": "strong.md"},
    ])
    result = await retriever.retrieve(workspace_id=1, project_id=1, question="峰值 TPS", top_k=2)
    assert result[0].chunk_id == 2
