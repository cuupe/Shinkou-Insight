from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.dependencies import verify_internal_api_key
from api.routes.knowledge import router
from core.cache import CacheService
from documents.chunker import DocumentChunker
from documents.parser import DocumentParser
from embeddings.providers import HashEmbeddingProvider
from rag.cached import CachedRetriever
from rag.indexer import InMemoryKnowledgeStore, KnowledgeIndexer
from storage.files import MinioFileStorage


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["KEYWORD", "VECTOR", "HYBRID"])
async def test_index_then_search_serializes_cold_and_cached_evidence(mode):
    cache = await CacheService.create(enabled=True, backend="memory", namespace="knowledge-api", max_entries=50)
    embedding = HashEmbeddingProvider(dimension=64)
    store = InMemoryKnowledgeStore(embedding)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[verify_internal_api_key] = lambda: None
    app.state.container = SimpleNamespace(embedding_factory=lambda _config: embedding)
    app.state.indexer = KnowledgeIndexer(DocumentParser(), DocumentChunker(), embedding, store, cache=cache)
    app.state.runtime = SimpleNamespace(retriever=CachedRetriever(store, cache, ttl_seconds=30))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/internal/indexing/assets/9", json={
            "assetId": 9, "workspaceId": 7, "projectId": 8,
            "fileName": "notes.txt", "content": "知识库回归检索，资料应保留证据来源。" * 70,
            "chunking": {"chunkSize": 400, "chunkOverlap": 40, "strategy": "fixed"},
        })
        assert response.status_code == 200, response.text
        assert response.json()["chunkCount"] > 1
        query = {"workspaceId": 7, "projectId": 8, "query": "知识库回归检索", "retrievalMode": mode, "useReranker": True}
        for _ in range(2):
            response = await client.post("/internal/knowledge/search", json=query)
            assert response.status_code == 200, response.text
            items = response.json()["items"]
            assert items and items[0]["assetId"] == 9
            assert items[0]["content"] and items[0]["sourceName"] == "notes.txt"
            assert items[0]["rerankScore"] is not None
        assert (await cache.stats())["hits"] >= 1
        response = await client.post("/internal/knowledge/search", json={**query, "projectId": 99})
        assert response.status_code == 200 and response.json()["items"] == []
        # Empty text must not be reported as successful indexing or wipe the old snapshot.
        response = await client.post("/internal/indexing/assets/9", json={
            "assetId": 9, "workspaceId": 7, "projectId": 8, "fileName": "notes.txt", "content": "   ",
        })
        assert response.status_code == 422
        assert store.items
    await cache.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [False, True])
async def test_storage_errors_are_actionable_instead_of_generic_500(missing):
    from minio.error import S3Error
    from urllib3.exceptions import MaxRetryError

    class UnavailableClient:
        def get_object(self, *_args):
            if missing:
                raise S3Error(response=None, code="NoSuchKey", message="not found", resource="fixture.txt", request_id="test", host_id="test")
            raise MaxRetryError(None, "/fixture", "connection refused")

    storage = object.__new__(MinioFileStorage)
    storage.bucket = "test"
    storage.client = UnavailableClient()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[verify_internal_api_key] = lambda: None
    app.state.storage = storage
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/internal/indexing/assets/9", json={
            "assetId": 9, "workspaceId": 7, "projectId": 8, "fileName": "fixture.txt", "storageKey": "fixture.txt",
        })
        assert response.status_code == (404 if missing else 503)
        assert ("重新上传" if missing else "重新索引") in response.json()["detail"]
