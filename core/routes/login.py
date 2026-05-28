from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import get_config
from ..services.user import auth_service, oauth_state_store

PACKAGE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    if getattr(request.state, "user", None):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    try:
        result = auth_service.login(username, password)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password"},
            status_code=401,
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "session_token",
        result["session_token"],
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

@router.get("/auth/github")
async def github_auth(request: Request):
    config = get_config()
    if not config.github_client_id:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
    state = oauth_state_store.generate()
    params = urlencode({
        "client_id": config.github_client_id,
        "scope": "read:user user:email",
        "state": state,
    })
    return RedirectResponse(
        f"https://github.com/login/oauth/authorize?{params}", status_code=303
    )


@router.get("/auth/github/callback")
async def github_callback(request: Request, code: str, state: str):
    if not oauth_state_store.consume(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    config = get_config()
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": config.github_client_id,
                "client_secret": config.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_data = token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to obtain access token from GitHub")

    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        github_user = user_resp.json()

    github_id = str(github_user["id"])
    username = github_user.get("login", f"github_{github_id}")
    email = github_user.get("email") or f"{github_id}@users.noreply.github.com"

    result = auth_service.create_oauth_session("github", github_id, username, email)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "session_token",
        result["session_token"],
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        auth_service.logout(session_token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_token")
    return response


@router.get("/register")
async def register_page(request: Request):
    if getattr(request.state, "user", None):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "register.html", {})


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
):
    try:
        auth_service.register_user(username, password, email)
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": str(e)},
            status_code=400,
        )
    result = auth_service.login(username, password)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "session_token",
        result["session_token"],
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response
