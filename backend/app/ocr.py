"""Local OCR + light heuristics for 磅單 (weighbridge/pricing slip) photos.

No network calls, no LLM calls — this is the whole point of the platform:
every upload costs a few hundred ms of CPU, not tokens. Accuracy on messy
handwriting will often be poor, so this module only ever produces
*suggestions*; the human always reviews/corrects them in the entry form
before anything is saved.
"""
from __future__ import annotations

import re
from typing import Optional

try:
    import pytesseract
    from PIL import Image, ImageOps

    _TESSERACT_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - import-time environment issue
    pytesseract = None  # type: ignore
    Image = None  # type: ignore
    ImageOps = None  # type: ignore
    _TESSERACT_IMPORT_ERROR = str(exc)

# Traditional Chinese + English. Falls back to English-only if the
# chi_tra language pack isn't installed on this machine.
TESSERACT_LANGS = "chi_tra+eng"

_WEIGHT_LABELS = {
    "gross_weight": ["總重", "毛重"],
    "tare_weight": ["空重", "皮重"],
    "net_weight": ["淨重", "净重"],
}

_NUMBER_RE = r"[\d,，]{2,7}(?:\.\d+)?"


def _clean_number(raw: str) -> Optional[float]:
    raw = raw.replace(",", "").replace("，", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _roc_to_western_date(y: int, m: int, d: int) -> Optional[str]:
    if y < 200:  # Republic-of-China calendar, e.g. 115/08/27 -> 2026-08-27
        y += 1911
    try:
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        return None


def _guess_weights(text: str) -> dict:
    guesses: dict = {}
    for field, labels in _WEIGHT_LABELS.items():
        for label in labels:
            m = re.search(rf"{label}[^\d]{{0,4}}({_NUMBER_RE})", text)
            if m:
                val = _clean_number(m.group(1))
                if val is not None:
                    guesses[field] = val
                    break
    return guesses


def _guess_date(text: str) -> Optional[str]:
    # ISO-ish: 2026-08-27 / 2026/08/27
    m = re.search(r"(20\d{2})[./\-年](\d{1,2})[./\-月](\d{1,2})", text)
    if m:
        return _roc_to_western_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # ROC: 115/08/27 or 115.08.27
    m = re.search(r"(?<!\d)(1[0-2]\d)[./\-](\d{1,2})[./\-](\d{1,2})(?!\d)", text)
    if m:
        return _roc_to_western_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _guess_vehicle_no(text: str) -> Optional[str]:
    m = re.search(r"車號[:：]?\s*([A-Za-z0-9\-]{4,8})", text)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b([A-Za-z]{1,3}-\d{2,4})\b", text)
    if m:
        return m.group(1).upper()
    return None


def _guess_slip_no(text: str) -> Optional[str]:
    m = re.search(r"(?:傳票編號|序號|NO\.?|No\.?)[:：#]?\s*([A-Za-z0-9]{3,10})", text, re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b([A-Z]\d{5,7})\b", text)
    if m:
        return m.group(1)
    return None


def _guess_location(text: str, known_locations: list[str]) -> Optional[str]:
    for loc in known_locations:
        if loc and loc in text:
            return loc
    return None


def guess_fields(raw_text: str, known_locations: list[str] | None = None) -> dict:
    text = raw_text or ""
    guesses = _guess_weights(text)
    date = _guess_date(text)
    if date:
        guesses["unload_date"] = date
    vehicle_no = _guess_vehicle_no(text)
    if vehicle_no:
        guesses["vehicle_no"] = vehicle_no
    slip_no = _guess_slip_no(text)
    if slip_no:
        guesses["slip_no"] = slip_no
    location = _guess_location(text, known_locations or [])
    if location:
        guesses["location"] = location

    weights = {k: guesses[k] for k in ("gross_weight", "tare_weight", "net_weight") if k in guesses}
    if "net_weight" not in weights and "gross_weight" in weights and "tare_weight" in weights:
        computed = weights["gross_weight"] - weights["tare_weight"]
        if computed > 0:
            guesses["net_weight"] = round(computed, 2)

    return guesses


def run_ocr(image_path: str, known_locations: list[str] | None = None) -> tuple[str, dict, bool, Optional[str]]:
    """Returns (raw_text, guesses, ocr_available, message)."""
    if pytesseract is None:
        return "", {}, False, (
            "本機未安裝 OCR 套件 (pytesseract/Pillow)，請直接手動填寫下方欄位。"
            f" 詳細錯誤：{_TESSERACT_IMPORT_ERROR}"
        )
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        if img.mode != "L":
            img = img.convert("L")
        raw_text = pytesseract.image_to_string(img, lang=TESSERACT_LANGS)
    except pytesseract.TesseractNotFoundError:
        return "", {}, False, (
            "本機未安裝 tesseract 執行檔，請參考 README 安裝，或直接手動填寫下方欄位。"
        )
    except Exception as exc:  # noqa: BLE001 - surface any OCR failure without crashing the upload
        return "", {}, False, f"OCR 辨識失敗，請直接手動填寫下方欄位。錯誤：{exc}"

    guesses = guess_fields(raw_text, known_locations)
    return raw_text, guesses, True, None
