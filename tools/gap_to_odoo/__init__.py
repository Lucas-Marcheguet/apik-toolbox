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

from .services.gap_to_odoo import gap_to_odoo, EXCEL_COLUMN_NAMES

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
    return templates.TemplateResponse(request, "index.html", {"request": request})


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb"}


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        logger.warning(f"Rejected file '{file.filename}' with unsupported extension '{suffix}'")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
    contents = await file.read()
    try:
        sheets = pd.read_excel(io.BytesIO(contents), sheet_name=None, header=1)
        # Fuse all worksheets into one DataFrame (if multiple sheets exist)
        # Get worksheet only if you can find EXCEL_COLUMN_NAMES in it, otherwise skip
        # Log all sheet.columns for debugging
        for sheet_name, sheet in sheets.items():
            if sheet is not None and not sheet.empty:
                logger.info(f"Sheet '{sheet_name}' columns: {list(sheet.columns)}")
        df = pd.concat(
            [sheet for sheet in sheets.values() if sheet is not None and not sheet.empty and set(EXCEL_COLUMN_NAMES).issubset(set(sheet.columns))],
            ignore_index=True
        )
        logger.info(f"Loaded {len(df)} rows from file '{file.filename}' after concatenating sheets")    
        df = gap_to_odoo(df)
    except Exception as exc:
        logger.error(f"Error processing file '{file.filename}': {exc}")
        raise HTTPException(status_code=400, detail=f"Error processing file: {exc}")
    
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    logger.info(f"Successfully processed file '{file.filename}' with {len(df)} rows and {len(df.columns)} columns")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=converted_{file.filename}"},
    )
