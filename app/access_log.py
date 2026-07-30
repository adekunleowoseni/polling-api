from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import ACCESS_LOG_COLLECTION


async def log_access(
    db: AsyncIOMotorDatabase,
    *,
    entity_type: str,
    entity_id: str,
    actor_type: str,
    actor_id: str,
    actor_name: str,
    action: str,
    ip: str | None,
) -> None:
    """Record a view/edit of a result sheet or witness statement.

    This is the audit trail courts and opposing counsel probe: not just
    "was it captured correctly" but "could it have been swapped between
    polling day and trial." Best-effort — a logging failure must never
    block the underlying request.
    """
    try:
        await db[ACCESS_LOG_COLLECTION].insert_one(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "action": action,
                "ip": ip,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        pass


async def list_access_log(db: AsyncIOMotorDatabase, entity_id: str) -> list[dict[str, Any]]:
    cursor = db[ACCESS_LOG_COLLECTION].find({"entity_id": entity_id}).sort("created_at", 1)
    return await cursor.to_list(length=10000)
