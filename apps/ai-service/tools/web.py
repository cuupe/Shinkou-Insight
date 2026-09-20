from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qs, unquote, urlparse
from typing import Protocol

import httpx
from bs4 import BeautifulSoup

from models.schemas import Evidence
from security.policy import SecurityPolicyError, validate_external_url
from tools.search_quality import rank_web_evidence


class WebSearchProvider(Protocol):
    async def search(self, query: str, top_k: int = 5) -> list[Evidence]: ...


class WebSearchError(RuntimeError):
    """Base error for an external search provider."""


_BLOCKED_SOURCE_MARKERS = (
    "captcha",
    "verify you are human",
    "access denied",
    "请求过于频繁",
    "访问被拒绝",
    "安全验证",
)


DEFAULT_DUCKDUCKGO_BASE_URL = "https://html.duckduckgo.com/html/"
DEFAULT_BING_BASE_URL = "https://www.bing.com/search"
WEB_SEARCH_TIMEOUT_SECONDS = 12.0


def _relevant_candidates(
    query: str, candidates: list[tuple[str, str, str]], top_k: int
) -> list[tuple[str, str, str]]:
    """Drop search-engine noise before it reaches the model or citation panel."""

    rows = [
        Evidence(
            id=str(index),
            chunk_id=str(index),
            source_name=title,
            content=description or title,
            url=url,
            source_type="web",
            content_kind="search_snippet",
        )
        for index, (title, url, description) in enumerate(candidates)
    ]
    return [candidates[int(item.id)] for item in rank_web_evidence(query, rows, top_k)]


def _source_terms(value: object) -> set[str]:
    normalized = _plain_text(value).casefold()
    terms = set(re.findall(r"[a-z0-9][a-z0-9._-]{2,}|[\u4e00-\u9fff]{2,}", normalized))
    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        terms.update(block[index : index + 2] for index in range(len(block) - 1))
    return {term for term in terms if len(term) >= 2}


async def validate_web_source(
    client: httpx.AsyncClient,
    *,
    url: str,
    title: str = "",
    excerpt: str = "",
) -> dict[str, object]:
    """Verify that a citation URL is reachable and contains its claimed evidence."""

    try:
        normalized_url = validate_external_url(url)
    except SecurityPolicyError as exc:
        return {"valid": False, "reason": str(exc), "url": str(url or "")}

    try:
        response = await client.get(
            normalized_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain",
                "User-Agent": "Shinkou-Insight/0.1 (+citation validation)",
            },
            timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except httpx.TimeoutException:
        return {"valid": False, "reason": "来源页面响应超时", "url": normalized_url}
    except httpx.RequestError as exc:
        return {
            "valid": False,
            "reason": f"来源页面无法访问：{exc}",
            "url": normalized_url,
        }

    content_type = response.headers.get("content-type", "").casefold()
    if response.status_code < 200 or response.status_code >= 300:
        return {
            "valid": False,
            "reason": f"来源页面返回 HTTP {response.status_code}",
            "url": normalized_url,
            "statusCode": response.status_code,
        }
    if "application/pdf" in content_type:
        valid = len(response.content) >= 1_000
        return {
            "valid": valid,
            "reason": "" if valid else "来源 PDF 内容为空或不完整",
            "url": str(response.url),
            "statusCode": response.status_code,
            "contentType": content_type,
        }

    soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
    page_text = _plain_text(soup.get_text(" ", strip=True))
    lowered = page_text.casefold()
    if len(page_text) < 80:
        return {
            "valid": False,
            "reason": "来源页面没有可验证的正文内容",
            "url": str(response.url),
            "statusCode": response.status_code,
        }
    if any(marker in lowered for marker in _BLOCKED_SOURCE_MARKERS):
        return {
            "valid": False,
            "reason": "来源页面是验证或拦截页面",
            "url": str(response.url),
            "statusCode": response.status_code,
        }

    page_terms = _source_terms(page_text)
    title_matches = len(_source_terms(title) & page_terms)
    excerpt_matches = len(_source_terms(excerpt) & page_terms)
    valid = title_matches >= 2 or excerpt_matches >= 2
    return {
        "valid": valid,
        "reason": "" if valid else "来源页面内容与引用标题或摘录不匹配",
        "url": str(response.url),
        "statusCode": response.status_code,
        "contentType": content_type,
        "titleMatches": title_matches,
        "excerptMatches": excerpt_matches,
    }


class DisabledWebSearch:
    """Explicitly fail when a request needs an unconfigured web provider."""

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        raise WebSearchError("external web search is not configured")


class BraveWebSearch:
    """Brave Search API adapter that returns URL-backed evidence."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        api_key: str,
        base_url: str,
        search_language: str = "zh-hans",
    ):
        if not api_key:
            raise ValueError(
                "runtime web search API key is required when web search is enabled"
            )
        self.client = client
        self.api_key = api_key
        self.base_url = base_url
        self.search_language = search_language

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        try:
            response = await self.client.get(
                self.base_url,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
                params={
                    "q": query,
                    "count": max(1, min(max(top_k * 3, 10), 20)),
                    "search_lang": self.search_language,
                    "text_decorations": "false",
                },
                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise WebSearchError("web search request timed out") from exc
        except httpx.RequestError as exc:
            raise WebSearchError(f"web search request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise WebSearchError("web search authentication failed")
        if response.status_code == 429:
            raise WebSearchError("web search rate limit exceeded")
        if response.is_error:
            raise WebSearchError(f"web search failed with HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise WebSearchError("web search returned invalid JSON") from exc

        results = (payload.get("web") or {}).get("results") or []
        candidates: list[tuple[str, str, str]] = []
        for item in results:
            title = _plain_text(item.get("title"))
            url = str(item.get("url") or "").strip()
            description = _plain_text(item.get("description"))
            if not title or not url or not description:
                continue
            candidates.append((title, url, description))

        evidence: list[Evidence] = []
        for title, url, description in _relevant_candidates(query, candidates, top_k):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            evidence.append(
                Evidence(
                    id=f"W{digest[:12]}",
                    chunk_id=f"web:{digest[:16]}",
                    content=f"{title}\n{description}",
                    source_name=title,
                    content_kind="search_snippet",
                    score=round(1 / (len(evidence) + 1), 4),
                    url=url,
                    source_type="web",
                )
            )
        return evidence


class BingWebSearch:
    """Public Bing HTML adapter used as a fallback for blocked public providers."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str = DEFAULT_BING_BASE_URL,
        search_language: str = "zh-hans",
    ):
        self.client = client
        self.base_url = base_url
        self.search_language = search_language

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        try:
            response = await self.client.get(
                self.base_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "Shinkou-Insight/0.1 (+local development)",
                },
                params={
                    "q": query,
                    "setlang": self.search_language,
                },
                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise WebSearchError("fallback web search request timed out") from exc
        except httpx.RequestError as exc:
            raise WebSearchError(f"fallback web search request failed: {exc}") from exc

        if response.status_code == 429:
            raise WebSearchError("fallback web search rate limit exceeded")
        if response.is_error:
            raise WebSearchError(
                f"fallback web search failed with HTTP {response.status_code}"
            )

        soup = BeautifulSoup(response.text, "html.parser")
        candidates: list[tuple[str, str, str]] = []
        seen_urls: set[str] = set()
        for item in soup.select("li.b_algo"):
            link = item.select_one("h2 a")
            snippet = item.select_one(".b_caption p")
            title = _plain_text(link.get_text(" ", strip=True) if link else "")
            url = str(link.get("href") or "").strip() if link else ""
            description = _plain_text(
                snippet.get_text(" ", strip=True) if snippet else ""
            )
            if (
                not title
                or not url.startswith(("http://", "https://"))
                or url in seen_urls
            ):
                continue
            seen_urls.add(url)
            candidates.append((title, url, description))
            if len(candidates) >= max(10, min(top_k * 3, 20)):
                break

        evidence: list[Evidence] = []
        for title, url, description in _relevant_candidates(query, candidates, top_k):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            evidence.append(
                Evidence(
                    id=f"W{digest[:12]}",
                    chunk_id=f"web:{digest[:16]}",
                    content=f"{title}\n{description}" if description else title,
                    source_name=title,
                    content_kind="search_snippet",
                    score=round(1 / (len(evidence) + 1), 4),
                    url=url,
                    source_type="web",
                )
            )
        return evidence


class DuckDuckGoWebSearch:
    """Public HTML search adapter used when a project has no provider key."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str = DEFAULT_DUCKDUCKGO_BASE_URL,
        search_language: str = "zh-hans",
    ):
        self.client = client
        self.base_url = base_url
        self.search_language = search_language

    async def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        try:
            response = await self.client.get(
                self.base_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "Shinkou-Insight/0.1 (+local development)",
                },
                params={
                    "q": query,
                    "kl": _duckduckgo_region(self.search_language),
                },
                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            return await self._fallback_to_bing(
                query, top_k, WebSearchError("web search request timed out")
            )
        except httpx.RequestError as exc:
            return await self._fallback_to_bing(
                query, top_k, WebSearchError(f"web search request failed: {exc}")
            )

        if response.status_code == 429:
            return await self._fallback_to_bing(
                query, top_k, WebSearchError("web search rate limit exceeded")
            )
        if response.status_code in {401, 403}:
            return await self._fallback_to_bing(
                query,
                top_k,
                WebSearchError("public web search was blocked by the provider"),
            )
        if response.is_error:
            return await self._fallback_to_bing(
                query,
                top_k,
                WebSearchError(f"web search failed with HTTP {response.status_code}"),
            )

        soup = BeautifulSoup(response.text, "html.parser")
        candidate_limit = max(10, min(top_k * 3, 20))
        candidates: list[tuple[str, str, str]] = []
        seen_urls: set[str] = set()
        for item in soup.select(".result"):
            link = item.select_one("a.result__a")
            snippet = item.select_one(".result__snippet")
            title = _plain_text(link.get_text(" ", strip=True) if link else "")
            url = _duckduckgo_result_url(link.get("href") if link else "")
            description = _plain_text(
                snippet.get_text(" ", strip=True) if snippet else ""
            )
            if not title or not url or not description or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append((title, url, description))
            if len(candidates) >= candidate_limit:
                break
        evidence: list[Evidence] = []
        for title, url, description in _relevant_candidates(query, candidates, top_k):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            evidence.append(
                Evidence(
                    id=f"W{digest[:12]}",
                    chunk_id=f"web:{digest[:16]}",
                    content=f"{title}\n{description}",
                    source_name=title,
                    content_kind="search_snippet",
                    score=round(1 / (len(evidence) + 1), 4),
                    url=url,
                    source_type="web",
                )
            )
        if evidence:
            return evidence
        return await self._fallback_to_bing(
            query,
            top_k,
            WebSearchError("public web search returned no parseable results"),
        )

    async def _fallback_to_bing(
        self, query: str, top_k: int, original_error: WebSearchError
    ) -> list[Evidence]:
        try:
            return await BingWebSearch(
                client=self.client, search_language=self.search_language
            ).search(query, top_k)
        except Exception:
            raise original_error


def _duckduckgo_region(language: str) -> str:
    normalized = str(language or "").lower().replace("_", "-")
    return {"zh-hans": "cn-zh", "zh-cn": "cn-zh", "en-us": "us-en"}.get(
        normalized, normalized or "wt-wt"
    )


def _duckduckgo_result_url(value: object) -> str:
    raw_url = html.unescape(str(value or "")).strip()
    if raw_url.startswith("//"):
        raw_url = f"https:{raw_url}"
    parsed = urlparse(raw_url)
    redirect = parse_qs(parsed.query).get("uddg", [])
    return unquote(redirect[0]).strip() if redirect else raw_url


def _plain_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"<[^>]+>", "", text).strip()
