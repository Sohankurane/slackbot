"""Login / Register / Logout endpoints for the admin UI."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.core.security import hash_password, verify_password
from app.models import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/ui/templates")


# ---------- Login ----------

@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("admin_user_id"):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": None}
    )


@router.post("/admin/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.username == username.strip())
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active or not verify_password(password, user.password_hash):
            logger.warning("Failed login attempt for username=%s", username)
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid username or password"},
                status_code=401,
            )

        user.last_login_at = datetime.now(timezone.utc)
        await session.commit()

        request.session["admin_user_id"] = user.id
        request.session["admin_username"] = user.username
        logger.info("Admin login: %s", user.username)

    return RedirectResponse("/admin", status_code=303)


# ---------- Register ----------

@router.get("/admin/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if request.session.get("admin_user_id"):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        "register.html", {"request": request, "error": None, "values": {}}
    )


@router.post("/admin/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    username = username.strip()
    values = {"username": username}

    # Validate
    if len(username) < 3:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username must be at least 3 characters", "values": values},
            status_code=400,
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Password must be at least 6 characters", "values": values},
            status_code=400,
        )
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match", "values": values},
            status_code=400,
        )

    sm = get_system_sessionmaker()
    async with sm() as session:
        # Check duplicate
        result = await session.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        if result.scalar_one_or_none():
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "Username already taken", "values": values},
                status_code=409,
            )

        # Create
        user = AdminUser(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Auto-login
        request.session["admin_user_id"] = user.id
        request.session["admin_username"] = user.username
        logger.info("Admin registered + logged in: %s", user.username)

    return RedirectResponse("/admin", status_code=303)


# ---------- Logout ----------

@router.post("/admin/logout")
async def logout(request: Request):
    username = request.session.get("admin_username")
    request.session.clear()
    logger.info("Admin logout: %s", username)
    return RedirectResponse("/admin/login", status_code=303)