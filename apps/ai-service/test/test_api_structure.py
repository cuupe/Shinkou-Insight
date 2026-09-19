from main import app


def test_public_and_internal_routes_are_registered():
    paths = set(app.openapi()["paths"])

    assert {
        "/health",
        "/internal/health",
        "/internal/llm/chat",
        "/internal/llm/context",
        "/internal/knowledge/search",
        "/internal/tools",
        "/internal/tools/custom/reload",
        "/internal/tools/calls",
        "/internal/tools/calls/{call_id}",
        "/internal/tools/chains",
        "/internal/tools/chains/{chain_id}",
        "/internal/files/tools",
        "/internal/web-source/validate",
        "/internal/research/runs/{run_id}",
        "/internal/research/runs/{run_id}/events",
    } <= paths
