from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import crud
from ..schemas import RecordIn, RecordOut, RecordPatch

router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("", response_model=list[RecordOut])
def list_records(
    location: str | None = None,
    pricing_slip_received: str | None = None,
    payment_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = Query(None, description="搜尋魚貨主/船名/備註/車號/傳票編號"),
):
    return crud.list_records({
        "location": location,
        "pricing_slip_received": pricing_slip_received,
        "payment_status": payment_status,
        "date_from": date_from,
        "date_to": date_to,
        "q": q,
    })


@router.get("/{record_id}", response_model=RecordOut)
def get_record(record_id: int):
    rec = crud.get_record(record_id)
    if not rec:
        raise HTTPException(404, "找不到這筆紀錄")
    return rec


@router.post("", response_model=RecordOut)
def create_record(payload: RecordIn):
    data = payload.model_dump()
    image_id = data.pop("image_id", None)
    if image_id:
        data["image_path"] = image_id
    for cat in ("location", "pricing_slip_received", "payment_status"):
        if data.get(cat):
            crud.add_option(cat, data[cat])
    return crud.create_record(data)


@router.patch("/{record_id}", response_model=RecordOut)
def patch_record(record_id: int, payload: RecordPatch):
    rec = crud.update_record(record_id, payload.model_dump(exclude_unset=True))
    if not rec:
        raise HTTPException(404, "找不到這筆紀錄")
    return rec


@router.delete("/{record_id}")
def delete_record(record_id: int):
    ok = crud.delete_record(record_id)
    if not ok:
        raise HTTPException(404, "找不到這筆紀錄")
    return {"deleted": True}
