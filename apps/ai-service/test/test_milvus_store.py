from rag.milvus_store import MilvusKnowledgeStore, _keyword_terms


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


def test_milvus_search_accepts_schema_primary_field_as_chunk_id():
    class PrimaryKeyClient(FakeMilvusClient):
        def search(self, **kwargs):
            self.calls.append(kwargs)
            return [[{"chunk_id": 23, "distance": 0.87, "entity": {}}]]

    hits = MilvusKnowledgeStore._search_vectors(
        PrimaryKeyClient(), "chunks", [0.1, 0.2], "workspace_id == 7", 20
    )

    assert hits == [{"id": 23, "score": 0.87}]


def test_keyword_terms_keep_chinese_entity_inside_natural_question():
    terms = _keyword_terms("乎古哀是什么时代的人，知识库中有")

    assert "乎古哀" in terms
    assert "古哀" in terms
