from __future__ import annotations

from pathlib import Path

RESULT_SHEETS_DIR = Path(__file__).resolve().parent.parent / "storage" / "result_sheets"


def ensure_result_sheets_dir() -> Path:
    RESULT_SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULT_SHEETS_DIR


def result_sheet_file_path(sheet_id: str) -> Path:
    return RESULT_SHEETS_DIR / f"{sheet_id}.jpg"
