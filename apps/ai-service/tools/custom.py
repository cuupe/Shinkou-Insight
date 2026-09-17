from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from tools.registry import ToolSpec


CUSTOM_TOOL_SPEC = "__shinkou_tool_spec__"


def custom_tool(
    name: str,
    *,
    description: str = "",
    permission: Literal["READ", "WRITE"] = "READ",
    timeout_seconds: float = 30,
    max_concurrency: int = 4,
    requires_confirmation: bool = False,
    input_schema: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Declare a developer-owned Python tool.

    The decorator only attaches a validated contract. The loader performs the
    actual registration, so importing a custom module never mutates the global
    registry by itself.
    """

    spec = ToolSpec(
        name=name,
        description=description,
        permission=permission,
        timeout_seconds=timeout_seconds,
        max_concurrency=max_concurrency,
        requires_confirmation=requires_confirmation,
        input_schema=input_schema or {"type": "object"},
    )

    def decorate(handler: Callable[..., Any]) -> Callable[..., Any]:
        setattr(handler, CUSTOM_TOOL_SPEC, spec)
        return handler

    return decorate
