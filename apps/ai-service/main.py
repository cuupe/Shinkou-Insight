"""ASGI entrypoint for the Shinkou Insight AI service.

Keep the application object in ``app.py`` for backwards compatibility with
existing deployments; new commands should use ``main:app``.
"""

from app import app

__all__ = ["app"]
