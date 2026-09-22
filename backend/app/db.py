"""SQLite storage layer for the weighbridge-slip tracker (磅單追蹤平台).

Single-file DB, zero external services. Schema mirrors the columns of the
original Excel tracking sheet (磅單紀錄) plus two extra fields the sheet's
own 說明 tab documents but the data crammed into free-text notes instead
(傳票編號/序號, 車號), and a couple of bookkeeping fields (image, OCR text,
included_in_stats) that make the stats/export logic exact instead of manual.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "app.db"
UPLOADS_DIR = DATA_DIR / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    location                TEXT NOT NULL,          -- 卸魚地點
    unload_date             TEXT,                    -- 卸魚日期 (YYYY-MM-DD)
    slip_no                 TEXT,                    -- 傳票編號/序號
    vehicle_no              TEXT,                    -- 車號
    owner_boat              TEXT,                    -- 魚貨主/船名
    gross_weight            REAL,                    -- 總重(KG)
    tare_weight             REAL,                    -- 空重(KG)
    net_weight              REAL,                    -- 淨重(KG)
    notes                   TEXT,                    -- 備註(魚種/數量)
    pricing_slip_received   TEXT,                    -- 是否收到計價單
    pricing_slip_date       TEXT,                    -- 計價單收到日期
    payment_schedule        TEXT,                    -- 付款排程(卸魚+14天)
    price_amount            REAL,                    -- 計價金額(未稅,元)
    net_transfer_amount     REAL,                    -- 切結轉帳淨額(元)
    payment_status          TEXT,                    -- 付款狀態
    actual_payment_date     TEXT,                    -- 實際付款日
    included_in_stats       INTEGER NOT NULL DEFAULT 1, -- 0 = 金額已併入其他列，不重複計入
    image_path              TEXT,                    -- 上傳磅單照片相對路徑
    ocr_raw_text             TEXT,                    -- OCR 原始辨識文字（除錯/追溯用）
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS options (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,   -- 'location' | 'pricing_slip_received' | 'payment_status'
    value    TEXT NOT NULL,
    UNIQUE(category, value)
);

CREATE INDEX IF NOT EXISTS idx_records_location ON records(location);
CREATE INDEX IF NOT EXISTS idx_records_unload_date ON records(unload_date);
CREATE INDEX IF NOT EXISTS idx_records_payment_status ON records(payment_status);
CREATE INDEX IF NOT EXISTS idx_records_payment_schedule ON records(payment_schedule);
"""

# Seed values: union of the original workbook's dropdown lists and the values
# actually observed in real use, so nothing the user already typed is "invalid".
SEED_OPTIONS = {
    "location": ["高雄區漁會", "東港區漁會", "前鎮魚市場", "小港區漁會", "其他"],
    "pricing_slip_received": [
        "是", "否", "待收計價單", "下船東的牌", "部份廣宏/部份船東", "已由正式計價單取代",
    ],
    "payment_status": ["未付款", "已排款", "已付款", "收單"],
}


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        for category, values in SEED_OPTIONS.items():
            for value in values:
                conn.execute(
                    "INSERT OR IGNORE INTO options(category, value) VALUES (?, ?)",
                    (category, value),
                )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
