from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.knowledge import router as knowledge_router
from api.routes.research import router as research_router
from api.routes.security import router as security_router
from api.routes.system import router as system_router
from config import get_settings
from core.container import ServiceContainer

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = await ServiceContainer.build(settings)
    app.state.container = container
    app.state.runtime = container.runtime
    app.state.indexer = container.indexer
    app.state.storage = container.storage
    app.state.graph_store = container.graph_store
    app.state.embedding = container.embedding
    app.state.events = container.events
    app.state.repository = container.repository
    app.state.model_gateway = container.model_gateway
    app.state.mcp_bridge = container.mcp_bridge
    try:
        yield
    finally:
        await container.close()


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    application.include_router(system_router)
    application.include_router(knowledge_router)
    application.include_router(research_router)
    application.include_router(security_router)
    return application


app = create_app()
