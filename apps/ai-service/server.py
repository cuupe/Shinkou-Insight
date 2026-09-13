"""Local AI-service launcher with a psycopg-compatible Windows event loop."""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn

from main import app


def run() -> None:
    parser = argparse.ArgumentParser(description="Run the Shinkou Insight AI service")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    config = uvicorn.Config(app, host=args.host, port=args.port, loop="asyncio")
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        # Uvicorn 0.36 deliberately chooses ProactorEventLoop for its normal
        # asyncio runner, while psycopg's async pool requires Selector.
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    run()
