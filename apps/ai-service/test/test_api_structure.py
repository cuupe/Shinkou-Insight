from main import app


def test_public_and_internal_routes_are_registered():
    paths = set(app.openapi()["paths"])

    assert {
        "/health",
        "/internal/health",
        "/internal/llm/chat",
        "/internal/knowledge/search",
        "/internal/research/runs/{run_id}",
        "/internal/research/runs/{run_id}/events",
    } <= paths
