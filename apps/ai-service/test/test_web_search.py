import httpx
import pytest

from tools.multi_source_search import MultiSourceWebSearch
from tools.web import BingWebSearch, BraveWebSearch, DuckDuckGoWebSearch, validate_web_source


@pytest.mark.asyncio
async def test_brave_search_maps_results_to_citable_evidence():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Subscription-Token"] == "key"
        assert request.url.params["q"] == "PostgreSQL vector search"
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "PostgreSQL Documentation",
                            "url": "https://www.postgresql.org/docs/",
                            "description": "<strong>PostgreSQL</strong> documentation and reference.",
                        }
                    ]
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        results = await BraveWebSearch(client=client, api_key="key", base_url="https://search.test").search("PostgreSQL vector search")

    assert len(results) == 1
    assert results[0].source_type == "web"
    assert results[0].url == "https://www.postgresql.org/docs/"
    assert "<strong>" not in results[0].content


@pytest.mark.asyncio
async def test_brave_search_drops_results_without_query_topic():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "ChatGPT 联网搜索教程",
                            "url": "https://example.com/chatgpt",
                            "description": "通用聊天机器人搜索说明。",
                        },
                        {
                            "title": "ZUN 最新作品与东方 Project 资料",
                            "url": "https://example.com/zun",
                            "description": "ZUN 的作品和东方 Project 相关信息。",
                        },
                    ]
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        results = await BraveWebSearch(client=client, api_key="key", base_url="https://search.test").search(
            "ZUN 最新作品是什么", top_k=5
        )

    assert len(results) == 1
    assert results[0].url == "https://example.com/zun"


@pytest.mark.asyncio
async def test_duckduckgo_search_maps_redirected_html_results():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "Python"
        return httpx.Response(
            200,
            text=(
                '<div class="result">'
                '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org%2F">Python</a>'
                '<a class="result__snippet">The <b>Python</b> programming language.</a>'
                "</div>"
            ),
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        results = await DuckDuckGoWebSearch(client=client).search("Python", top_k=1)

    assert len(results) == 1
    assert results[0].url == "https://python.org/"
    assert results[0].source_type == "web"
    assert "<b>" not in results[0].content


@pytest.mark.asyncio
async def test_duckduckgo_search_falls_back_to_bing_when_no_results_are_parseable():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "duck.test":
            return httpx.Response(200, text="<html><body>challenge</body></html>", request=request)
        assert request.url.host == "www.bing.com"
        return httpx.Response(
            200,
            text=(
                '<li class="b_algo">'
                '<h2><a href="https://graphics.example.org">Graphics progress</a></h2>'
                '<div class="b_caption"><p>Recent graphics research.</p></div>'
                "</li>"
            ),
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        results = await DuckDuckGoWebSearch(client=client, base_url="https://duck.test").search(
            "graphics", top_k=1
        )
        assert results[0].url == "https://graphics.example.org"


@pytest.mark.asyncio
async def test_bing_search_maps_html_results_to_citable_evidence():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                '<li class="b_algo">'
                '<h2><a href="https://graphics.example.org">Graphics <strong>progress</strong></a></h2>'
                '<div class="b_caption"><p>Latest <b>graphics</b> progress.</p></div>'
                "</li>"
            ),
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        results = await BingWebSearch(client=client).search("graphics progress", top_k=1)

    assert len(results) == 1
    assert results[0].url == "https://graphics.example.org"
    assert "<strong>" not in results[0].content
    assert "<b>" not in results[0].content


@pytest.mark.asyncio
async def test_multi_source_search_fuses_general_and_technical_sources():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "api.github.com":
            return httpx.Response(
                200,
                json={"items": [{"full_name": "psycopg/psycopg", "html_url": "https://github.com/psycopg/psycopg", "description": "PostgreSQL driver"}]},
                request=request,
            )
        raise AssertionError(f"unexpected host: {request.url.host}")

    class General:
        async def search(self, query: str, top_k: int = 5):
            return []

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        search = MultiSourceWebSearch(client=client, general=General(), sources=["general", "github"])
        results = await search.search("PostgreSQL technical implementation", top_k=3)

    assert calls == ["api.github.com"]
    assert results[0].url == "https://github.com/psycopg/psycopg"
    assert results[0].fusion_score is not None


@pytest.mark.asyncio
async def test_validate_web_source_requires_reachable_matching_content():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><title>3D Gaussian Splatting</title><main>3D Gaussian Splatting enables real-time scene rendering. This page describes the method, its reconstruction pipeline, and the rendering tradeoffs observed in dynamic graphics scenes. The paper evaluates quality, speed, and view synthesis on several public datasets.</main></html>",
            headers={"content-type": "text/html; charset=utf-8"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await validate_web_source(
            client,
            url="https://graphics.example.org/paper",
            title="3D Gaussian Splatting",
            excerpt="real-time scene rendering",
        )

    assert result["valid"] is True


@pytest.mark.asyncio
async def test_validate_web_source_rejects_challenge_pages_and_mismatched_excerpt():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html><body>Access denied. Please verify you are human.</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await validate_web_source(
            client,
            url="https://graphics.example.org/blocked",
            title="Computer graphics research",
            excerpt="unrelated fabricated evidence",
        )

    assert result["valid"] is False
    assert str(result["reason"])
