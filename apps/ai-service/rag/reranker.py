from __future__ import annotations

from typing import Protocol

from models.schemas import RetrievalItem
from rag.hybrid import extract_search_terms, normalize_query


class Reranker(Protocol):
    async def rerank(self, query: str, items: list[RetrievalItem]) -> list[RetrievalItem]: ...


class LexicalReranker:
    """Cheap deterministic reranker; replace with a cross-encoder adapter."""

    async def rerank(self, query: str, items: list[RetrievalItem]) -> list[RetrievalItem]:
        terms = extract_search_terms(query)
        normalized_query = normalize_query(query)
        ranked = []
        for item in items:
            content = normalize_query(item.content)
            overlap = sum(term in content for term in terms)
            lexical = overlap / max(len(terms), 1)
            phrase_bonus = 0.15 if normalized_query and normalized_query in content else 0.0
            base = item.fusion_score if item.fusion_score is not None else item.score or 0.0
            score = min(1.0, lexical * 0.65 + min(1.0, base) * 0.2 + phrase_bonus)
            item.rerank_score = round(score, 6)
            ranked.append(item)
        return sorted(ranked, key=lambda item: item.rerank_score or 0, reverse=True)
