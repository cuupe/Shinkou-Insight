"""Query-only relevance and source diversity, shared by every web adapter.

Scores measure lexical support, not truth. In particular, a year, URL, or a
provider's own snippet must never make an unrelated source pass body validation.
"""
from __future__ import annotations

import re
from calendar import monthrange
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models.schemas import Evidence
from prompts.search_prompts import WEB_SEARCH_STOPWORDS

_EN_STOP = frozenset("""a an the and or of for to in on with is are what which how
please tell me about search find latest recent newest current official release
progress development developments related news work technical implementation""".split())
_ZH_STOP = WEB_SEARCH_STOPWORDS | {
    "当前", "相关", "进展", "动态", "消息", "整理", "总结", "研究", "官方", "发布",
    "今天", "今日", "本周", "本月", "今年", "近期", "过去",
    "梳理", "报告", "内容", "全面", "详细", "情况", "现状", "概况", "一份", "一个", "给我",
}
_ALIASES = (
    ("人工智能", "artificial intelligence", "ai"),
    ("大模型", "large language models", "large language model", "llm", "llms"),
    ("机器学习", "machine learning"),
)


def _contains(text: str, term: str) -> bool:
    if re.search(r"[a-z]", term):
        # AI must not match 'rain', nor R1 match R10.
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None
    return term in text


@lru_cache(maxsize=512)
def _topic_units(query: str) -> tuple[tuple[str, ...], ...]:
    normalized = query.casefold()
    normalized = re.sub(r"https?://\S+|\bsite:\S+", " ", normalized)
    units: list[tuple[str, ...]] = []
    for aliases in _ALIASES:
        if any(_contains(normalized, alias) for alias in aliases):
            units.append(aliases)
            for alias in aliases:
                if re.search(r"[a-z]", alias):
                    normalized = re.sub(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", " ", normalized)
                else:
                    normalized = normalized.replace(alias, " ")
    for word in sorted(_ZH_STOP, key=len, reverse=True):
        normalized = normalized.replace(word, " ")
    for word in re.findall(r"[a-z0-9][a-z0-9._+-]*|[\u4e00-\u9fff]{2,}", normalized):
        if word not in _EN_STOP and not re.fullmatch(r"[\d._+-]+", word):
            unit = (word.rstrip("."),)
            if unit not in units:
                units.append(unit)
    return tuple(units)


def topic_score(query: str, text: str) -> float:
    """Coverage across query concepts; partial Chinese overlap is not one vote."""
    units = _topic_units(query)
    if not units:
        return 0.0
    normalized = text.casefold()
    # Distinctive names in mixed-language questions are topic anchors. Matching
    # only "作品" must not answer a question about ZUN with someone else's work.
    latin_units = [terms[0] for terms in units if len(terms) == 1 and re.search(r"[a-z]", terms[0])]
    capitalized = {word.casefold() for word in re.findall(r"\b[A-Z][A-Za-z0-9._+-]*", query)}
    anchors = [term for term in latin_units if (re.search(r"[\u4e00-\u9fff]", query) or term in capitalized) and not re.fullmatch(r"v?\d[\w.]*", term)]
    if anchors and not any(_contains(normalized, term) for term in anchors):
        return 0.0
    versions = [term for term in latin_units if re.fullmatch(r"v\d+(?:\.\d+)*", term)]
    if any(not _contains(normalized, version) for version in versions):
        return 0.0
    scores: list[float] = []
    for aliases in units:
        if any(_contains(normalized, term) for term in aliases):
            scores.append(1.0)
        elif len(aliases) == 1 and re.fullmatch(r"[\u4e00-\u9fff]{3,}", aliases[0]):
            term = aliases[0]
            grams = {term[i:i + n] for n in (2, 3) for i in range(len(term) - n + 1)}
            scores.append(sum(gram in normalized for gram in grams) / len(grams))
        else:
            scores.append(0.0)
    coverage = sum(scores) / len(scores)
    return coverage if max(scores) >= 0.6 and coverage >= 0.5 else 0.0


def filter_relevant_evidence(
    query: str, items: list[Evidence | dict[str, object]]
) -> list[Evidence]:
    """Drop retrieved rows whose source content does not answer the query."""

    relevant: list[Evidence] = []
    for raw in items:
        try:
            item = Evidence.model_validate(raw)
        except Exception:
            continue
        searchable = "\n".join(
            value
            for value in (item.source_name, item.section_title or "", item.content)
            if value
        )
        if topic_score(query, searchable) > 0:
            relevant.append(item)
    return relevant


def focused_query(query: str) -> str:
    """Keep subject/time constraints without injecting unrelated years or keywords."""
    text = re.sub(r"^(?:请帮我|请问|帮我|请|联网|搜索|查一下|搜一下|整理|总结)[：:\s]*", "", query.strip())
    text = re.sub(r"^(?:梳理|归纳)(?:一下)?[：:\s]*", "", text)
    text = re.sub(r"[，,、；;]\s*(?:整理|总结)(?:一个|一份)?(?:报告|总结)?(?:给我)?", "", text)
    text = re.sub(r"[，,、；;]\s*(?:内容)?要(?:全面|详细|完整).*?$", "", text)
    text = re.sub(r"(?:是什么|有哪些|有吗|吗|呢)[？?。\s]*$", "", text)
    return re.sub(r"\s+", " ", text).strip() or query.strip()


def fallback_queries(query: str) -> list[str]:
    """At most two topic/date rewrites; never broaden the evidence acceptance query."""
    units = _topic_units(query)
    if not units:
        return []
    window = freshness_window(query)
    period = window[1].strftime("%Y-%m") if window else ""
    if window and window[0].year == window[1].year and (window[1] - window[0]).days > 300:
        period = str(window[1].year)
    if window and window[0] == window[1]:
        period = window[1].isoformat()
    native = " ".join([*(unit[0] for unit in units), period]).strip()
    translated = " ".join([*(unit[1] if len(unit) > 1 else unit[0] for unit in units), period]).strip()
    return [value for value in dict.fromkeys([native, translated]) if value != focused_query(query)][:2]


def freshness_window(query: str, *, today: date | None = None) -> tuple[date, date] | None:
    today = today or date.today()
    dates = re.findall(r"(?<!\d)(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})(?:日)?(?!\d)", query)
    if dates:
        try:
            parsed = [date(*map(int, parts)) for parts in dates]
            return min(parsed), min(today, max(parsed))
        except ValueError:
            return today + timedelta(days=1), today  # Invalid dates match no evidence.
    months = re.findall(r"(?<!\d)(20\d{2})[-/年](\d{1,2})(?:月)?(?!\d)", query)
    if months:
        try:
            parsed_months = [date(int(year), int(month), 1) for year, month in months]
            last = max(parsed_months)
            return min(parsed_months), min(today, date(last.year, last.month, monthrange(last.year, last.month)[1]))
        except ValueError:
            return today + timedelta(days=1), today
    years = [int(value) for value in re.findall(r"(?<!\d)20\d{2}(?!\d)", query)]
    if years:
        return date(min(years), 1, 1), min(today, date(max(years), 12, 31))
    if not re.search(r"最新|最近|近期|目前|当前|今天|今日|本周|本月|今年|过去\s*\d+\s*天|近\s*\d+\s*天|\b(latest|recent|newest|current|today)\b", query, re.I):
        return None
    days_match = re.search(r"(?:过去|近)\s*(\d+)\s*天", query)
    days = min(max(int(days_match[1]), 1), 3660) if days_match else 90
    if re.search(r"今天|今日|\btoday\b", query, re.I):
        days = 1
    elif "本周" in query:
        days = today.weekday() + 1
    elif "本月" in query:
        days = today.day
    elif "今年" in query:
        return date(today.year, 1, 1), today
    return today - timedelta(days=days - 1), today


def canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.casefold().startswith("utm_") and key.casefold() not in {"gclid", "fbclid", "msclkid"}]
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path.rstrip("/") or "/", urlencode(sorted(query)), ""))


def _fingerprint(text: str) -> set[str]:
    compact = re.sub(r"\W+", "", text.casefold())[:6000]
    return {compact[i:i + 8] for i in range(max(0, len(compact) - 7))}


def source_weight(item: Evidence) -> float:
    """Prefer attributable publishers over community digests; never certify truth."""
    parsed = urlsplit(item.url or "")
    host = parsed.hostname or ""
    community = ("juejin.cn", "csdn.net", "segmentfault.com", "zhihu.com")
    weight = 0.7 if any(host == domain or host.endswith("." + domain) for domain in community) else 1.0
    if host.endswith((".gov", ".gov.cn", ".edu", ".edu.cn", ".ac.uk")) or re.search(r"/(?:newsroom|press-releases|research|papers|docs)/", parsed.path):
        weight += 0.15
    if re.search(r"日报|资讯盘点|热点.*梳理|每天.*分钟|每日.*资讯|\bdaily.*(?:news|digest)\b", item.source_name, re.I):
        weight *= 0.6
    return weight


def rank_web_evidence(query: str, items: list[Evidence], limit: int, *, require_body: bool = False) -> list[Evidence]:
    ranked: list[tuple[float, Evidence]] = []
    window = freshness_window(query) if require_body else None
    for item in items:
        if not item.url or (require_body and item.content_kind != "fulltext"):
            continue
        try:
            parsed = urlsplit(item.url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
        except ValueError:
            continue
        body_score = topic_score(query, item.content)
        if require_body and not body_score:
            continue
        relevance = topic_score(query, f"{item.source_name}\n{item.content}")
        if not relevance:
            continue
        if window:
            # Missing or stale dates cannot substantiate a claim about "latest".
            try:
                published = date.fromisoformat((item.published_at or "")[:10])
            except ValueError:
                continue
            if not window[0] <= published <= window[1]:
                continue
        score = (relevance * 0.65 + topic_score(query, item.source_name) * 0.35) * source_weight(item)
        ranked.append((score, item))
    ranked.sort(key=lambda pair: -pair[0])
    selected: list[Evidence] = []
    urls: set[str] = set()
    fingerprints: list[set[str]] = []
    hosts: Counter[str] = Counter()
    while ranked and len(selected) < limit:
        # Soft domain diversity: keep useful same-site pages if alternatives fail.
        best = max(range(len(ranked)), key=lambda i: ranked[i][0] / (1 + 0.35 * hosts[urlsplit(ranked[i][1].url or "").hostname or ""]))
        score, item = ranked.pop(best)
        identity = canonical_url(item.url or "")
        fingerprint = _fingerprint(item.content)
        if identity in urls or (len(item.content) >= 80 and any(len(fingerprint & other) / max(len(fingerprint | other), 1) >= 0.85 for other in fingerprints)):
            continue
        urls.add(identity)
        fingerprints.append(fingerprint)
        hosts[urlsplit(item.url or "").hostname or ""] += 1
        selected.append(item.model_copy(update={"rerank_score": round(score, 4)}))
    return selected
