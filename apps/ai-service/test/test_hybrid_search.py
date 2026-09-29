from rag.hybrid import (
    FusedCandidate,
    bm25_scores,
    build_query_variants,
    diversify_candidates,
    extract_search_terms,
    fuse_ranked_candidates,
)
from rag.keyword import asset_name_matches, explicit_file_names


def test_chinese_query_produces_entity_ngrams_and_bounded_variants():
    terms = extract_search_terms("庖丁是什么时代的人，知识库中有记录吗")
    variants = build_query_variants("庖丁是什么时代的人，知识库中有记录吗")

    assert "庖丁" in terms
    assert 1 <= len(variants) <= 3
    assert all(len(item) <= len("庖丁是什么时代的人，知识库中有记录吗") * 2 for item in variants)


def test_english_query_ignores_common_words_and_citation_instructions():
    terms = extract_search_terms(
        "WHO headquarters location official website. Check this project knowledge base first; "
        "if absent, search the official WHO site and cite it. If you cannot find an official "
        "source, say so."
    )

    assert "who" not in terms
    assert "if" not in terms
    assert "and" not in terms
    assert "you" not in terms
    assert "an" not in terms
    assert "cite" not in terms
    assert "source" not in terms
    assert "headquarters" in terms
    assert "location" in terms


def test_explicit_filename_is_extracted_and_matches_only_that_asset():
    names = explicit_file_names("请总结 test.txt 的主要内容")

    assert names == ["test.txt"]
    assert asset_name_matches("test.txt", names)
    assert asset_name_matches("项目资料/test.txt", names)
    assert not asset_name_matches("not-test.txt", names)
    assert not asset_name_matches("斗破苍穹.txt", names)


def test_weighted_rrf_deduplicates_chunks_and_preserves_channel_scores():
    fused = fuse_ranked_candidates(
        {
            "vector": [("same", {"content": "A"}, 0.9), ("vector-only", {"content": "B"}, 0.8)],
            "keyword": [("same", {"content": "A"}, 4.0), ("keyword-only", {"content": "C"}, 3.0)],
        },
        method="WEIGHTED_RRF",
        weights={"vector": 0.6, "keyword": 0.4},
    )

    assert [item.key for item in fused] == ["same", "vector-only", "keyword-only"]
    assert fused[0].channel_ranks == {"vector": 1, "keyword": 1}
    assert fused[0].channel_scores["keyword"] == 4.0


def test_linear_fusion_and_mmr_reduce_repeated_passages():
    fused = fuse_ranked_candidates(
        {
            "vector": [("a", "Kafka PostgreSQL", 0.9), ("b", "Kafka PostgreSQL details", 0.8), ("c", "Milvus indexing", 0.7)],
            "keyword": [("a", "Kafka PostgreSQL", 5.0), ("b", "Kafka PostgreSQL details", 4.0), ("c", "Milvus indexing", 1.0)],
        },
        method="LINEAR",
        weights={"vector": 0.5, "keyword": 0.5},
    )
    selected = diversify_candidates(fused, top_k=2, content_fn=lambda item: item, diversity_lambda=0.5)

    assert len(selected) == 2
    assert selected[0].key == "a"
    assert selected[1].key == "c"
