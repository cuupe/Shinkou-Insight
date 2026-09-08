import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


def _load_project_env() -> None:
    """Load the real project environment file; never fall back to .env.example."""

    if not ENV_PATH.is_file():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


_load_project_env()


class Settings(BaseSettings):
    """Runtime configuration for the AI service."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "ai-service"
    app_env: str = "local"
    internal_api_key: str = "local-dev-key"
    database_url: str | None = None
    retriever_mode: str = "milvus"
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_db_name: str = "default"
    milvus_collection_name: str = "shinkou_knowledge_chunks"
    db_pool_min_size: int = Field(default=2, ge=1, le=50)
    db_pool_max_size: int = Field(default=10, ge=1, le=100)
    redis_url: str | None = None
    storage_mode: str = "local"
    storage_root: str = "./data"
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "shinkou-files"
    graph_mode: str = "memory"
    graph_extraction_mode: str = "heuristic"
    neo4j_uri: str | None = None
    neo4j_username: str = "neo4j"
    neo4j_password: str | None = None
    embedding_mode: str = "hash"
    embedding_model: str = "hash-embedding-v1"
    embedding_dimension: int = Field(default=1536, ge=8, le=3072)
    embedding_base_url: str | None = None
    embedding_api_key: str | None = Field(default=None, validation_alias="AI_SERVICE_EMBEDDING_API_KEY")
    llm_mode: str = "http"
    llm_base_url: str | None = Field(default=None, validation_alias="AI_SERVICE_LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, validation_alias="AI_SERVICE_LLM_API_KEY")
    llm_model: str = Field(default="", validation_alias="AI_SERVICE_LLM_MODEL")
    llm_timeout_seconds: float = Field(default=60, gt=0, le=600)
    request_timeout_seconds: float = Field(default=30, gt=0, le=600)
    max_retries: int = Field(default=2, ge=0, le=5)
    llm_structured_output_method: str = "json_schema"
    max_research_rounds: int = Field(default=3, ge=1, le=8)
    max_evidence: int = Field(default=12, ge=1, le=50)
    enable_web_search: bool = False
    web_search_provider: str = "brave"
    web_search_api_key: str | None = Field(default=None, validation_alias="AI_SERVICE_WEB_SEARCH_API_KEY")
    web_search_base_url: str = "https://api.search.brave.com/res/v1/web/search"
    web_search_language: str = "zh-hans"
    mcp_enabled: bool = False
    mcp_url: str | None = None
    mcp_api_key: str | None = None
    mcp_allowed_tools: Annotated[list[str], NoDecode] = Field(default_factory=list)
    mcp_transport: str = "streamable-http"
    mcp_timeout_seconds: float = Field(default=15, gt=0, le=120)
    agent_transport: str = "in-process"
    agent_worker_urls: Annotated[dict[str, str], NoDecode] = Field(default_factory=dict)
    agent_worker_role: str | None = None

    @field_validator("mcp_allowed_tools", mode="before")
    @classmethod
    def parse_allowed_tools(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value or [])

    @field_validator("agent_worker_urls", mode="before")
    @classmethod
    def parse_worker_urls(cls, value: object) -> dict[str, str]:
        if isinstance(value, dict):
            return {str(name): str(url) for name, url in value.items()}
        if not isinstance(value, str):
            return {}
        result: dict[str, str] = {}
        for item in value.split(","):
            name, separator, url = item.partition("=")
            if separator and name.strip() and url.strip():
                result[name.strip()] = url.strip()
        return result

    @model_validator(mode="after")
    def validate_runtime_options(self) -> "Settings":
        if self.db_pool_min_size > self.db_pool_max_size:
            raise ValueError("DB_POOL_MIN_SIZE cannot be greater than DB_POOL_MAX_SIZE")
        if self.llm_structured_output_method not in {"json_schema", "function_calling", "json_mode"}:
            raise ValueError("LLM_STRUCTURED_OUTPUT_METHOD must be json_schema, function_calling, or json_mode")
        if self.mcp_api_key is None:
            self.mcp_api_key = self.internal_api_key
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
