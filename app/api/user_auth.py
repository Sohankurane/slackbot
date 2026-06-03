"""User login / logout — separate from admin auth."""

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.db import get_system_sessionmaker
from app.services.user_account_service import authenticate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["user-auth"])
templates = Jinja2Templates(directory="app/ui/templates")


@router.get("/user/login", response_class=HTMLResponse)
async def user_login_page(request: Request):
    if request.session.get("user_account_id"):
        return RedirectResponse("/user/dashboard", status_code=303)
    return templates.TemplateResponse(
        "user_login.html", {"request": request, "error": None}
    )


@router.post("/user/login", response_class=HTMLResponse)
async def user_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    sm = get_system_sessionmaker()
    async with sm() as session:
        acct = await authenticate(session, username=username, password=password)
        if not acct:
            logger.warning("Failed user login for username=%s", username)
            return templates.TemplateResponse(
                "user_login.html",
                {"request": request, "error": "Invalid username or password"},
                status_code=401,
            )
        # Separate session key — walled off from admin_user_id
        request.session["user_account_id"] = acct.id
        request.session["user_username"] = acct.username
        logger.info("User login: %s", acct.username)

    return RedirectResponse("/user/dashboard", status_code=303)


@router.post("/user/logout")
async def user_logout(request: Request):
    username = request.session.get("user_username")
    # Only clear the user keys, not the whole session (in case admin also logged in same browser)
    request.session.pop("user_account_id", None)
    request.session.pop("user_username", None)
    logger.info("User logout: %s", username)
    return RedirectResponse("/user/login", status_code=303)