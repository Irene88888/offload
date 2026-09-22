from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import crud
from ..db import UPLOADS_DIR
from ..ocr import run_ocr
from ..schemas import OcrResult

router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tiff"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/ocr", response_model=OcrResult)
async def ocr_image(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支援的檔案類型：{suffix or '未知'}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "檔案過大，請壓縮後再上傳（上限 20MB）")

    image_id = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS_DIR / image_id
    dest.write_bytes(content)

    known_locations = crud.list_options().get("location", [])
    raw_text, guesses, ocr_available, message = run_ocr(str(dest), known_locations)

    return OcrResult(
        image_id=image_id,
        image_url=f"/uploads/{image_id}",
        raw_text=raw_text,
        guesses=guesses,
        ocr_available=ocr_available,
        ocr_message=message,
    )
