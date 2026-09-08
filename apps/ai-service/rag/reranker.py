from __future__ import annotations

from typing import Protocol

from models.schemas import RetrievalItem


class Reranker(Protocol):
    async def rerank(self, query: str, items: list[RetrievalItem]) -> list[RetrievalItem]: ...


class LexicalReranker:
    """Cheap deterministic reranker; replace with a cross-encoder adapter."""

    async def rerank(self, query: str, items: list[RetrievalItem]) -> list[RetrievalItem]:
        terms = {term.casefold() for term in query.split() if term.strip()}
        ranked = []
        for item in items:
            overlap = sum(term in item.content.casefold() for term in terms)
            score = min(1.0, (overlap / max(len(terms), 1)) * 0.7 + (item.vector_score or 0) * 0.3)
            item.rerank_score = round(score, 6)
            ranked.append(item)
        return sorted(ranked, key=lambda item: item.rerank_score or 0, reverse=True)
