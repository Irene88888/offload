from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import UPLOADS_DIR, init_db
from .routers import export_import, options, records, stats, upload

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend" / "static"

app = FastAPI(title="磅單追蹤平台")

# StaticFiles requires the directory to exist at mount time, and init_db()
# (which also seeds the dropdown options) only runs on the startup event —
# so create the uploads dir eagerly here, before the mount below.
init_db()


app.include_router(records.router)
app.include_router(options.router)
app.include_router(stats.router)
app.include_router(upload.router)
app.include_router(export_import.router)

# Uploaded slip photos, served back for the entry-form preview and list view.
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# The no-build-step frontend. html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
