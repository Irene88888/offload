from __future__ import annotations

from fastapi import APIRouter

from .. import crud
from ..schemas import OptionIn

router = APIRouter(prefix="/api/options", tags=["options"])


@router.get("")
def get_options():
    return crud.list_options()


@router.post("")
def add_option(payload: OptionIn):
    crud.add_option(payload.category, payload.value)
    return crud.list_options()
