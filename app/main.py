"""FastAPI application factory + lifespan."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.slack import router as slack_router
from app.config import get_settings
from app.core.db import dispose_all, get_system_engine
from app.core.logging_setup import setup_logging
from app.core.redis import close_redis, get_redis
from app.middleware.tenant import TenantMiddleware
from app.ui.routes import router as ui_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("Starting app in %s mode", settings.app_env)

    get_system_engine()
    await get_redis()

    yield

    logger.info("Shutting down")
    await dispose_all()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-tenant Slack Bot", lifespan=lifespan)

    app.add_middleware(TenantMiddleware)

    # Static files
    app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

    # Routers
    app.include_router(slack_router)
    app.include_router(admin_router)
    app.include_router(ui_router)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/")
    async def root():
        return JSONResponse({"service": "multi-tenant-slackbot", "ok": True})

    return app


app = create_app()