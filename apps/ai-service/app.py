"""Backward-compatible ASGI import path.

Use ``main:app`` for new deployments. The application composition lives in
``api.application`` and routes are grouped by bounded context.
"""

from api.application import app

__all__ = ["app"]
