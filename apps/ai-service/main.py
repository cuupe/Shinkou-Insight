"""ASGI entrypoint for the Shinkou Insight AI service.

Keep the application object in ``app.py`` for backwards compatibility with
existing deployments; new commands should use ``main:app``.
"""

import asyncio
import sys


if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    # psycopg's async pool does not support Windows' default Proactor loop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from app import app  # noqa: E402

__all__ = ["app"]
