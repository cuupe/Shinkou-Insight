from rag.milvus_store import MilvusKnowledgeStore


class FakeMilvusClient:
    def __init__(self):
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return [[{"id": 17, "distance": 0.91, "entity": {}}]]


def test_milvus_filter_is_tenant_scoped():
    expression = MilvusKnowledgeStore._milvus_filter(7, 8, [11, 12])

    assert expression == "workspace_id == 7 and project_id == 8 and asset_id in [11, 12]"


def test_milvus_search_uses_cosine_and_returns_primary_key():
    client = FakeMilvusClient()

    hits = MilvusKnowledgeStore._search_vectors(client, "chunks", [0.1, 0.2], "workspace_id == 7", 20)

    assert hits == [{"id": 17, "score": 0.91}]
    assert client.calls[0]["collection_name"] == "chunks"
    assert client.calls[0]["search_params"]["metric_type"] == "COSINE"
