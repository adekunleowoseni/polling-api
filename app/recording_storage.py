from __future__ import annotations

from pathlib import Path

RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "storage" / "recordings"


def ensure_recordings_dir() -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return RECORDINGS_DIR


def recording_file_path(recording_id: str) -> Path:
    return RECORDINGS_DIR / f"{recording_id}.mp4"
