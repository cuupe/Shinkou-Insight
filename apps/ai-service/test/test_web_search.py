import httpx
import pytest

from tools.web import BraveWebSearch


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
