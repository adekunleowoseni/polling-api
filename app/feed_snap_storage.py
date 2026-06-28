from __future__ import annotations

from pathlib import Path

SNAPS_DIR = Path(__file__).resolve().parent.parent / "storage" / "snaps"


def ensure_snaps_dir() -> Path:
    SNAPS_DIR.mkdir(parents=True, exist_ok=True)
    return SNAPS_DIR


def snap_file_path(snap_id: str) -> Path:
    return SNAPS_DIR / f"{snap_id}.jpg"
