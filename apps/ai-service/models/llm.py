import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from models.schemas import (
    ModelChatResult,
    ModelGenerationConfig,
    TokenUsage,
)
from prompts.search_prompts import MODEL_GRAPH_HINTS, MODEL_SOURCE_HINTS

T = TypeVar(
    "T",
    bound=BaseModel,
)

_SILICONFLOW_THINKING_BUDGETS = {
    "low": 1_024,
    "medium": 4_096,
    "high": 16_384,
}


def _siliconflow_thinking_options(
    effort: str,
    extra_body: dict[str, Any],
    kwargs: dict[str, Any],
) -> None:
    """Translate the UI's three thinking levels into provider controls.

    SiliconFlow maps low/medium ``reasoning_effort`` to high for DeepSeek
    V4/V4-Flash, so the budget is the control that keeps the levels distinct.
    """

    extra_body["enable_thinking"] = effort != "none"
    budget = _SILICONFLOW_THINKING_BUDGETS.get(effort)
    if budget is not None:
        extra_body["thinking_budget"] = budget
    else:
        extra_body.pop("thinking_budget", None)
    if effort == "high":
        kwargs["reasoning_effort"] = effort


# =========================================================
# Exceptions
# =========================================================


class ModelGatewayError(Exception):
    """
    所有模型错误的父类。
    """

    pass


class ModelTimeoutError(ModelGatewayError):
    """
    模型请求超时。
    """

    pass


class ModelAuthError(ModelGatewayError):
    """
    API Key 错误、没有权限等。
    """

    pass


class ModelRateLimitError(ModelGatewayError):
    """
    请求太频繁或者额度限制。
    """

    pass


class ModelServerError(ModelGatewayError):
    """
    模型供应商服务器错误。
    """

    pass


class ModelRequestError(ModelGatewayError):
    """
    HTTP / 网络层错误。
    """

    pass


class ModelResponseError(ModelGatewayError):
    """
    模型返回格式不符合预期。
    """

    pass


_CONTEXT_WINDOW_KEYS = (
    "context_length",
    "context_window",
    "contextWindow",
    "max_context_length",
    "maxContextLength",
    "max_model_len",
    "maxModelLen",
    "max_input_tokens",
    "maxInputTokens",
    "input_token_limit",
    "inputTokenLimit",
    "model_context_length",
    "modelContextLength",
    "max_position_embeddings",
)


def _positive_int(value: Any) -> int | None:
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 2_000_000 else None


def _metadata_context_window(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    for key in _CONTEXT_WINDOW_KEYS:
        candidate = _positive_int(value.get(key))
        if candidate is not None:
            return candidate
    for key in ("top_provider", "topProvider", "limits", "metadata", "model_info", "modelInfo"):
        candidate = _metadata_context_window(value.get(key))
        if candidate is not None:
            return candidate
    return None


def extract_model_context_window(payload: Any, model: str) -> int | None:
    """Read context metadata from common OpenAI-compatible model catalogs."""

    if not isinstance(payload, dict):
        return None
    raw_models = payload.get("data")
    candidates = raw_models if isinstance(raw_models, list) else []
    requested = str(model or "").strip().casefold()
    matching = [
        item
        for item in candidates
        if isinstance(item, dict)
        and any(str(item.get(key) or "").strip().casefold() == requested for key in ("id", "model", "name"))
    ]
    if matching:
        return _metadata_context_window(matching[0])
    if len(candidates) == 1:
        return _metadata_context_window(candidates[0])
    return _metadata_context_window(payload)


async def fetch_model_context_window(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    """Fetch provider metadata without sending a billable completion request."""

    started_at = time.perf_counter()
    url = f"{base_url.rstrip('/')}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        response = await client.get(url, headers=headers, timeout=timeout_seconds)
    except httpx.TimeoutException:
        return {
            "status": "unavailable",
            "available": False,
            "model": model,
            "detail": "模型目录请求超时，保留当前手动配置的上下文窗口",
            "latencyMs": int((time.perf_counter() - started_at) * 1000),
        }
    except httpx.RequestError as exc:
        return {
            "status": "unavailable",
            "available": False,
            "model": model,
            "detail": f"模型目录请求失败：{str(exc)[:240]}",
            "latencyMs": int((time.perf_counter() - started_at) * 1000),
        }

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    if response.status_code in {401, 403}:
        return {"status": "unavailable", "available": False, "model": model, "detail": "模型目录认证失败，请检查凭证", "latencyMs": latency_ms}
    if response.is_error:
        return {"status": "unavailable", "available": False, "model": model, "detail": f"模型目录不支持查询（HTTP {response.status_code}）", "latencyMs": latency_ms}
    try:
        payload = response.json()
    except ValueError:
        return {"status": "unavailable", "available": False, "model": model, "detail": "模型目录返回的不是有效 JSON", "latencyMs": latency_ms}

    context_window = extract_model_context_window(payload, model)
    if context_window is None:
        return {"status": "unavailable", "available": False, "model": model, "detail": "该服务未公开模型最大上下文窗口，请手动填写", "latencyMs": latency_ms}
    return {
        "status": "ok",
        "available": True,
        "model": model,
        "contextWindow": context_window,
        "source": "provider-model-catalog",
        "latencyMs": latency_ms,
    }


# =========================================================
# Interface
# =========================================================


class ModelGateway(Protocol):
    """
    业务层只依赖这个接口。
    """

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> ModelChatResult: ...

    async def structured(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float | None = None,
    ) -> tuple[T, ModelChatResult]: ...

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator["ModelStreamChunk"]: ...

    def with_generation(self, generation: ModelGenerationConfig) -> "ModelGateway": ...


@dataclass(frozen=True)
class ModelStreamChunk:
    """One provider response delta and optional usage metadata."""

    delta: str = ""
    usage: TokenUsage | None = None


class UnavailableModelGateway:
    """进程级模型未配置时的显式占位实现。

    项目级模型由 Java 从数据库解析后注入单次运行；未选择项目模型时才会触发这里。
    """

    async def chat(self, messages: list[dict[str, str]], *, temperature: float | None = None) -> ModelChatResult:
        raise ModelGatewayError("no default LLM configured; select a project model configuration")


    async def structured(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float | None = None,
    ) -> tuple[T, ModelChatResult]:
        raise ModelGatewayError("no default LLM configured; select a project model configuration")

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[ModelStreamChunk]:
        raise ModelGatewayError("no default LLM configured; select a project model configuration")
        yield ModelStreamChunk()

    def with_generation(self, generation: ModelGenerationConfig) -> "UnavailableModelGateway":
        return self


class LangChainModelGateway:
    """LangChain adapter for OpenAI-compatible chat models.

    The application depends on the small ``ModelGateway`` contract instead of
    exposing LangChain runnables to every agent. This keeps provider details in
    one place while still using LangChain's message conversion and structured
    output support consistently.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        provider: str | None = None,
        timeout_seconds: float = 60,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
        structured_output_method: str = "json_schema",
        generation: ModelGenerationConfig | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("runtime model base URL is required")
        if not api_key:
            raise ValueError("runtime model API key is required")
        if not model:
            raise ValueError("runtime model id is required")
        if structured_output_method not in {"json_schema", "function_calling", "json_mode"}:
            raise ValueError("structured output method must be json_schema, function_calling, or json_mode")

        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - dependency is required in production
            raise RuntimeError("langchain-openai is required for the LangChain model gateway") from exc

        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = (provider or "").strip().casefold()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.structured_output_method = structured_output_method
        self.generation = generation or ModelGenerationConfig()
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "base_url": self.base_url,
            "timeout": timeout_seconds,
            "max_retries": max_retries,
        }
        if client is not None:
            kwargs["http_async_client"] = client
        self._chat_model = ChatOpenAI(**kwargs)

    def with_generation(self, generation: ModelGenerationConfig) -> "LangChainModelGateway":
        return LangChainModelGateway(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            provider=self.provider,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            client=self.client,
            structured_output_method=self.structured_output_method,
            generation=generation,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> ModelChatResult:
        started_at = time.perf_counter()
        try:
            response = await self._chat_model.ainvoke(
                _to_langchain_messages(messages),
                **self._invoke_kwargs(temperature),
            )
        except Exception as exc:
            raise _translate_langchain_error(exc) from exc
        return _model_chat_result(
            response,
            fallback_model=self.model,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[ModelStreamChunk]:
        try:
            async for chunk in self._chat_model.astream(
                _to_langchain_messages(messages),
                **self._invoke_kwargs(temperature),
            ):
                content = _message_content(chunk)
                if content:
                    yield ModelStreamChunk(delta=content)
        except Exception as exc:
            raise _translate_langchain_error(exc) from exc

    async def structured(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float | None = None,
    ) -> tuple[T, ModelChatResult]:
        started_at = time.perf_counter()
        runnable = self._chat_model.with_structured_output(
            schema,
            method=self.structured_output_method,
            include_raw=True,
        )
        try:
            response = await runnable.ainvoke(
                _to_langchain_messages(messages),
                **self._invoke_kwargs(temperature, run_name=f"shinkou.llm.structured.{schema.__name__}"),
            )
        except Exception as exc:
            raise _translate_langchain_error(exc) from exc

        if not isinstance(response, dict):
            raise ModelResponseError("LangChain structured output returned an unexpected value")
        parsing_error = response.get("parsing_error")
        if parsing_error:
            raise ModelResponseError(f"LLM structured output could not be parsed: {parsing_error}")
        parsed = response.get("parsed")
        if parsed is None:
            raise ModelResponseError("LLM structured output is empty")
        try:
            value = parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
        except Exception as exc:
            raise ModelResponseError(f"LLM structured output does not match {schema.__name__}") from exc

        raw = response.get("raw")
        if raw is None:
            result = ModelChatResult(
                content=json.dumps(value.model_dump(), ensure_ascii=False),
                model=self.model,
                usage=TokenUsage(available=False),
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )
        else:
            result = _model_chat_result(
                raw,
                fallback_model=self.model,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
            )
        return value, result

    def _invoke_kwargs(self, temperature: float | None, *, run_name: str = "shinkou.llm.chat") -> dict[str, Any]:
        generation = self.generation
        kwargs: dict[str, Any] = {
            "temperature": generation.temperature if temperature is None else temperature,
            "top_p": generation.top_p,
            "max_tokens": generation.max_tokens,
            "frequency_penalty": generation.frequency_penalty,
            "presence_penalty": generation.presence_penalty,
            "config": {"run_name": run_name},
        }
        if generation.seed is not None:
            kwargs["seed"] = generation.seed
        if generation.stop:
            kwargs["stop"] = generation.stop
        extra_body = dict(generation.extra_body)
        if self.provider in {"siliconflow", "silicon flow", "硅基流动"}:
            effort = generation.reasoning_effort or "none"
            _siliconflow_thinking_options(effort, extra_body, kwargs)
        elif generation.reasoning_effort and generation.reasoning_effort != "none":
            kwargs["reasoning_effort"] = generation.reasoning_effort
        if generation.top_k is not None:
            extra_body.setdefault("top_k", generation.top_k)
        if extra_body:
            kwargs["extra_body"] = extra_body
        return kwargs


def _to_langchain_messages(messages: Sequence[dict[str, str]]) -> list[Any]:
    """Convert the transport-neutral message shape into LangChain messages."""

    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    converted: list[Any] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        elif role == "tool":
            converted.append(ToolMessage(content=content, tool_call_id=message.get("tool_call_id", "runtime")))
        else:
            converted.append(HumanMessage(content=content))
    return converted


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                value = block.get("text") or block.get("content")
                if value:
                    parts.append(str(value))
        return "".join(parts)
    return str(content or "")


def _model_chat_result(message: Any, *, fallback_model: str, latency_ms: int) -> ModelChatResult:
    """Normalize an AIMessage without leaking provider-specific metadata."""

    response_metadata = getattr(message, "response_metadata", None) or {}
    usage_metadata = getattr(message, "usage_metadata", None) or {}
    token_usage = response_metadata.get("token_usage") or response_metadata.get("usage") or {}
    usage_available = bool(usage_metadata or token_usage)
    input_tokens = int(usage_metadata.get("input_tokens", token_usage.get("prompt_tokens", 0)) or 0)
    output_tokens = int(usage_metadata.get("output_tokens", token_usage.get("completion_tokens", 0)) or 0)
    total_tokens = int(usage_metadata.get("total_tokens", token_usage.get("total_tokens", input_tokens + output_tokens)) or 0)
    content = _message_content(message)
    if not content.strip():
        raise ModelResponseError("LLM returned empty content")
    return ModelChatResult(
        content=content,
        model=str(response_metadata.get("model_name") or response_metadata.get("model") or fallback_model),
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            available=usage_available,
        ),
        latency_ms=latency_ms,
        request_id=(response_metadata.get("id") or response_metadata.get("request_id")),
    )


def _translate_langchain_error(error: Exception) -> ModelGatewayError:
    """Map provider exceptions to the stable application error taxonomy."""

    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return ModelTimeoutError("LLM request timed out")
    status_code = getattr(error, "status_code", None)
    if status_code is None:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
    detail = _langchain_error_detail(error)
    error_type = type(error).__name__.casefold()
    if any(marker in error_type for marker in ("connection", "connecterror", "network")):
        return ModelRequestError(f"LLM network request failed{detail or f': {type(error).__name__}'}")
    if status_code in {401, 403}:
        return ModelAuthError(f"LLM authentication failed{detail}")
    if status_code == 429:
        return ModelRateLimitError(f"LLM rate limit exceeded{detail}")
    if isinstance(status_code, int) and status_code >= 500:
        return ModelServerError(f"LLM provider server error (status={status_code}){detail}")
    status_suffix = f" (status={status_code})" if status_code is not None else ""
    return ModelRequestError(f"LLM request failed{status_suffix}: {detail or type(error).__name__}")


def _langchain_error_detail(error: Exception) -> str:
    """Keep provider diagnostics while removing anything that looks like a secret.

    LangChain/OpenAI exceptions otherwise collapse into a generic ``OpenAIError``
    message, which makes connection testing impossible to diagnose from the UI.
    The provider response is useful here (for example SiliconFlow's 20012 model
    error), but it must be bounded and must never echo an Authorization header.
    """

    candidates: list[str] = []
    current: BaseException | None = error
    visited: set[int] = set()
    for _ in range(4):
        if current is None or id(current) in visited:
            break
        visited.add(id(current))
        response = getattr(current, "response", None)
        if response is not None:
            try:
                text = response.text
            except Exception:  # pragma: no cover - defensive for provider exceptions
                text = ""
            if text:
                candidates.append(str(text))

        body = getattr(current, "body", None)
        if body:
            try:
                candidates.append(json.dumps(body, ensure_ascii=False, default=str))
            except Exception:  # pragma: no cover - defensive only
                candidates.append(str(body))

        message = str(current).strip()
        if message:
            candidates.append(message)
        current = current.__cause__ or current.__context__

    for candidate in candidates:
        normalized = re.sub(r"[\r\n\t]+", " ", candidate).strip()
        if not normalized:
            continue
        normalized = re.sub(r"(?i)(bearer\s+)[^\s,}]+", r"\1[REDACTED]", normalized)
        normalized = re.sub(
            r"(?i)((?:api[_-]?key|access[_-]?token)\s*[:=]\s*[\"']?)[^\"'\s,}]+",
            r"\1[REDACTED]",
            normalized,
        )
        return f": {normalized[:1000]}"
    return ""

    async def structured(self, messages: list[dict[str, str]], schema: type[T], *, temperature: float | None = None) -> tuple[T, ModelChatResult]:
        raise ModelGatewayError("no default LLM configured; select a project model configuration")


# =========================================================
# HTTP implementation
# =========================================================


class HttpModelGateway:
    """
    使用 OpenAI-compatible Chat Completions 风格 HTTP API。

    即：

    POST {base_url}/chat/completions

    Request:

    {
        "model": "...",
        "messages": [...],
        "temperature": 0.2
    }
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        model: str,
        provider: str | None = None,
        timeout_seconds: float = 60,
        max_retries: int = 2,
        generation: ModelGenerationConfig | None = None,
    ):
        if not base_url:
            raise ValueError("runtime model base URL is required")

        if not api_key:
            raise ValueError("runtime model API key is required")

        if not model:
            raise ValueError("runtime model id is required")

        self.client = client
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = (provider or "").strip().casefold()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.generation = generation or ModelGenerationConfig()

    def with_generation(self, generation: ModelGenerationConfig) -> "HttpModelGateway":
        return HttpModelGateway(
            client=self.client,
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            provider=self.provider,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            generation=generation,
        )

    # =====================================================
    # 普通聊天
    # =====================================================

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> ModelChatResult:

        url = f"{self.base_url}" "/chat/completions"

        headers = {
            "Authorization": (f"Bearer {self.api_key}"),
            "Content-Type": "application/json",
        }

        payload = self._build_payload(messages, temperature=temperature, stream=False)

        started_at = time.perf_counter()

        try:
            response = await self.client.post(
                url,
                headers=headers,
                json=payload,
            )

        except httpx.TimeoutException as exc:

            raise ModelTimeoutError("LLM request timed out") from exc

        except httpx.RequestError as exc:

            detail = str(exc).strip() or repr(exc)
            raise ModelRequestError(f"LLM network request failed at {url}: {detail[:1000]}") from exc

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        self._raise_for_status(response)

        try:
            data = response.json()

        except ValueError as exc:

            raise ModelResponseError("LLM response is not valid JSON") from exc

        content = self._extract_content(data)

        usage = self._extract_usage(data)

        model_name = data.get(
            "model",
            self.model,
        )

        request_id = response.headers.get("x-request-id") or response.headers.get(
            "request-id"
        )

        return ModelChatResult(
            content=content,
            model=model_name,
            usage=usage,
            latency_ms=latency_ms,
            request_id=request_id,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[ModelStreamChunk]:
        """Stream OpenAI-compatible SSE deltas without buffering the answer."""

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = self._build_payload(messages, temperature=temperature, stream=True)
        usage: TokenUsage | None = None
        try:
            async with self.client.stream("POST", url, headers=headers, json=payload) as response:
                if not 200 <= response.status_code < 300:
                    await response.aread()
                    self._raise_for_status(response)
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":") or line.startswith("event:"):
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        data = json.loads(line)
                    except ValueError as exc:
                        raise ModelResponseError("LLM streaming response is not valid JSON") from exc
                    raw_usage = data.get("usage")
                    if raw_usage:
                        usage = self._extract_usage(data)
                    delta = self._extract_stream_delta(data)
                    if delta:
                        yield ModelStreamChunk(delta=delta)
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError("LLM request timed out") from exc
        except httpx.RequestError as exc:
            detail = str(exc).strip() or repr(exc)
            raise ModelRequestError(f"LLM network request failed at {url}: {detail[:1000]}") from exc
        if usage is not None:
            yield ModelStreamChunk(usage=usage)

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None,
        stream: bool,
    ) -> dict[str, Any]:
        generation = self.generation
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": generation.temperature if temperature is None else temperature,
            "top_p": generation.top_p,
            "max_tokens": generation.max_tokens,
            "frequency_penalty": generation.frequency_penalty,
            "presence_penalty": generation.presence_penalty,
        }
        if stream:
            payload["stream"] = True
            # OpenAI-compatible providers return usage for a stream only when
            # this option is explicitly requested.
            payload["stream_options"] = {"include_usage": True}
        if generation.top_k is not None:
            payload["top_k"] = generation.top_k
        if generation.seed is not None:
            payload["seed"] = generation.seed
        if generation.stop:
            payload["stop"] = generation.stop
        extra_body = dict(generation.extra_body)
        if self.provider in {"siliconflow", "silicon flow", "硅基流动"}:
            effort = generation.reasoning_effort or "none"
            options: dict[str, Any] = {}
            _siliconflow_thinking_options(effort, extra_body, options)
            payload.update(options)
        elif generation.reasoning_effort and generation.reasoning_effort != "none":
            payload["reasoning_effort"] = generation.reasoning_effort
        payload.update(extra_body)
        return payload

    def _extract_stream_delta(self, data: dict[str, Any]) -> str:
        try:
            choice = (data.get("choices") or [])[0]
        except (IndexError, TypeError):
            return ""
        delta = choice.get("delta") or choice.get("message") or {}
        content = delta.get("content", "") if isinstance(delta, dict) else ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                str(item.get("text", "")) for item in content if isinstance(item, dict) and item.get("text")
            )
        return ""

    # =====================================================
    # JSON / Structured Output
    # =====================================================

    async def structured(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float | None = None,
    ) -> tuple[T, ModelChatResult]:

        schema_json = json.dumps(
            schema.model_json_schema(),
            ensure_ascii=False,
        )

        structure_instruction = {
            "role": "system",
            "content": (
                "你必须只返回一个合法 JSON 对象。"
                "不要返回 Markdown。"
                "不要返回 ```json 代码块。"
                "不要添加任何解释文字。"
                "返回结果必须满足以下 JSON Schema：\n"
                f"{schema_json}"
            ),
        }

        structured_messages = [
            structure_instruction,
            *messages,
        ]

        result = await self.chat(
            structured_messages,
            temperature=temperature,
        )

        raw_content = result.content.strip()

        cleaned_content = self._clean_json_text(raw_content)

        try:
            json_data = json.loads(cleaned_content)

        except json.JSONDecodeError as exc:

            raise ModelResponseError(
                "Model did not return valid JSON. " f"Raw content: {raw_content[:500]}"
            ) from exc

        try:
            parsed = schema.model_validate(json_data)

        except ValidationError as exc:

            raise ModelResponseError(
                "Model JSON does not match schema. " f"Errors: {exc.errors()}"
            ) from exc

        return (
            parsed,
            result,
        )

    # =====================================================
    # HTTP status
    # =====================================================

    def _raise_for_status(
        self,
        response: httpx.Response,
    ) -> None:

        status_code = response.status_code

        if 200 <= status_code < 300:
            return

        body = response.text[:1000]

        if status_code in {
            401,
            403,
        }:
            raise ModelAuthError(
                "LLM authentication failed. "
                f"status={status_code}, "
                f"response={body}"
            )

        if status_code == 429:
            raise ModelRateLimitError("LLM rate limit exceeded. " f"response={body}")

        if status_code >= 500:
            raise ModelServerError(
                "LLM provider server error. "
                f"status={status_code}, "
                f"response={body}"
            )

        raise ModelRequestError(
            "LLM request failed. " f"status={status_code}, " f"response={body}"
        )

    # =====================================================
    # Content parser
    # =====================================================

    def _extract_content(
        self,
        data: dict[str, Any],
    ) -> str:

        try:
            content = data["choices"][0]["message"]["content"]

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:

            raise ModelResponseError("Unexpected LLM response structure") from exc

        if not isinstance(
            content,
            str,
        ):
            raise ModelResponseError("LLM content is not a string")

        if not content.strip():
            raise ModelResponseError("LLM returned empty content")

        return content

    # =====================================================
    # Token parser
    # =====================================================

    def _extract_usage(
        self,
        data: dict[str, Any],
    ) -> TokenUsage:

        raw_usage = data.get("usage") or {}

        input_tokens = int(
            raw_usage.get(
                "prompt_tokens",
                raw_usage.get(
                    "input_tokens",
                    0,
                ),
            )
            or 0
        )

        output_tokens = int(
            raw_usage.get(
                "completion_tokens",
                raw_usage.get(
                    "output_tokens",
                    0,
                ),
            )
            or 0
        )

        total_tokens = int(
            raw_usage.get(
                "total_tokens",
                input_tokens + output_tokens,
            )
            or 0
        )

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            available=bool(raw_usage),
        )

    # =====================================================
    # JSON cleaner
    # =====================================================

    def _clean_json_text(
        self,
        text: str,
    ) -> str:

        text = text.strip()

        if not text.startswith("```"):
            return text

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines).strip()


class MockModelGateway:
    """Deterministic provider for local development and CI."""

    model = "mock-agent"

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> ModelChatResult:
        user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        content = f"基于当前项目证据处理：{user_text[:500]}"
        return ModelChatResult(
            content=content,
            model=self.model,
            usage=TokenUsage(input_tokens=len(str(messages)) // 4, output_tokens=len(content) // 2),
            request_id="mock",
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[ModelStreamChunk]:
        result = await self.chat(messages, temperature=temperature)
        for index in range(0, len(result.content), 12):
            await asyncio.sleep(0)
            yield ModelStreamChunk(delta=result.content[index : index + 12])
        yield ModelStreamChunk(usage=result.usage)

    async def structured(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float | None = None,
    ) -> tuple[T, ModelChatResult]:
        from models.schemas import AgentPlan, EvidenceEvaluation, Finding, PlanItem, ReActAction, ReflectionResult, ReportDraft, ReviewResult

        goal = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "研究目标")
        if schema is PlanItem:
            value: Any = {"id": "Q1", "question": goal[:500], "source": "BOTH", "rationale": "先核对项目资料，再补充外部信息"}
        elif schema is AgentPlan:
            first_action = "SEARCH_GRAPH" if any(marker in goal.casefold() for marker in MODEL_GRAPH_HINTS) else "SEARCH_INTERNAL"
            value = {
                "summary": "先核对项目资料，再整理结论",
                "steps": [
                    {"id": "S1", "objective": "核对项目实体关系" if first_action == "SEARCH_GRAPH" else "核对与问题相关的项目资料", "action": first_action, "query": goal[:500]},
                    {"id": "S2", "objective": "整理最终回答", "action": "SYNTHESIZE", "query": ""},
                ],
            }
        elif schema is ReActAction:
            normalized_goal = goal.casefold()
            if any(marker in normalized_goal for marker in MODEL_GRAPH_HINTS):
                action = "SEARCH_GRAPH"
            else:
                action = "SEARCH_INTERNAL" if any(marker in normalized_goal for marker in MODEL_SOURCE_HINTS) else "FINAL"
            value = {"action": action, "query": goal[:500], "note": "先核对项目实体关系" if action == "SEARCH_GRAPH" else "先核对与问题直接相关的项目资料"}
        elif schema is EvidenceEvaluation:
            has_evidence = "证据数量=0" not in goal and "没有可用证据" not in goal
            value = {"sufficient": has_evidence, "next_action": "ENOUGH" if has_evidence else "MORE_INTERNAL", "missing": [] if has_evidence else ["需要更多项目证据"], "conflicts": []}
        elif schema is Finding:
            value = {"id": "F1", "kind": "fact", "statement": "项目资料已提供与研究目标相关的可追溯证据。", "evidence_ids": ["E1"], "confidence": 0.72}
        elif schema is ReportDraft:
            value = {"title": "研究报告", "executive_summary": "以下结论仅基于已检索且可追溯的项目证据。", "sections": [{"heading": "结论", "content": "已完成证据整理。", "evidence_ids": ["E1"]}], "recommendations": ["对关键结论进行人工复核"], "limitations": ["当前结果受可用资料范围限制"], "evidence_ids": ["E1"]}
        elif schema is ReviewResult:
            value = {"approved": True, "issues": [], "missing_citations": [], "rewrite_instructions": []}
        elif schema is ReflectionResult:
            value = {"approved": True, "issues": [], "corrections": [], "confidence": 0.9}
        else:
            value = {}
        raw = ModelChatResult(content=json.dumps(value, ensure_ascii=False), model=self.model)
        return schema.model_validate(value), raw


def build_model_gateway(
    *,
    mode: str,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    provider: str | None = None,
    timeout_seconds: float = 60,
    max_retries: int = 2,
    client: httpx.AsyncClient | None = None,
    structured_output_method: str = "json_schema",
    generation: ModelGenerationConfig | None = None,
) -> ModelGateway:
    """Build the configured model adapter used by HTTP and Agent execution."""

    normalized_mode = mode.casefold()
    if normalized_mode == "mock":
        return MockModelGateway()
    if normalized_mode not in {"http", "openai", "compatible", "langchain"}:
        raise ValueError("LLM_MODE must be http, openai, compatible, langchain, or mock")
    if not base_url or not api_key or not model:
        return UnavailableModelGateway()
    if normalized_mode == "langchain":
        return LangChainModelGateway(
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider=provider,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
            structured_output_method=structured_output_method,
            generation=generation,
        )
    return HttpModelGateway(
        client=client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)),
        base_url=base_url,
        api_key=api_key,
        model=model,
        provider=provider,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        generation=generation,
    )
