"""
GAP to Odoo tool.

Exposes a single `router` (APIRouter) that the toolbox mounts at
  GET /tools/gap_to_odoo/

Upload an Excel file, edit its contents in-browser using pandas,
then export it back as an xlsx file.
"""
import logging
import io
import json
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

from .services.gap_to_odoo import gap_to_odoo

TOOL_DIR = Path(__file__).parent

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(TOOL_DIR))

router = APIRouter()
# api_router = APIRouter(prefix="/api")
# router.include_router(api_router)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@router.get("/")
async def index(request: Request):
    logger.info("Rendering index page")
    return templates.TemplateResponse(request, "index.html", {})


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb"}


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse(
            request, "views/editor.html",
            {"error": "Only Excel files (.xlsx, .xls, .xlsm, .xlsb) are supported."},
        )
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
        df = gap_to_odoo(df)
    except Exception as exc:
        return templates.TemplateResponse(
            request, "views/editor.html",
            {"error": f"Could not parse file: {exc}"},
        )
    
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    logger.info(f"Successfully processed file '{file.filename}' with {len(df)} rows and {len(df.columns)} columns")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=converted_{file.filename}"},
    )


@router.post("/export")
async def export(
    columns_json: str = Form(...),
    rows_json: str = Form(...),
    filename: str = Form("export.xlsx"),
):
    try:
        columns = json.loads(columns_json)
        rows = json.loads(rows_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {exc}") from exc

    df = pd.DataFrame(rows, columns=columns)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    safe_stem = "".join(c if c.isalnum() or c in "-_." else "_" for c in Path(filename).stem) or "export"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=edited_{safe_stem}.xlsx"},
    )
