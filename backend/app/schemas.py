"""Pydantic request/response models."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RecordIn(BaseModel):
    location: str
    unload_date: Optional[str] = None
    slip_no: Optional[str] = None
    vehicle_no: Optional[str] = None
    owner_boat: Optional[str] = None
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    net_weight: Optional[float] = None
    notes: Optional[str] = None
    pricing_slip_received: Optional[str] = None
    pricing_slip_date: Optional[str] = None
    payment_schedule: Optional[str] = None
    price_amount: Optional[float] = None
    net_transfer_amount: Optional[float] = None
    payment_status: Optional[str] = None
    actual_payment_date: Optional[str] = None
    included_in_stats: bool = True
    image_id: Optional[str] = None  # references a file already saved via /api/ocr or /api/upload-image
    ocr_raw_text: Optional[str] = None


class RecordPatch(BaseModel):
    location: Optional[str] = None
    unload_date: Optional[str] = None
    slip_no: Optional[str] = None
    vehicle_no: Optional[str] = None
    owner_boat: Optional[str] = None
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    net_weight: Optional[float] = None
    notes: Optional[str] = None
    pricing_slip_received: Optional[str] = None
    pricing_slip_date: Optional[str] = None
    payment_schedule: Optional[str] = None
    price_amount: Optional[float] = None
    net_transfer_amount: Optional[float] = None
    payment_status: Optional[str] = None
    actual_payment_date: Optional[str] = None
    included_in_stats: Optional[bool] = None


class RecordOut(RecordIn):
    id: int
    image_path: Optional[str] = None
    created_at: str
    updated_at: str


class OptionIn(BaseModel):
    category: str = Field(pattern="^(location|pricing_slip_received|payment_status)$")
    value: str


class OcrResult(BaseModel):
    image_id: str
    image_url: str
    raw_text: str
    guesses: dict
    ocr_available: bool
    ocr_message: Optional[str] = None
