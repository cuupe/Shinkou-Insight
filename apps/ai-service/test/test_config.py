import pytest
from pydantic import ValidationError

from config import Settings


def test_settings_parse_comma_separated_runtime_options():
    settings = Settings(
        MCP_ALLOWED_TOOLS="search_knowledge, search_graph",
        AGENT_WORKER_URLS="planner=http://planner:8000,writer=http://writer:8000",
        LLM_STRUCTURED_OUTPUT_METHOD="function_calling",
        CUSTOM_TOOLS_MODULES="weather, finance.py",
    )

    assert settings.mcp_allowed_tools == ["search_knowledge", "search_graph"]
    assert settings.agent_worker_urls == {
        "planner": "http://planner:8000",
        "writer": "http://writer:8000",
    }
    assert settings.llm_structured_output_method == "function_calling"
    assert settings.custom_tools_modules == ["weather", "finance.py"]


def test_settings_reject_invalid_pool_range_and_output_method():
    with pytest.raises(ValidationError):
        Settings(DB_POOL_MIN_SIZE=5, DB_POOL_MAX_SIZE=2)
    with pytest.raises(ValidationError):
        Settings(LLM_STRUCTURED_OUTPUT_METHOD="unsupported")
