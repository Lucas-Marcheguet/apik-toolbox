from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

PACKAGE_DIR = Path(__file__).parent

app = FastAPI()

app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
templates.env.cache = None


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
