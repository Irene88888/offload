"""Pure-Python aggregation — replaces what used to be "ask Claude to re-tally
the whole sheet every time a row is added". Same arithmetic every time, zero
tokens, runs in milliseconds.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def effective_amount(record: dict[str, Any]) -> float | None:
    """有效金額: 切結轉帳淨額 if known, else falls back to 計價金額(未稅).
    Mirrors the coalesce rule found in the original hand-kept sheet.
    """
    net = record.get("net_transfer_amount")
    if net is not None:
        return net
    return record.get("price_amount")


def compute_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    received = sum(1 for r in records if r.get("pricing_slip_received") == "是")
    not_received = sum(1 for r in records if r.get("pricing_slip_received") == "否")
    unpaid = sum(1 for r in records if r.get("payment_status") == "未付款")
    scheduled = sum(1 for r in records if r.get("payment_status") == "已排款")
    paid = sum(1 for r in records if r.get("payment_status") == "已付款")

    by_location: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "net_weight_kg": 0.0})
    for r in records:
        loc = r.get("location") or "未填"
        by_location[loc]["count"] += 1
        by_location[loc]["net_weight_kg"] += float(r.get("net_weight") or 0)

    return {
        "total_count": total,
        "pricing_slip_not_received_count": not_received,
        "pricing_slip_received_count": received,
        "unpaid_count": unpaid,
        "scheduled_count": scheduled,
        "paid_count": paid,
        "by_location": [
            {"location": loc, "count": v["count"], "net_weight_kg": round(v["net_weight_kg"], 2)}
            for loc, v in sorted(by_location.items())
        ],
    }


def compute_by_date(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Groups by 付款排程 (payment_schedule), summing 有效金額 (net_transfer_amount
    where included_in_stats is true) and listing the owner/boat names, mirroring
    the original 依日期統計 sheet.
    """
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"amount": 0.0, "names": []})
    for r in records:
        date = r.get("payment_schedule")
        if not date:
            continue
        g = groups[date]
        amount = effective_amount(r) if r.get("included_in_stats", True) else None
        if amount:
            g["amount"] += float(amount)
        name = r.get("owner_boat")
        if name and name not in g["names"]:
            g["names"].append(name)

    return [
        {"date": date, "amount": round(v["amount"], 2), "detail": "、".join(v["names"])}
        for date, v in sorted(groups.items())
    ]
