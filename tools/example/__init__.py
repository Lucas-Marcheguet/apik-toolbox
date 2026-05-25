"""
Example tool.

Exposes a single `router` (APIRouter) that the toolbox mounts at
  GET /tools/example/

Sub-routes and additional views are added to the same router or to
dedicated sub-routers included here.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

TOOL_DIR = Path(__file__).parent

# Jinja2Templates is patched by the tool manager to also resolve templates
# from the main app (so `{% extends "base.html" %}` works).
templates = Jinja2Templates(directory=str(TOOL_DIR))

router = APIRouter()

# ---------------------------------------------------------------------------
# Optional sub-router (e.g. for an internal API or additional view group)
# ---------------------------------------------------------------------------
api_router = APIRouter(prefix="/api")
router.include_router(api_router)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"active_view": "home"})


@router.get("/view/second")
async def second_view(request: Request):
    """Allows direct-URL access with the correct tab pre-selected."""
    return templates.TemplateResponse(request, "index.html", {"active_view": "second"})


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@api_router.get("/hello")
async def hello():
    return {"message": "Hello from the example tool API!"}
