import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

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


def _configure_bundled_file_tools() -> None:
    """Make project-local file-analysis tools available to the service.

    Windows development machines often cannot install system-wide binaries.
    Keep the optional OCR/PDF/Office toolchain inside the project and expose
    it to both ``shutil.which`` and subprocesses without changing the user's
    global PATH.
    """

    bundled_root = PROJECT_ROOT / "tools" / "runtime"
    poppler_root = bundled_root / "poppler"
    poppler_bins = [
        version_dir / "Library" / "bin"
        for version_dir in poppler_root.glob("*/")
        if (version_dir / "Library" / "bin").is_dir()
    ]
    tool_dirs = [
        bundled_root / "tesseract",
        *poppler_bins,
        bundled_root / "libreoffice" / "program",
    ]
    existing = [str(path) for path in tool_dirs if path.is_dir()]
    if existing:
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join([*existing, current_path]) if current_path else os.pathsep.join(existing)

    tessdata = bundled_root / "tesseract" / "tessdata"
    if tessdata.is_dir() and not os.environ.get("TESSDATA_PREFIX"):
        os.environ["TESSDATA_PREFIX"] = str(tessdata)


_configure_bundled_file_tools()


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
    redis_host: str = "localhost"
    redis_port: int = Field(default=16379, ge=1, le=65535)
    redis_password: str | None = None
    cache_enabled: bool = True
    cache_backend: str = "auto"
    cache_namespace: str = "shinkou-insight"
    cache_retrieval_ttl_seconds: int = Field(default=300, ge=1, le=86_400)
    cache_web_ttl_seconds: int = Field(default=900, ge=1, le=86_400)
    cache_embedding_ttl_seconds: int = Field(default=86_400, ge=1, le=2_592_000)
    cache_max_entries: int = Field(default=2_000, ge=100, le=100_000)
    task_queue_enabled: bool = True
    task_queue_stream: str = "shinkou:research-tasks"
    task_queue_group: str = "ai-service"
    task_queue_max_retries: int = Field(default=3, ge=0, le=10)
    task_queue_concurrency: int = Field(default=8, ge=1, le=64)
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
    # Knowledge retrieval is an optional enrichment step. It must never hold
    # the whole answer behind the provider/database timeout.
    knowledge_timeout_seconds: float = Field(default=6, gt=0, le=120)
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
    web_search_sources: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["general", "arxiv", "openalex", "crossref", "github", "stackoverflow"]
    )
    mcp_enabled: bool = False
    mcp_url: str | None = None
    mcp_api_key: str | None = None
    mcp_allowed_tools: Annotated[list[str], NoDecode] = Field(default_factory=list)
    mcp_transport: str = "streamable-http"
    mcp_timeout_seconds: float = Field(default=15, gt=0, le=120)
    custom_tools_enabled: bool = True
    custom_tools_dir: str = "custom_tools"
    custom_tools_modules: Annotated[list[str], NoDecode] = Field(default_factory=list)
    custom_tools_strict: bool = False
    file_ocr_enabled: bool = True
    file_ocr_languages: str = "chi_sim+eng"
    file_pdf_dpi: int = Field(default=180, ge=72, le=400)
    file_max_ocr_pages: int = Field(default=100, ge=1, le=500)
    file_max_video_frames: int = Field(default=8, ge=0, le=32)
    file_whisper_model: str = "base"
    file_whisper_device: str = "cpu"
    file_whisper_compute_type: str = "int8"
    file_analysis_timeout_seconds: float = Field(default=180, gt=5, le=900)
    file_analysis_max_chars: int = Field(default=20_000, ge=1_000, le=100_000)
    agent_transport: str = "in-process"
    agent_worker_urls: Annotated[dict[str, str], NoDecode] = Field(default_factory=dict)
    agent_worker_role: str | None = None

    @field_validator("mcp_allowed_tools", mode="before")
    @classmethod
    def parse_allowed_tools(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value or [])

    @field_validator("custom_tools_modules", mode="before")
    @classmethod
    def parse_custom_tools_modules(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value or [])

    @field_validator("web_search_sources", mode="before")
    @classmethod
    def parse_web_search_sources(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip().casefold() for item in value.split(",") if item.strip()]
        return [str(item).strip().casefold() for item in (value or []) if str(item).strip()]

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
        if self.cache_backend.casefold() not in {"auto", "redis", "memory"}:
            raise ValueError("CACHE_BACKEND must be auto, redis, or memory")
        if self.redis_url is None and self.redis_password:
            password = quote(self.redis_password, safe="")
            self.redis_url = f"redis://:{password}@{self.redis_host}:{self.redis_port}/0"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
