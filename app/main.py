"""FastAPI application factory + lifespan."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.slack import router as slack_router
from app.config import get_settings
from app.core.db import dispose_all, get_system_engine
from app.core.logging_setup import setup_logging
from app.core.redis import close_redis, get_redis
from app.middleware.tenant import TenantMiddleware
from app.ui.routes import router as ui_router

from app.api.oauth import router as oauth_router
from app.api.user_auth import router as user_auth_router
from app.api.user_dashboard import router as user_dashboard_router

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
    settings = get_settings()
    app = FastAPI(title="Multi-tenant Slack Bot", lifespan=lifespan)

    # ---- Routes ----
    app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
    app.include_router(auth_router)
    app.include_router(user_auth_router)
    app.include_router(user_dashboard_router)
    app.include_router(slack_router)
    app.include_router(admin_router)
    app.include_router(ui_router)
    app.include_router(oauth_router)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/")
    async def root():
        return JSONResponse({"service": "multi-tenant-slackbot", "ok": True})

    # ---- Browser auth gate (HTML routes redirect, API routes 401) ----
    @app.middleware("http")
    async def auth_redirect_middleware(request: Request, call_next):
        path = request.url.path

        # --- Admin area guard (admin session or API token) ---
        admin_needs_auth = (
            path.startswith("/admin")
            and not path.startswith("/admin/login")
            and not path.startswith("/admin/logout")
            and not path.startswith("/admin/register")
        ) or path.startswith("/api/admin")

        if admin_needs_auth:
            session_uid = request.session.get("admin_user_id")
            header_token = request.headers.get("x-admin-token")
            expected = settings.admin_token
            authed_by_token = bool(header_token) and header_token == expected
            if not session_uid and not authed_by_token:
                if path.startswith("/api/"):
                    return JSONResponse({"detail": "not_authenticated"}, status_code=401)
                return RedirectResponse("/admin/login", status_code=303)

        # --- User area guard (user session only) ---
        user_needs_auth = (
            path.startswith("/user")
            and not path.startswith("/user/login")
            and not path.startswith("/user/logout")
        ) or path.startswith("/api/user")

        if user_needs_auth:
            user_uid = request.session.get("user_account_id")
            if not user_uid:
                if path.startswith("/api/"):
                    return JSONResponse({"detail": "not_authenticated"}, status_code=401)
                return RedirectResponse("/user/login", status_code=303)

        return await call_next(request)

    # ---- Middlewares
    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.app_secret_key,
        session_cookie="slackbot_admin",
        max_age=60 * 60 * 8,
        same_site="lax",
        https_only=False,
    )

    return app


app = create_app()