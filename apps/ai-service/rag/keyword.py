"""Tenant-scoped keyword recall shared by PostgreSQL-backed retrievers."""

from __future__ import annotations

import re
from typing import Any

from rag.hybrid import build_query_variants, extract_search_terms

_FILE_REFERENCE = re.compile(
    r"(?<![\w])[\w][\w.-]{0,191}\.(?:txt|md|pdf|docx?|xlsx?|pptx?|csv|json|html?|rtf|log)(?![A-Za-z0-9_.-])",
    re.I,
)


def explicit_file_names(question: str) -> list[str]:
    """Return file-name references written explicitly in a question."""

    names: list[str] = []
    seen: set[str] = set()
    for match in _FILE_REFERENCE.finditer(str(question or "")):
        name = match.group(0).replace("\\", "/").rsplit("/", 1)[-1].casefold()
        if name not in seen:
            names.append(name)
            seen.add(name)
    return names


def asset_name_matches(asset_name: str, file_names: list[str]) -> bool:
    """Match a referenced file exactly, or by a space-delimited basename suffix."""

    normalized = str(asset_name or "").replace("\\", "/").rsplit("/", 1)[-1].casefold()
    for file_name in file_names:
        if normalized == file_name:
            return True
        if normalized.endswith(file_name) and len(normalized) > len(file_name):
            boundary = normalized[-len(file_name) - 1]
            if boundary in " \t/\\\"'“”‘’《》「」【】([{":
                return True
    return False


async def fetch_keyword_rows(
    pool: Any,
    workspace_id: int,
    project_id: int,
    question: str,
    asset_ids: list[int],
    limit: int,
    query_variants: list[str] | None = None,
) -> list[tuple]:
    variants = query_variants or build_query_variants(question)
    terms = list(dict.fromkeys(
        term for variant in [question, *variants]
        for term in extract_search_terms(variant)
    ))[:128]
    file_names = explicit_file_names(question)
    if not terms and not file_names:
        return []

    # Normalize each scoped chunk once. Repeated locale-aware ILIKE scans over
    # Chinese n-grams were slower than the entire knowledge-tool deadline.
    # STRPOS also treats %, _ and backslashes literally, without LIKE escaping.
    scope = """
        FROM asset_chunks c
        JOIN knowledge_assets a ON a.id = c.asset_id
        JOIN projects p ON p.id = a.project_id
        WHERE p.workspace_id = %s AND p.id = %s
          AND a.index_status IN ('SUCCESS','INDEXED')
    """
    params: list[Any] = [workspace_id, project_id]
    if asset_ids:
        scope += " AND c.asset_id = ANY(%s)"
        params.append(asset_ids)
    sql = """
        WITH scoped AS MATERIALIZED (
            SELECT c.id,c.asset_id,a.name,c.page_number,c.section_title,c.content,
                   c.chunk_index,c.search_vector,lower(c.content) AS normalized_content
    """ + scope + """
        ), scored AS MATERIALIZED (
            SELECT c.*,
                   GREATEST(
                ts_rank_cd(c.search_vector, plainto_tsquery('simple', %s)),
                (SELECT COALESCE(SUM(char_length(term)), 0)::float
                 FROM unnest(%s::text[]) AS term
                 WHERE strpos(c.normalized_content, term) > 0) / %s
            ) + CASE WHEN EXISTS (
                SELECT 1 FROM unnest(%s::text[]) AS file_name
                WHERE lower(c.name) = file_name
                   OR (right(lower(c.name), char_length(file_name) + 1) = ' ' || file_name)
                   OR (right(lower(c.name), char_length(file_name) + 1) = '/' || file_name)
            ) THEN 2.0 ELSE 0.0 END AS score
            FROM scoped c
        )
        SELECT id,asset_id,name,page_number,section_title,content,score
        FROM scored WHERE score > 0
        ORDER BY score DESC, chunk_index, id LIMIT %s
    """
    # Longer entity n-grams contribute more than incidental two-character
    # matches. Rank BEFORE LIMIT so a relevant older chunk cannot be crowded
    # out by documents that merely share one common term.
    params.extend([question, terms, max(1, sum(map(len, terms))), file_names, limit])
    async with pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(sql, params)
            rows = await cursor.fetchall()
    if file_names:
        return [row for row in rows if asset_name_matches(row[2], file_names)]
    return rows
