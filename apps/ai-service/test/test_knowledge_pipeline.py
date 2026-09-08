import pytest

from documents.chunker import DocumentChunker
from documents.parser import DocumentParser
from embeddings.providers import HashEmbeddingProvider
from graph.store import GraphExtractor, MemoryGraphStore
from rag.indexer import InMemoryKnowledgeStore, KnowledgeIndexer


@pytest.mark.asyncio
async def test_document_parse_chunk_embed_and_graph_pipeline():
    embedding = HashEmbeddingProvider(dimension=64)
    store = InMemoryKnowledgeStore(embedding)
    graph = MemoryGraphStore()
    indexer = KnowledgeIndexer(DocumentParser(), DocumentChunker(chunk_size=40, chunk_overlap=8), embedding, store, graph, GraphExtractor())
    result = await indexer.index_bytes(data="# Architecture\nKafka and PostgreSQL are used by the service.".encode(), file_name="architecture.md", mime_type="text/markdown", workspace_id=7, project_id=8, asset_id=9)
    assert result["chunk_count"] >= 1
    assert result["embedding_dimension"] == 64
    assert result["graph_entities"] >= 2
    items = await store.retrieve(workspace_id=7, project_id=8, question="Kafka PostgreSQL", top_k=3, retrieval_mode="HYBRID")
    assert items and items[0].asset_id == 9
    nodes, edges = await graph.search(workspace_id=7, project_id=8, query="Kafka", limit=5)
    assert nodes and any(node.name == "Kafka" for node in nodes)


@pytest.mark.asyncio
async def test_file_parser_rejects_unsupported_type():
    with pytest.raises(ValueError, match="Unsupported document type"):
        DocumentParser().parse_bytes(b"binary", file_name="archive.zip")
