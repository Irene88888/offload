"""Excel <-> DB bridge.

export_workbook(): turns the current DB into a workbook shaped like the
original template (說明 / 磅單紀錄 / 統計摘要 / 依日期統計), so anything
downstream that expects that file still works.

parse_workbook(): reads an existing tracking-sheet .xlsx (the original
template, or a previous export) back into row dicts ready for DB insertion —
used to migrate the sheet the user already has.
"""
from __future__ import annotations

import datetime as dt
import io
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from . import stats as stats_mod

EXPORT_COLUMNS: list[tuple[str, str]] = [
    ("location", "卸魚地點"),
    ("unload_date", "卸魚日期"),
    ("slip_no", "傳票編號/序號"),
    ("vehicle_no", "車號"),
    ("owner_boat", "魚貨主/船名"),
    ("gross_weight", "總重(KG)"),
    ("tare_weight", "空重(KG)"),
    ("net_weight", "淨重(KG)"),
    ("notes", "備註(魚種/數量)"),
    ("pricing_slip_received", "是否收到計價單"),
    ("pricing_slip_date", "計價單收到日期"),
    ("payment_schedule", "付款排程(卸魚+14天)"),
    ("price_amount", "計價金額(未稅,元)"),
    ("net_transfer_amount", "切結轉帳淨額(元)"),
    ("payment_status", "付款狀態"),
    ("actual_payment_date", "實際付款日"),
    ("effective_amount", "有效金額(供依日期統計加總用)"),
    ("included_in_stats", "是否計入統計加總"),
]

# Header text -> DB field, covering both our own export and the original
# hand-built template (which lacked slip_no/vehicle_no/included_in_stats).
_HEADER_TO_FIELD = {label: field for field, label in EXPORT_COLUMNS}
_HEADER_TO_FIELD["有效金額(供依日期統計加總用)"] = "effective_amount"

_DATE_FIELDS = {"unload_date", "pricing_slip_date", "payment_schedule", "actual_payment_date"}
_NUMBER_FIELDS = {"gross_weight", "tare_weight", "net_weight", "price_amount", "net_transfer_amount"}

USAGE_TEXT = [
    "磅單追蹤表 使用說明（平台自動匯出版）",
    "",
    "本檔案由「磅單追蹤平台」自動產生，資料來源為平台資料庫，請勿手動編輯後再匯入，",
    "以免與平台上的紀錄不同步。若需修改資料，請回到平台的「紀錄列表」頁編輯，",
    "再重新匯出即可。",
    "",
    "1. 每次收到魚市場秤量傳票／地磅單，請在平台的「新增紀錄」頁上傳照片或直接手動輸入。",
    "2. 平台會嘗試用本機 OCR 辨識照片文字並猜測欄位，但請務必核對後再送出，OCR 不保證正確。",
    "3.「是否收到計價單」與「付款狀態」欄位為下拉選單，方便篩選追蹤進度。",
    "4. 建議每週在平台檢查一次「是否收到計價單」為「否」的列，主動向承銷人／漁會確認。",
    "5. 若某一列的金額已併入同一船隻其他列彙總（避免重複計算），可在平台將該列標記",
    "  「不計入統計」，匯出時「有效金額」欄會自動留空，並在「是否計入統計加總」欄標示「否」。",
    "",
    "欄位說明",
]

FIELD_DESCRIPTIONS = [
    ("卸魚地點", "傳票單頭寫的漁會／魚市場名稱，例如：高雄區漁會、東港區漁會"),
    ("卸魚日期", "傳票上的日期（民國年已自動換算為西元年）"),
    ("傳票編號/序號", "傳票右上角或右下角的編號，例如 N023637 或地磅單序號"),
    ("車號", "傳票上的車牌號碼"),
    ("魚貨主/船名", "傳票上的魚貨主欄位"),
    ("總重/空重/淨重(KG)", "傳票上過磅的三個重量數字"),
    ("備註(魚種/數量)", "傳票備註欄，通常寫魚種與件數，如：大丁、中丁、大石"),
    ("是否收到計價單", "是否已收到魚市場開立的計價單（結算單）"),
    ("計價單收到日期", "實際收到計價單的日期"),
    ("付款排程", "預計付款/請款日期"),
    ("付款狀態", "未付款／已排款／已付款"),
    ("實際付款日", "款項實際入帳日期"),
    ("有效金額", "供依日期統計加總使用；標記「不計入統計」的列會自動留空，避免重複加總"),
]


def _cell_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    return text or None


def _cell_to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def export_workbook(records: list[dict[str, Any]], options: dict[str, list[str]]) -> bytes:
    wb = openpyxl.Workbook()

    # --- 說明 -----------------------------------------------------------
    ws = wb.active
    ws.title = "說明"
    ws.column_dimensions["B"].width = 60
    ws.column_dimensions["C"].width = 60
    row = 2
    ws.cell(row=row, column=2, value=USAGE_TEXT[0]).font = Font(bold=True, size=14)
    row += 2
    for line in USAGE_TEXT[1:]:
        ws.cell(row=row, column=2, value=line)
        row += 1
    row += 1
    for label, desc in FIELD_DESCRIPTIONS:
        ws.cell(row=row, column=2, value=label).font = Font(bold=True)
        ws.cell(row=row, column=3, value=desc)
        row += 1

    # --- 磅單紀錄 ---------------------------------------------------------
    ws2 = wb.create_sheet("磅單紀錄")
    headers = [label for _, label in EXPORT_COLUMNS]
    ws2.append(headers)
    for col_idx in range(1, len(headers) + 1):
        c = ws2.cell(row=1, column=col_idx)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2E7D32")
        c.alignment = Alignment(horizontal="center")

    for r in records:
        effective = stats_mod.effective_amount(r) if r.get("included_in_stats", True) else None
        row_values = []
        for field, _ in EXPORT_COLUMNS:
            if field == "effective_amount":
                row_values.append(effective)
            elif field == "included_in_stats":
                row_values.append("是" if r.get("included_in_stats", True) else "否")
            else:
                row_values.append(r.get(field))
        ws2.append(row_values)

    last_row = max(ws2.max_row, 200)
    dv_specs = [
        ("location", options.get("location", []), "A"),
        ("pricing_slip_received", options.get("pricing_slip_received", []), "J"),
        ("payment_status", options.get("payment_status", []), "O"),
    ]
    for _, values, col_letter in dv_specs:
        # Excel's inline data-validation list can't contain a comma inside an
        # option (no escaping mechanism), so values with one are dropped from
        # the dropdown — they stay valid, stored data, just not re-selectable.
        values = [v for v in values if "," not in v and "，" not in v]
        if not values:
            continue
        formula = '"' + ",".join(values) + '"'
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        ws2.add_data_validation(dv)
        dv.add(f"{col_letter}2:{col_letter}{last_row}")

    for col_idx, (_, label) in enumerate(EXPORT_COLUMNS, start=1):
        ws2.column_dimensions[ws2.cell(row=1, column=col_idx).column_letter].width = max(12, len(label) + 2)

    # --- 統計摘要 ---------------------------------------------------------
    ws3 = wb.create_sheet("統計摘要")
    ws3.column_dimensions["B"].width = 30
    ws3.column_dimensions["C"].width = 20
    ws3.cell(row=2, column=2, value="磅單追蹤 統計摘要").font = Font(bold=True, size=14)
    ws3.cell(row=4, column=2, value="統計項目").font = Font(bold=True)
    ws3.cell(row=4, column=3, value="數值").font = Font(bold=True)

    summary = stats_mod.compute_summary(records)
    lines = [
        ("總筆數", summary["total_count"]),
        ("尚未收到計價單筆數", summary["pricing_slip_not_received_count"]),
        ("已收到計價單筆數", summary["pricing_slip_received_count"]),
        ("未付款筆數", summary["unpaid_count"]),
        ("已排款筆數", summary["scheduled_count"]),
        ("已付款筆數", summary["paid_count"]),
    ]
    row = 5
    for label, value in lines:
        ws3.cell(row=row, column=2, value=label)
        ws3.cell(row=row, column=3, value=value)
        row += 1
    for loc in summary["by_location"]:
        ws3.cell(row=row, column=2, value=f"{loc['location']} 卸魚筆數")
        ws3.cell(row=row, column=3, value=loc["count"])
        row += 1
    for loc in summary["by_location"]:
        ws3.cell(row=row, column=2, value=f"{loc['location']} 淨重合計(KG)")
        ws3.cell(row=row, column=3, value=loc["net_weight_kg"])
        row += 1

    # --- 依日期統計 -------------------------------------------------------
    ws4 = wb.create_sheet("依日期統計")
    ws4.column_dimensions["B"].width = 14
    ws4.column_dimensions["C"].width = 14
    ws4.column_dimensions["D"].width = 60
    ws4.cell(row=1, column=2, value="依付款排程日期統計").font = Font(bold=True, size=13)
    ws4.cell(row=2, column=2, value="日期").font = Font(bold=True)
    ws4.cell(row=2, column=3, value="金額").font = Font(bold=True)
    ws4.cell(row=2, column=4, value="明細").font = Font(bold=True)
    row = 3
    for g in stats_mod.compute_by_date(records):
        ws4.cell(row=row, column=2, value=g["date"])
        ws4.cell(row=row, column=3, value=g["amount"] or None)
        ws4.cell(row=row, column=4, value=g["detail"])
        row += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_workbook(file_bytes: bytes) -> list[dict[str, Any]]:
    """Parses a tracking-sheet .xlsx (original template or our own export)
    and returns a list of record dicts, ready for bulk insert.
    Looks for a sheet named 磅單紀錄; falls back to the first sheet with a
    recognizable header row.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb["磅單紀錄"] if "磅單紀錄" in wb.sheetnames else wb.worksheets[0]

    header_row = None
    field_by_col: dict[int, str] = {}
    for row in ws.iter_rows(min_row=1, max_row=min(5, ws.max_row)):
        mapping = {}
        for cell in row:
            if cell.value is None:
                continue
            field = _HEADER_TO_FIELD.get(str(cell.value).strip())
            if field:
                mapping[cell.column] = field
        if len(mapping) >= 5:
            header_row = row[0].row
            field_by_col = mapping
            break

    if header_row is None:
        raise ValueError("找不到可辨識的欄位標題列，請確認上傳的是磅單追蹤表格式的 Excel 檔。")

    records: list[dict[str, Any]] = []
    for row in ws.iter_rows(min_row=header_row + 1):
        if all(c.value is None for c in row):
            continue
        rec: dict[str, Any] = {}
        for cell in row:
            field = field_by_col.get(cell.column)
            if not field:
                continue
            if field == "effective_amount":
                rec["_effective_amount"] = _cell_to_number(cell.value)
                continue
            if field == "included_in_stats":
                rec["included_in_stats"] = str(cell.value).strip() != "否" if cell.value is not None else True
                continue
            if field in _DATE_FIELDS:
                rec[field] = _cell_to_str(cell.value)
            elif field in _NUMBER_FIELDS:
                rec[field] = _cell_to_number(cell.value)
            else:
                rec[field] = _cell_to_str(cell.value)
        if not rec.get("location"):
            continue
        if "included_in_stats" not in rec:
            eff = rec.pop("_effective_amount", None)
            coalesce = stats_mod.effective_amount(rec)
            # No amount known yet either way -> nothing to lose by including it.
            # An amount known but 有效金額 was left blank -> bookkeeper intentionally excluded it.
            rec["included_in_stats"] = True if coalesce is None else eff is not None
        else:
            rec.pop("_effective_amount", None)
        records.append(rec)

    return records
