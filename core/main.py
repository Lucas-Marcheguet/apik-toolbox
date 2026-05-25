from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_config
from .services.tool_manager import LoadedTool, discover_tools, register_tools

PACKAGE_DIR = Path(__file__).parent

app = FastAPI()

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
