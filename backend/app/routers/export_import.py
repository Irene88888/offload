from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from .. import crud
from ..xlsx_io import export_workbook, parse_workbook

router = APIRouter(prefix="/api", tags=["export-import"])


@router.get("/export.xlsx")
def export_xlsx():
    records = crud.list_records()
    options = crud.list_options()
    content = export_workbook(records, options)
    filename = f"磅單追蹤表_{datetime.now():%Y%m%d_%H%M}.xlsx"
    encoded_filename = quote(filename)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


@router.post("/import-xlsx")
async def import_xlsx(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "請上傳 .xlsx 檔案")
    content = await file.read()
    try:
        records = parse_workbook(content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if not records:
        raise HTTPException(400, "檔案中沒有可匯入的資料列")

    crud.ensure_options_from_records(records)
    count = crud.bulk_insert(records)
    return {"imported": count}
