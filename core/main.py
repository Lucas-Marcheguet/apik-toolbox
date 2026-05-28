from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tortoise.contrib.fastapi import RegisterTortoise

from .config import get_config
from .routes.login import router as login_router
from .services.tool_manager import LoadedTool, discover_tools, register_tools
from .services.user import auth_service

PACKAGE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Tortoise ORM helpers
# ---------------------------------------------------------------------------

def _collect_model_modules(tools: list[LoadedTool]) -> list[str]:
    """Return the list of Tortoise model module paths to register.

    Always includes ``core.models``. Any tool that ships a ``models.py``
    (or a ``models/`` package) next to its ``__init__.py`` is also included
    so that tool-specific models are discovered automatically.
    """
    modules: list[str] = ["core.models"]
    for tool in tools:
        tool_dir = tool.tool_dir
        has_models = (
            (tool_dir / "models.py").exists()
            or (tool_dir / "models" / "__init__.py").exists()
        )
        if has_models:
            modules.append(f"apik_tools.{tool.manifest.slug}.models")
    return modules


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = _config.database_url
    if db_url:
        async with RegisterTortoise(
            app=app,
            db_url=db_url,
            modules={"models": _collect_model_modules(_tools)},
            generate_schemas=_config.database_generate_schemas,
            add_exception_handlers=True,
        ):
            yield
    else:
        yield


app = FastAPI(lifespan=lifespan)


_PUBLIC_PATHS = {"/login", "/register", "/auth/github", "/auth/github/callback"}
_PUBLIC_PREFIXES = ("/static/", "/sw.js", "/manifest.json", "/favicon.ico")


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_token = request.cookies.get("session_token")
    request.state.user = auth_service.validate_session(session_token) if session_token else None
    path = request.url.path
    if not request.state.user and path not in _PUBLIC_PATHS and not any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
templates.env.cache = None

# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------
_config = get_config()
_tools: list[LoadedTool] = discover_tools(
    _config.tools_dir,
    disabled_slugs=set(_config.disabled_tools),
)
register_tools(app, _tools)
app.include_router(login_router)


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------

@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(
        PACKAGE_DIR / "static" / "sw.js",
        media_type="application/javascript",
    )


@app.get("/manifest.json", include_in_schema=False)
async def web_manifest():
    return FileResponse(
        PACKAGE_DIR / "static" / "manifest.json",
        media_type="application/manifest+json",
    )


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tools": [asdict(t.manifest) for t in _tools]},
    )


@app.exception_handler(404)
async def not_found(request: Request, _: HTTPException):
    return templates.TemplateResponse(request, "404.html", status_code=404)
