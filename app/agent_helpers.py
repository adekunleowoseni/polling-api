from __future__ import annotations

from datetime import timezone
from typing import Any

from .schemas import AgentOut


def _as_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def agent_doc_to_out(doc: dict[str, Any]) -> AgentOut:
    return AgentOut(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        lga=doc.get("lga"),
        ward=doc.get("ward"),
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
    )
