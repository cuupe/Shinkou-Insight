"""Query-only relevance and source diversity, shared by every web adapter.

Scores measure lexical support, not truth. In particular, a year, URL, or a
provider's own snippet must never make an unrelated source pass body validation.
"""

from __future__ import annotations

import re
from calendar import monthrange
from collections import Counter
from datetime import date, datetime, timedelta
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models.schemas import Evidence
from core import clock
from core.clock import current_date
from prompts.search_prompts import WEB_SEARCH_STOPWORDS

_EN_STOP = frozenset("""a an the and or of for to in on with is are what which how
please tell me about search find latest recent newest current incumbent now official release
progress development developments related news work technical implementation""".split())
_ZH_STOP = WEB_SEARCH_STOPWORDS | {
    "当前",
    "相关",
    "进展",
    "动态",
    "消息",
    "整理",
    "总结",
    "研究",
    "官方",
    "发布",
    "今天",
    "今日",
    "本周",
    "本月",
    "今年",
    "近期",
    "过去",
    "梳理",
    "报告",
    "内容",
    "全面",
    "详细",
    "情况",
    "现状",
    "概况",
    "一份",
    "一个",
    "给我",
    "现任",
    "在任",
    "现职",
    "现在",
    "是谁",
    "哪位",
}
_COUNTRY_ALIASES = (
    ("美国", "united states", "american", "u.s.", "usa"),
    ("日本", "japan", "japanese"),
)
_ALIASES = (
    ("人工智能", "artificial intelligence", "ai"),
    ("大模型", "large language models", "large language model", "llm", "llms"),
    ("机器学习", "machine learning"),
    *_COUNTRY_ALIASES,
    ("总统", "president"),
    ("首相", "prime minister", "内閣総理大臣", "総理大臣"),
)

_DATE_TOKEN = re.compile(
    r"(?<![a-z0-9._-])20\d{2}(?:[-/年]\d{1,2}(?:[-/月]\d{1,2}日?)?月?|年)?(?![a-z0-9])",
    re.I,
)
_CURRENT_STATUS = re.compile(r"现任|在任|现职|\bincumbent\b", re.I)
_CURRENT_TIME = re.compile(r"现在|目前|当前|今天|今日|\b(?:now|current|today)\b", re.I)
_PUBLIC_ROLE = re.compile(
    r"总统|首相|总理|国家主席|国王|女王|市长|州长|部长|执政|\b(?:president|prime minister|chancellor|mayor|governor|ceo|chairperson)\b",
    re.I,
)


def is_current_status_query(query: str) -> bool:
    """Recognize current office/state questions, including implicit 'who is'."""
    if _DATE_TOKEN.search(query):
        return False  # User-specified historical dates are authoritative.
    if re.search(
        r"小说|虚构|假设|设定|故事|资料中|文档中|\bfiction\b", query, re.I
    ) and not re.search(r"现实|real-world", query, re.I):
        return False
    if _CURRENT_STATUS.search(query):
        return True
    if not _PUBLIC_ROLE.search(query):
        return False
    if _CURRENT_TIME.search(query):
        return True
    if re.search(
        r"历任|前任|任期|就职|上任|当选|历史|\b(?:former|history|when|inaugurat)\b",
        query,
        re.I,
    ):
        return False
    return bool(re.search(r"谁|哪位|叫什么|\bwho\b", query, re.I))


def current_status_subjects(query: str) -> list[str]:
    """Require separate support for each office in a combined current question."""
    roles = list(_PUBLIC_ROLE.finditer(query))
    if len(roles) < 2:
        return [query]
    connectors = list(re.finditer(r"和|以及|、|，|,|;|；|\band\b", query, flags=re.I))
    splits = [
        matches[-1]
        for before, after in zip(roles, roles[1:])
        if (
            matches := [
                match
                for match in connectors
                if before.end() <= match.start() < after.start()
            ]
        )
    ]
    parts: list[str] = []
    start = 0
    for split in splits:
        parts.append(query[start : split.start()])
        start = split.end()
    parts.append(query[start:])
    subjects = [part.strip() for part in parts if _PUBLIC_ROLE.search(part)]
    if len(subjects) < 2:
        return [query]
    return [
        part if is_current_status_query(part) else "current " + part
        for part in subjects
    ]


def temporal_search_query(
    query: str, goal: str = "", *, today: date | None = None
) -> str:
    """Keep tool-generated dates inside the original user's temporal intent."""
    today = today or current_date()
    goal = goal or query
    candidate = focused_query(query)
    user_dates = _DATE_TOKEN.findall(goal)
    if is_current_status_query(goal):
        candidate = _DATE_TOKEN.sub(" ", candidate)
        if not (_CURRENT_TIME.search(candidate) or _CURRENT_STATUS.search(candidate)):
            candidate = (
                "current " if re.search(r"[a-z]", candidate, re.I) else "当前现任 "
            ) + candidate
        elif not _CURRENT_TIME.search(candidate):
            candidate = "当前 " + candidate
        return re.sub(r"\s+", " ", candidate).strip()
    if user_dates:
        # A planner may focus the subject, but cannot change an explicit period.
        candidate = _DATE_TOKEN.sub(" ", candidate)
        candidate += " " + " ".join(dict.fromkeys(user_dates))
    elif freshness_window(goal, today=today):
        candidate = _DATE_TOKEN.sub(" ", candidate)
        if freshness_window(candidate, today=today) is None:
            relative = re.search(
                r"过去\s*\d+\s*天|近\s*\d+\s*天|今天|今日|本周|本月|今年|最新|最近|近期|目前|当前|\b(?:latest|recent|newest|current|today)\b",
                goal,
                re.I,
            )
            candidate += " " + (relative[0] if relative else "最新")
    return re.sub(r"\s+", " ", candidate).strip()


def unsupported_event_dates(answer: str, evidence: list[Evidence]) -> list[str]:
    """Check calendar claims against source BODY dates, not publication metadata."""
    pattern = re.compile(
        r"(?<!\d)(20\d{2})(?:\s*[-/年.]\s*(\d{1,2})(?:\s*[-/月.]\s*(\d{1,2})\s*日?)?\s*月?|\s*年)(?!\d)"
    )

    months = {
        name.casefold(): index
        for index, name in enumerate(
            (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ),
            start=1,
        )
    }
    month_names = "|".join(months)

    def calendar_claims(text: str):
        for match in pattern.finditer(text):
            value = (
                int(match[1]),
                int(match[2]) if match[2] else None,
                int(match[3]) if match[3] else None,
            )
            yield value, match[0], match.start()
        for match in re.finditer(
            rf"\b({month_names})\s+(\d{{1,2}}),?\s+(20\d{{2}})\b", text, re.I
        ):
            yield (int(match[3]), months[match[1].casefold()], int(match[2])), match[
                0
            ], match.start()
        for match in re.finditer(
            rf"\b(\d{{1,2}})\s+({month_names})\s+(20\d{{2}})\b", text, re.I
        ):
            yield (int(match[3]), months[match[2].casefold()], int(match[1])), match[
                0
            ], match.start()
        for match in re.finditer(rf"\b({month_names})\s+(20\d{{2}})\b", text, re.I):
            yield (int(match[2]), months[match[1].casefold()], None), match[
                0
            ], match.start()

    source_dates = [
        value
        for item in evidence
        for value, _raw, _start in calendar_claims(item.content)
    ]
    unsupported: list[str] = []
    today = current_date()
    for value, raw, start in calendar_claims(answer):
        prefix = answer[max(0, start - 24) : start]
        if value == (today.year, today.month, today.day) and re.search(
            r"截至|当前日期|核验日期|\bas of\b", prefix, re.I
        ):
            continue
        if not any(
            all(
                expected is None or expected == actual
                for expected, actual in zip(value, source)
            )
            for source in source_dates
        ):
            unsupported.append(raw.strip())
    return list(dict.fromkeys(unsupported))


def _contains(text: str, term: str) -> bool:
    if re.search(r"[a-z]", term):
        # AI must not match 'rain', nor R1 match R10.
        return (
            re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text)
            is not None
        )
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
                    normalized = re.sub(
                        r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])",
                        " ",
                        normalized,
                    )
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
    countries = [aliases for aliases in _COUNTRY_ALIASES if aliases in units]
    if countries and not any(
        _contains(normalized, term) for aliases in countries for term in aliases
    ):
        return 0.0
    # Distinctive names in mixed-language questions are topic anchors. Matching
    # only "作品" must not answer a question about ZUN with someone else's work.
    latin_units = [
        terms[0] for terms in units if len(terms) == 1 and re.search(r"[a-z]", terms[0])
    ]
    capitalized = {
        word.casefold() for word in re.findall(r"\b[A-Z][A-Za-z0-9._+-]*", query)
    }
    anchors = [
        term
        for term in latin_units
        if (re.search(r"[\u4e00-\u9fff]", query) or term in capitalized)
        and not re.fullmatch(r"v?\d[\w.]*", term)
    ]
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
            grams = {term[i : i + n] for n in (2, 3) for i in range(len(term) - n + 1)}
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
    text = re.sub(
        r"^(?:请帮我|请问|帮我|请|联网|搜索|查一下|搜一下|整理|总结)[：:\s]*",
        "",
        query.strip(),
    )
    text = re.sub(r"^(?:梳理|归纳)(?:一下)?[：:\s]*", "", text)
    text = re.sub(
        r"[，,、；;]\s*(?:整理|总结)(?:一个|一份)?(?:报告|总结)?(?:给我)?", "", text
    )
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
    if (
        window
        and window[0].year == window[1].year
        and (window[1] - window[0]).days > 300
    ):
        period = str(window[1].year)
    if window and window[0] == window[1]:
        period = window[1].isoformat()
    if is_current_status_query(query):
        period = f"current {current_date().year}"
    native = " ".join([*(unit[0] for unit in units), period]).strip()
    translated = " ".join(
        [*(unit[1] if len(unit) > 1 else unit[0] for unit in units), period]
    ).strip()
    return [
        value
        for value in dict.fromkeys([native, translated])
        if value != focused_query(query)
    ][:2]


def freshness_window(
    query: str, *, today: date | None = None
) -> tuple[date, date] | None:
    today = today or current_date()
    if is_current_status_query(query):
        return today - timedelta(days=89), today
    dates = re.findall(
        r"(?<!\d)(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})(?:日)?(?!\d)", query
    )
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
            return min(parsed_months), min(
                today, date(last.year, last.month, monthrange(last.year, last.month)[1])
            )
        except ValueError:
            return today + timedelta(days=1), today
    years = [int(value) for value in re.findall(r"(?<!\d)20\d{2}(?!\d)", query)]
    if years:
        return date(min(years), 1, 1), min(today, date(max(years), 12, 31))
    if not re.search(
        r"最新|最近|近期|目前|当前|现在|今天|今日|本周|本月|今年|过去\s*\d+\s*天|近\s*\d+\s*天|\b(latest|recent|newest|current|today)\b",
        query,
        re.I,
    ):
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
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in {"gclid", "fbclid", "msclkid"}
    ]
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path.rstrip("/") or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def _fingerprint(text: str) -> set[str]:
    compact = re.sub(r"\W+", "", text.casefold())[:6000]
    return {compact[i : i + 8] for i in range(max(0, len(compact) - 7))}


def source_weight(item: Evidence) -> float:
    """Prefer attributable publishers over community digests; never certify truth."""
    parsed = urlsplit(item.url or "")
    host = parsed.hostname or ""
    community = ("juejin.cn", "csdn.net", "segmentfault.com", "zhihu.com")
    weight = (
        0.7
        if any(host == domain or host.endswith("." + domain) for domain in community)
        else 1.0
    )
    if (
        _official_host(host)
        or host.endswith((".edu", ".edu.cn", ".ac.uk"))
        or re.search(r"/(?:newsroom|press-releases|research|papers|docs)/", parsed.path)
    ):
        weight += 0.15
    if re.search(
        r"日报|资讯盘点|热点.*梳理|每天.*分钟|每日.*资讯|\bdaily.*(?:news|digest)\b",
        item.source_name,
        re.I,
    ):
        weight *= 0.6
    return weight


def _official_host(host: str) -> bool:
    return bool(
        re.search(r"\.gov(?:\.[a-z]{2,3})?$|\.go\.jp$|\.gov\.uk$", host.casefold())
    )


def _live_status_source(item: Evidence) -> bool:
    """An undated official current profile needs a fresh read and explicit context.

    Reading an old biography today does not make its claims current.
    """
    parsed = urlsplit(item.url or "")
    if not _official_host(parsed.hostname or "") or not item.retrieved_at:
        return False
    try:
        retrieved = datetime.fromisoformat(item.retrieved_at.replace("Z", "+00:00"))
        now = clock.current_time()
        if retrieved.tzinfo is None or not timedelta(0) <= now - retrieved <= timedelta(
            days=1
        ):
            return False
    except ValueError:
        return False
    if re.search(
        r"archive|history|historical|former|past[-_]?administration", parsed.path, re.I
    ):
        return False
    if re.search(
        r"\.pdf$|/(?:news|articles?|speeches|press-releases?)/", parsed.path, re.I
    ):
        return False
    path_years = [
        int(value) for value in re.findall(r"(?<!\d)20\d{2}(?!\d)", parsed.path)
    ]
    if path_years and max(path_years) < now.year:
        return False
    if re.search(r"前任|历任|\bformer\b", item.source_name, re.I):
        return False
    return bool(
        re.search(r"现任|在任|current|incumbent|現在の|現職", item.content, re.I)
        or re.search(
            r"/(?:current|administration|prime-minister|prime_minister)(?:/|$)",
            parsed.path,
            re.I,
        )
    )


def rank_web_evidence(
    query: str, items: list[Evidence], limit: int, *, require_body: bool = False
) -> list[Evidence]:
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
                published = None
            if published and published > window[1]:
                continue
            if not (is_current_status_query(query) and _live_status_source(item)):
                if published is None or not window[0] <= published <= window[1]:
                    continue
        score = (
            relevance * 0.65 + topic_score(query, item.source_name) * 0.35
        ) * source_weight(item)
        ranked.append((score, item))
    ranked.sort(key=lambda pair: -pair[0])
    selected: list[Evidence] = []
    urls: set[str] = set()
    fingerprints: list[set[str]] = []
    hosts: Counter[str] = Counter()
    while ranked and len(selected) < limit:
        # Soft domain diversity: keep useful same-site pages if alternatives fail.
        best = max(
            range(len(ranked)),
            key=lambda i: ranked[i][0]
            / (1 + 0.35 * hosts[urlsplit(ranked[i][1].url or "").hostname or ""]),
        )
        score, item = ranked.pop(best)
        identity = canonical_url(item.url or "")
        fingerprint = _fingerprint(item.content)
        if identity in urls or (
            len(item.content) >= 80
            and any(
                len(fingerprint & other) / max(len(fingerprint | other), 1) >= 0.85
                for other in fingerprints
            )
        ):
            continue
        urls.add(identity)
        fingerprints.append(fingerprint)
        hosts[urlsplit(item.url or "").hostname or ""] += 1
        selected.append(item.model_copy(update={"rerank_score": round(score, 4)}))
    return selected
