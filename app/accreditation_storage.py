from __future__ import annotations

from pathlib import Path

ACCREDITATION_DIR = Path(__file__).resolve().parent.parent / "storage" / "accreditation"


def ensure_accreditation_dir() -> Path:
    ACCREDITATION_DIR.mkdir(parents=True, exist_ok=True)
    return ACCREDITATION_DIR


def accreditation_file_path(agent_id: str, ext: str) -> Path:
    return ACCREDITATION_DIR / f"{agent_id}.{ext}"
