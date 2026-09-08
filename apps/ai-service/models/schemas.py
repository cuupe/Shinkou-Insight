from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="ignore")


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: str
    mode: str


class ChatMessage(ApiModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


class ModelGenerationConfig(ApiModel):
    """Provider-neutral generation controls, separate from retrieval top_k."""

    temperature: float = Field(default=0.3, ge=0, le=2)
    top_p: float = Field(default=0.9, gt=0, le=1)
    top_k: int | None = Field(default=None, ge=1, le=1_000)
    max_tokens: int = Field(default=4_096, ge=1, le=1_000_000)
    context_window: int = Field(default=128_000, ge=1, le=2_000_000)
    frequency_penalty: float = Field(default=0, ge=-2, le=2)
    presence_penalty: float = Field(default=0, ge=-2, le=2)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    stop: list[str] = Field(default_factory=list, max_length=4)
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None
    extra_body: dict[str, Any] = Field(default_factory=dict)


class RuntimeModelConfig(ApiModel):
    """短生命周期的后端运行时模型配置，不进入用户可见的运行记录。"""

    base_url: str = Field(min_length=1, max_length=1_000)
    api_key: str = Field(min_length=1, max_length=10_000)
    model: str = Field(min_length=1, max_length=300)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    retries: int = Field(default=2, ge=0, le=5)
    generation: ModelGenerationConfig = Field(default_factory=ModelGenerationConfig)
    structured_output_method: Literal["json_schema", "function_calling", "json_mode"] = "json_schema"


class RuntimeWebSearchConfig(ApiModel):
    """按项目/团队解析的联网搜索配置。"""

    provider: str = "brave"
    api_key: str = Field(min_length=1, max_length=10_000)
    base_url: str = Field(min_length=1, max_length=1_000)
    language: str = "zh-hans"


class RuntimeEmbeddingConfig(ApiModel):
    """按项目/团队解析的向量化配置。"""

    mode: str = "openai"
    base_url: str = Field(min_length=1, max_length=1_000)
    api_key: str = Field(min_length=1, max_length=10_000)
    model: str = Field(min_length=1, max_length=300)
    dimension: int = Field(default=1536, ge=1, le=32_768)


class LlmChatRequest(ApiModel):
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0, le=2)


class TokenUsage(ApiModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ModelChatResult(ApiModel):
    content: str
    model: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: int = 0
    request_id: str | None = None


class LlmChatResponse(ModelChatResult):
    pass


class Evidence(ApiModel):
    id: str
    chunk_id: int | str
    content: str = Field(min_length=1)
    source_name: str
    page_number: int | None = None
    section_title: str | None = None
    score: float | None = None
    url: str | None = None
    source_type: Literal["internal", "web"] = "internal"
    asset_id: int | str | None = None
    asset_name: str | None = None
    vector_score: float | None = None
    keyword_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None


class Finding(ApiModel):
    id: str
    kind: Literal["fact", "risk", "conflict", "gap", "recommendation"]
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class PlanItem(ApiModel):
    id: str
    question: str
    source: Literal["INTERNAL", "WEB", "BOTH"]
    rationale: str = ""


class EvidenceEvaluation(ApiModel):
    sufficient: bool = False
    next_action: Literal["ENOUGH", "MORE_INTERNAL", "NEED_WEB"] = "MORE_INTERNAL"
    missing: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class ReportDraft(ApiModel):
    title: str
    executive_summary: str
    sections: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ReviewResult(ApiModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    missing_citations: list[str] = Field(default_factory=list)
    rewrite_instructions: list[str] = Field(default_factory=list)


class ResearchConfig(ApiModel):
    allow_web_search: bool = False
    max_research_rounds: int = Field(default=3, ge=1, le=8)
    report_template: str = "TECH_SELECTION"
    output_language: str = "zh-CN"
    top_k: int = Field(default=8, ge=1, le=20)
    retrieval_mode: Literal["VECTOR", "KEYWORD", "HYBRID"] = "HYBRID"
    use_reranker: bool = False
    system_prompts: dict[str, str] = Field(default_factory=dict)
    tool_max_calls: int = Field(default=10, ge=1, le=50)
    require_tool_approval: bool = True


class ExecuteRunRequest(ApiModel):
    run_id: int | str
    workspace_id: int
    project_id: int
    user_id: int = 0
    goal: str = Field(min_length=1, max_length=20_000)
    config: ResearchConfig = Field(default_factory=ResearchConfig)
    callback: dict[str, Any] | None = None
    runtime_model: RuntimeModelConfig | None = None
    runtime_web_search: RuntimeWebSearchConfig | None = None
    runtime_embedding: RuntimeEmbeddingConfig | None = None
    agent_message_id: str | None = None


class KnowledgeSearchRequest(ApiModel):
    workspace_id: int
    project_id: int
    query: str = Field(min_length=1, max_length=20_000)
    top_k: int = Field(default=8, ge=1, le=20)
    retrieval_mode: Literal["VECTOR", "KEYWORD", "HYBRID"] = "HYBRID"
    use_reranker: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)
    runtime_embedding: RuntimeEmbeddingConfig | None = None


class KnowledgeSearchResponse(ApiModel):
    query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    items: list[Evidence]


class RetrievalItem(Evidence):
    pass


class RetrievalResponse(ApiModel):
    query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    items: list[RetrievalItem]


class KnowledgeAnswerRequest(KnowledgeSearchRequest):
    answer_language: str = "zh-CN"
    runtime_model: RuntimeModelConfig | None = None


class KnowledgeCitation(ApiModel):
    evidence_id: str
    chunk_id: int | str
    asset_name: str
    page_number: int | None = None
    quote: str
    url: str | None = None


class KnowledgeAnswerDraft(ApiModel):
    answer: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class KnowledgeAnswerResponse(ApiModel):
    answer: str
    citations: list[KnowledgeCitation]
    insufficient_evidence: bool


class IndexAssetRequest(ApiModel):
    asset_id: int | str
    workspace_id: int
    project_id: int
    user_id: int = 0
    file_name: str
    mime_type: str | None = None
    storage_key: str | None = None
    content: str | None = None
    language: str | None = None
    checksum: str | None = None
    runtime_embedding: RuntimeEmbeddingConfig | None = None


class IndexAssetResponse(ApiModel):
    asset_id: int | str
    parse_status: str
    index_status: str
    chunk_count: int
    embedding_model: str
    embedding_dimension: int
    graph_entities: int = 0
    error_message: str | None = None


class GraphSearchRequest(ApiModel):
    workspace_id: int
    project_id: int
    query: str = Field(min_length=1, max_length=20_000)
    limit: int = Field(default=10, ge=1, le=50)


class GraphSearchResponse(ApiModel):
    nodes: list[dict[str, Any]]
    relationships: list[dict[str, Any]]


class GraphEntity(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    node_type: str = "ENTITY"


class GraphRelation(ApiModel):
    source: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=200)
    relation: str = Field(default="RELATED_TO", min_length=1, max_length=80)


class GraphExtraction(ApiModel):
    entities: list[GraphEntity] = Field(default_factory=list)
    relationships: list[GraphRelation] = Field(default_factory=list)


class RunAccepted(ApiModel):
    run_id: int | str
    status: str
    events_url: str
