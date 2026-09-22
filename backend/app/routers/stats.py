from __future__ import annotations

from fastapi import APIRouter

from .. import crud
from ..stats import compute_by_date, compute_summary

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats():
    records = crud.list_records()
    return {
        "summary": compute_summary(records),
        "by_date": compute_by_date(records),
    }
