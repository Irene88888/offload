"""Thin DB access layer shared by all routers."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from .db import get_conn

RECORD_FIELDS = [
    "location", "unload_date", "slip_no", "vehicle_no", "owner_boat",
    "gross_weight", "tare_weight", "net_weight", "notes",
    "pricing_slip_received", "pricing_slip_date", "payment_schedule",
    "price_amount", "net_transfer_amount", "payment_status",
    "actual_payment_date", "included_in_stats", "image_path", "ocr_raw_text",
]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["included_in_stats"] = bool(d.get("included_in_stats", 1))
    return d


def list_records(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    filters = filters or {}
    clauses, params = [], []
    if v := filters.get("location"):
        clauses.append("location = ?")
        params.append(v)
    if v := filters.get("pricing_slip_received"):
        clauses.append("pricing_slip_received = ?")
        params.append(v)
    if v := filters.get("payment_status"):
        clauses.append("payment_status = ?")
        params.append(v)
    if v := filters.get("date_from"):
        clauses.append("unload_date >= ?")
        params.append(v)
    if v := filters.get("date_to"):
        clauses.append("unload_date <= ?")
        params.append(v)
    if v := filters.get("q"):
        clauses.append("(owner_boat LIKE ? OR notes LIKE ? OR slip_no LIKE ? OR vehicle_no LIKE ?)")
        like = f"%{v}%"
        params.extend([like, like, like, like])

    sql = "SELECT * FROM records"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY unload_date DESC, id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_record(record_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    return _row_to_dict(row) if row else None


def create_record(data: dict[str, Any]) -> dict[str, Any]:
    values = {f: data.get(f) for f in RECORD_FIELDS}
    values["included_in_stats"] = 1 if data.get("included_in_stats", True) else 0
    cols = ", ".join(values.keys())
    placeholders = ", ".join("?" for _ in values)
    with get_conn() as conn:
        cur = conn.execute(f"INSERT INTO records ({cols}) VALUES ({placeholders})", list(values.values()))
        conn.commit()
        new_id = cur.lastrowid
    return get_record(new_id)  # type: ignore[return-value]


def update_record(record_id: int, patch: dict[str, Any]) -> dict[str, Any] | None:
    patch = {k: v for k, v in patch.items() if k in RECORD_FIELDS + ["included_in_stats"] and v is not None}
    if not patch:
        return get_record(record_id)
    if "included_in_stats" in patch:
        patch["included_in_stats"] = 1 if patch["included_in_stats"] else 0
    patch["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    set_clause = ", ".join(f"{k} = ?" for k in patch)
    with get_conn() as conn:
        conn.execute(f"UPDATE records SET {set_clause} WHERE id = ?", [*patch.values(), record_id])
        conn.commit()
    return get_record(record_id)


def delete_record(record_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        return cur.rowcount > 0


def bulk_insert(records: list[dict[str, Any]]) -> int:
    count = 0
    with get_conn() as conn:
        for data in records:
            values = {f: data.get(f) for f in RECORD_FIELDS if f not in ("image_path", "ocr_raw_text")}
            values["included_in_stats"] = 1 if data.get("included_in_stats", True) else 0
            cols = ", ".join(values.keys())
            placeholders = ", ".join("?" for _ in values)
            conn.execute(f"INSERT INTO records ({cols}) VALUES ({placeholders})", list(values.values()))
            count += 1
        conn.commit()
    return count


def list_options() -> dict[str, list[str]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT category, value FROM options ORDER BY category, id").fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["category"], []).append(row["value"])
    return result


def add_option(category: str, value: str) -> None:
    value = value.strip()
    if not value:
        return
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO options(category, value) VALUES (?, ?)",
            (category, value),
        )
        conn.commit()


def ensure_options_from_records(records: list[dict[str, Any]]) -> None:
    """Auto-registers any location/status values found on import so the
    dropdowns stay a superset of whatever is actually in the data."""
    for category in ("location", "pricing_slip_received", "payment_status"):
        for rec in records:
            v = rec.get(category)
            if v:
                add_option(category, v)
