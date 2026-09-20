"""Shared, deterministic hybrid retrieval primitives.

The module is deliberately independent of a database or a particular vector
engine.  Both the local store and the Milvus adapter use the same term
extraction, rank fusion, duplicate handling and diversity selection, so a
developer can tune retrieval once and get identical semantics in tests and in
production.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from prompts.search_prompts import SEARCH_STOPWORDS

_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]+", re.IGNORECASE)


def normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def extract_search_terms(value: str, max_terms: int = 64) -> list[str]:
    """Extract Latin words and Chinese 2/3-grams from a natural question."""

    normalized = normalize_query(value)
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        term = term.strip()
        if (
            len(term) < 2
            or term in SEARCH_STOPWORDS
            or term in seen
            or len(terms) >= max_terms
        ):
            return
        seen.add(term)
        terms.append(term)

    for token in _TOKEN_PATTERN.findall(normalized):
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if len(token) <= 8:
                add(token)
            for width in (3, 2):
                for index in range(max(0, len(token) - width + 1)):
                    add(token[index : index + width])
        else:
            add(token)
        if len(terms) >= max_terms:
            break
    return terms


def build_query_variants(question: str, *, max_variants: int = 3) -> list[str]:
    """Build cheap query variants without an extra LLM/keyword-generation call."""

    original = re.sub(r"\s+", " ", str(question or "")).strip()
    if not original:
        return []
    terms = extract_search_terms(original, max_terms=24)
    variants = [original]
    max_variant_chars = max(32, min(4_000, len(original) * 2))
    focused = " ".join(terms[:12])[:max_variant_chars]
    if focused and focused.casefold() != original.casefold():
        variants.append(focused)
    # A compact entity phrase helps exact/ILIKE retrieval, while remaining
    # bounded so a long user prompt never becomes a larger SQL pattern set.
    entities = [term for term in terms if len(term) >= 3][:6]
    if len(entities) >= 2:
        phrase = " ".join(entities)[:max_variant_chars]
        if phrase.casefold() not in {item.casefold() for item in variants}:
            variants.append(phrase)
    return variants[: max(1, max_variants)]


def bm25_scores(query: str, documents: Sequence[str]) -> list[float]:
    """Calculate a small BM25 implementation for local/fallback retrieval."""

    query_terms = extract_search_terms(query)
    if not documents or not query_terms:
        return [0.0 for _ in documents]
    tokenized = [
        extract_search_terms(document, max_terms=512) for document in documents
    ]
    document_frequency = {
        term: sum(term in set(tokens) for tokens in tokenized) for term in query_terms
    }
    average_length = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
    scores: list[float] = []
    for tokens in tokenized:
        counts = {term: tokens.count(term) for term in query_terms}
        length = len(tokens)
        score = 0.0
        for term in query_terms:
            frequency = counts[term]
            if not frequency:
                continue
            df = document_frequency[term]
            idf = math.log(1.0 + (len(documents) - df + 0.5) / (df + 0.5))
            denominator = frequency + 0.9 * (
                1.0 - 0.75 + 0.75 * length / max(average_length, 1.0)
            )
            score += idf * (frequency * 1.9) / max(denominator, 1e-9)
        if normalize_query(query) in normalize_query(" ".join(tokens)):
            score += 0.35
        scores.append(score)
    return scores


@dataclass(slots=True)
class FusedCandidate:
    key: str
    item: Any
    score: float
    channel_scores: dict[str, float] = field(default_factory=dict)
    channel_ranks: dict[str, int] = field(default_factory=dict)


def _unique_ranked(
    values: Iterable[tuple[str, Any, float]],
) -> list[tuple[str, Any, float]]:
    best: dict[str, tuple[str, Any, float]] = {}
    for key, item, score in values:
        normalized_key = str(key)
        candidate = (normalized_key, item, float(score))
        previous = best.get(normalized_key)
        if previous is None or candidate[2] > previous[2]:
            best[normalized_key] = candidate
    return sorted(best.values(), key=lambda value: value[2], reverse=True)


def fuse_ranked_candidates(
    channels: Mapping[str, Sequence[tuple[str, Any, float]]],
    *,
    method: str = "WEIGHTED_RRF",
    weights: Mapping[str, float] | None = None,
    rank_constant: int = 60,
    rank_window_size: int = 100,
) -> list[FusedCandidate]:
    """Fuse independent ranked lists using RRF or normalized linear scores."""

    clean_method = str(method or "WEIGHTED_RRF").upper()
    if clean_method not in {"RRF", "WEIGHTED_RRF", "LINEAR"}:
        clean_method = "WEIGHTED_RRF"
    configured = {
        name: max(0.0, float(value)) for name, value in (weights or {}).items()
    }
    if not configured:
        configured = {name: 1.0 for name in channels}
    total_weight = sum(configured.values()) or 1.0
    configured = {name: value / total_weight for name, value in configured.items()}

    ranked_channels = {
        name: _unique_ranked(values)[: max(1, int(rank_window_size))]
        for name, values in channels.items()
        if values
    }
    candidates: dict[str, FusedCandidate] = {}
    normalized_scores: dict[str, dict[str, float]] = {}
    if clean_method == "LINEAR":
        for name, values in ranked_channels.items():
            raw = [value[2] for value in values]
            low, high = min(raw), max(raw)
            span = high - low
            normalized_scores[name] = {
                key: (score - low) / span if span else (1.0 if score > 0 else 0.0)
                for key, _item, score in values
            }

    for name, values in ranked_channels.items():
        weight = (
            1.0 / len(ranked_channels)
            if clean_method == "RRF"
            else configured.get(name, 0.0)
        )
        for rank, (key, item, raw_score) in enumerate(values, start=1):
            candidate = candidates.get(key)
            if candidate is None:
                candidate = FusedCandidate(key=key, item=item, score=0.0)
                candidates[key] = candidate
            candidate.channel_scores[name] = raw_score
            candidate.channel_ranks[name] = rank
            contribution = (
                normalized_scores[name][key]
                if clean_method == "LINEAR"
                else 1.0 / (max(1, int(rank_constant)) + rank)
            )
            candidate.score += weight * contribution

    return sorted(candidates.values(), key=lambda item: (-item.score, item.key))


def diversify_candidates(
    candidates: Sequence[FusedCandidate],
    *,
    top_k: int,
    content_fn: Callable[[Any], str] = lambda item: str(item),
    diversity_lambda: float = 0.9,
) -> list[FusedCandidate]:
    """Apply lightweight MMR to prevent adjacent chunks repeating one passage."""

    limit = max(0, int(top_k))
    if limit == 0:
        return []
    value = min(1.0, max(0.0, float(diversity_lambda)))
    if value >= 0.999 or len(candidates) <= limit:
        return list(candidates[:limit])

    token_sets = {
        candidate.key: set(
            extract_search_terms(content_fn(candidate.item), max_terms=256)
        )
        for candidate in candidates
    }
    remaining = list(candidates)
    selected: list[FusedCandidate] = []
    while remaining and len(selected) < limit:
        if not selected:
            chosen = remaining[0]
        else:

            def mmr(candidate: FusedCandidate) -> float:
                current = token_sets[candidate.key]
                redundancy = max(
                    len(current & token_sets[item.key])
                    / max(len(current | token_sets[item.key]), 1)
                    for item in selected
                )
                return value * candidate.score - (1.0 - value) * redundancy

            chosen = max(remaining, key=lambda item: (mmr(item), item.score, item.key))
        selected.append(chosen)
        remaining.remove(chosen)
    return selected
