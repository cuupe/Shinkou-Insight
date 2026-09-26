from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, extra="ignore"
    )


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: str
    mode: str


class AttachmentInput(ApiModel):
    """Trusted object-storage reference for a user-uploaded chat attachment."""

    attachment_id: int | str | None = None
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=255)
    storage_key: str = Field(min_length=1, max_length=1_000)
    file_size: int | None = Field(default=None, ge=0, le=100_000_000)


class ChatMessage(ApiModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)
    attachments: list[AttachmentInput] = Field(default_factory=list, max_length=10)


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
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = "high"
    extra_body: dict[str, Any] = Field(default_factory=dict)


class RuntimeModelConfig(ApiModel):
    """短生命周期的后端运行时模型配置，不进入用户可见的运行记录。"""

    base_url: str = Field(min_length=1, max_length=1_000)
    api_key: str = Field(min_length=1, max_length=10_000)
    model: str = Field(min_length=1, max_length=300)
    provider: str | None = None
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    retries: int = Field(default=2, ge=0, le=5)
    generation: ModelGenerationConfig = Field(default_factory=ModelGenerationConfig)
    structured_output_method: Literal[
        "json_schema", "function_calling", "json_mode"
    ] = "json_schema"


class RuntimeWebSearchConfig(ApiModel):
    """按项目/团队解析的联网搜索配置。"""

    provider: str = "brave"
    # DuckDuckGo's public HTML endpoint does not require a credential.
    api_key: str = Field(default="", max_length=10_000)
    base_url: str = Field(min_length=1, max_length=1_000)
    language: str = "zh-hans"
    sources: list[str] = Field(default_factory=list, max_length=8)
    timeout_seconds: float = Field(default=12, gt=0, le=30)


class WebSourceValidationRequest(ApiModel):
    url: str = Field(min_length=1, max_length=4_000)
    title: str = Field(default="", max_length=1_000)
    excerpt: str = Field(default="", max_length=20_000)


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
    model: str | None = None
    # False means the provider did not return usage metadata; zero is not
    # treated as a made-up estimate in that case.
    available: bool = False
    estimated: bool = False


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
    source_type: Literal["internal", "graph", "web"] = "internal"
    asset_id: int | str | None = None
    asset_name: str | None = None
    vector_score: float | None = None
    keyword_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    content_kind: Literal["fulltext", "abstract", "search_snippet"] | None = None
    published_at: str | None = None


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
    citation_completeness: float = Field(default=0.0, ge=0, le=1)
    evidence_support: float = Field(default=0.0, ge=0, le=1)
    factual_consistency: float = Field(default=0.0, ge=0, le=1)
    numeric_consistency: float = Field(default=0.0, ge=0, le=1)
    conflict_count: int = Field(default=0, ge=0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "BLOCKED"] = "MEDIUM"
    blocking_issues: list[str] = Field(default_factory=list)


class ReviewPolicy(ApiModel):
    require_citations: bool = True
    verify_numbers: bool = True
    escalate_conflicts: bool = True
    label_external: bool = True


class ReflectionResult(ApiModel):
    """One bounded self-check for a chat draft."""

    approved: bool = False
    issues: list[str] = Field(default_factory=list, max_length=8)
    corrections: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(default=0.5, ge=0, le=1)


class ReActAction(ApiModel):
    """One bounded action in the interactive chat tool loop.

    ``note`` is an operational summary for the trace, not hidden
    chain-of-thought. The runtime records the action and its observation
    separately so the UI can explain what happened safely.
    """

    action: Literal["SEARCH_INTERNAL", "SEARCH_GRAPH", "SEARCH_WEB", "FINAL"] = "FINAL"
    query: str = Field(default="", max_length=2_000)
    note: str = Field(default="", max_length=300)


class PlanStep(ApiModel):
    """A small executable step used by the chat Plan-and-Solve path."""

    id: str = Field(min_length=1, max_length=40)
    objective: str = Field(min_length=1, max_length=500)
    feedback: str = Field(
        default="",
        max_length=500,
        description="A concise user-facing progress update for this step, not hidden reasoning.",
    )
    action: Literal["SEARCH_INTERNAL", "SEARCH_GRAPH", "SEARCH_WEB", "SYNTHESIZE"] = (
        "SYNTHESIZE"
    )
    query: str = Field(default="", max_length=2_000)


class AgentPlan(ApiModel):
    """A bounded plan containing tasks, not hidden reasoning."""

    summary: str = Field(default="", max_length=500)
    steps: list[PlanStep] = Field(default_factory=list, max_length=6)


class PlanUpdateRequest(ApiModel):
    """Versioned control message for an active research plan."""

    mode: Literal["REPLACE", "APPEND", "PAUSE", "RESUME"] = "APPEND"
    expected_version: int | None = Field(default=None, ge=0)
    summary: str | None = Field(default=None, max_length=500)
    steps: list[PlanStep] = Field(default_factory=list, max_length=6)


class ResearchConfig(ApiModel):
    allow_web_search: bool = False
    max_research_rounds: int = Field(default=3, ge=1, le=8)
    report_template: str = "TECH_SELECTION"
    output_language: str = "zh-CN"
    top_k: int = Field(default=8, ge=1, le=20)
    retrieval_mode: Literal["VECTOR", "KEYWORD", "HYBRID"] = "HYBRID"
    use_reranker: bool = False
    tool_max_calls: int = Field(default=10, ge=1, le=50)
    require_tool_approval: bool = True
    disabled_tools: list[str] = Field(default_factory=list, max_length=100)
    reflection_enabled: bool = True
    review_policy: ReviewPolicy = Field(default_factory=ReviewPolicy)
    # AUTO selects a suitable path per request. DIRECT is for internal callers
    # and is intentionally not exposed as a separate UI option.
    strategy: Literal["AUTO", "DIRECT", "REACT", "PLAN_AND_SOLVE", "REFLECTION"] = (
        "AUTO"
    )
    # AUTO keeps routine chat on the single-agent path. Complex requests or
    # explicit user wording can opt into the coordinator and its child agents.
    multi_agent_mode: Literal["AUTO", "ON", "OFF"] = "AUTO"
    # 当后端没有解析出项目级模型时，作为默认模型的本次运行覆盖参数。
    generation: ModelGenerationConfig | None = None


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
    context_messages: list[ChatMessage] = Field(default_factory=list, max_length=40)
    attachments: list[AttachmentInput] = Field(default_factory=list, max_length=10)


class KnowledgeSearchRequest(ApiModel):
    workspace_id: int
    project_id: int
    query: str = Field(min_length=1, max_length=20_000)
    top_k: int = Field(default=8, ge=1, le=20)
    retrieval_mode: Literal["VECTOR", "KEYWORD", "HYBRID"] = "HYBRID"
    use_reranker: bool = False
    fusion_method: Literal["RRF", "WEIGHTED_RRF", "LINEAR"] = "WEIGHTED_RRF"
    candidate_k: int = Field(default=40, ge=1, le=200)
    rank_constant: int = Field(default=60, ge=1, le=200)
    vector_weight: float = Field(default=0.55, ge=0, le=1)
    keyword_weight: float = Field(default=0.45, ge=0, le=1)
    diversity_lambda: float = Field(default=0.9, ge=0, le=1)
    rerank_top_k: int = Field(default=20, ge=1, le=200)
    filters: dict[str, Any] = Field(default_factory=dict)
    runtime_embedding: RuntimeEmbeddingConfig | None = None

    @model_validator(mode="after")
    def validate_search_weights(self) -> "KnowledgeSearchRequest":
        if (
            self.retrieval_mode == "HYBRID"
            and self.vector_weight == 0
            and self.keyword_weight == 0
        ):
            raise ValueError("vector_weight and keyword_weight cannot both be zero")
        return self


class KnowledgeSearchResponse(ApiModel):
    query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    items: list[Evidence]
    search_trace: dict[str, Any] = Field(default_factory=dict)


class RetrievalItem(Evidence):
    pass


class RetrievalResponse(ApiModel):
    query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    items: list[RetrievalItem]
    search_trace: dict[str, Any] = Field(default_factory=dict)


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


class ChunkingConfig(ApiModel):
    strategy: Literal["natural", "paragraph", "fixed"] = "natural"
    chunk_size: int = Field(default=1200, ge=400, le=4000)
    chunk_overlap: int = Field(default=180, ge=0, le=1200)
    preserve_sections: bool = True

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkingConfig":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


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
    chunking: ChunkingConfig | None = None


class IndexAssetResponse(ApiModel):
    asset_id: int | str
    parse_status: str
    index_status: str
    chunk_count: int
    embedding_model: str
    embedding_dimension: int
    graph_entities: int = 0
    error_message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class AsyncToolCallRequest(ApiModel):
    """Request for a non-blocking, auditable tool invocation."""

    run_id: int | str
    tool: str = Field(min_length=1, max_length=200)
    input_data: dict[str, Any] = Field(default_factory=dict)
    allow_writes: bool = False
    confirmed: bool = False
    call_id: str | None = Field(default=None, max_length=120)


class ToolChainStepRequest(ApiModel):
    id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=200)
    input_data: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    continue_on_error: bool = False


class ToolChainRequest(ApiModel):
    run_id: int | str
    steps: list[ToolChainStepRequest] = Field(min_length=1, max_length=32)
    allow_writes: bool = False
    confirmed: bool = False
    chain_id: str | None = Field(default=None, max_length=120)
    timeout_seconds: float = Field(default=300, gt=0, le=1_800)
