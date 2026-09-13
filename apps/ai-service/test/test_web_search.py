import httpx
import pytest

from tools.web import BraveWebSearch, DuckDuckGoWebSearch


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
