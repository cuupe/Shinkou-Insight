from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import Header, HTTPException, Request, status

from config import get_settings
from models.llm import (
    ModelAuthError,
    ModelGatewayError,
    ModelRateLimitError,
    ModelRequestError,
    ModelResponseError,
    ModelServerError,
    ModelTimeoutError,
)


def verify_internal_api_key(
    x_internal_api_key: Annotated[str | None, Header()] = None,
) -> None:
    settings = get_settings()
    if x_internal_api_key is None or not secrets.compare_digest(
        x_internal_api_key,
        settings.internal_api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )


def http_model_error(error: ModelGatewayError) -> HTTPException:
    if isinstance(error, ModelTimeoutError):
        return HTTPException(504, str(error))
    if isinstance(error, ModelRateLimitError):
        return HTTPException(429, str(error))
    if isinstance(
        error, (ModelAuthError, ModelServerError, ModelResponseError, ModelRequestError)
    ):
        return HTTPException(502, str(error))
    return HTTPException(500, str(error))


def request_container(request: Request) -> Any:
    return request.app.state.container
