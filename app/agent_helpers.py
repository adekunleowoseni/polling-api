from __future__ import annotations

from datetime import timezone
from typing import Any

from .geo_data import OGUN_LGAS
from .osun_geo_data import OSUN_LGAS
from .schemas import AgentOut


def state_for_lga(lga: str | None) -> str | None:
    """Map an agent/unit LGA to Ogun State or Osun State."""
    if not lga:
        return None
    name = lga.strip()
    if name in OGUN_LGAS:
        return "Ogun State"
    if name in OSUN_LGAS:
        return "Osun State"
    return None


def _as_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def agent_doc_to_out(doc: dict[str, Any]) -> AgentOut:
    lga = doc.get("lga")
    return AgentOut(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        lga=lga,
        ward=doc.get("ward"),
        state=state_for_lga(lga) or doc.get("state"),
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
        accreditation_status=doc.get("accreditation_status") or "none",
    )
