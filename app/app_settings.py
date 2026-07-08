from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import APP_SETTINGS_COLLECTION

SETTINGS_ID = "global"

DEFAULTS: dict[str, Any] = {
    "strict_one_data_claim_per_phone": False,
    "strict_one_airtime_claim_per_phone": False,
}


async def get_app_settings(db: AsyncIOMotorDatabase) -> dict[str, Any]:
    """Return the global settings doc merged over defaults."""
    doc = await db[APP_SETTINGS_COLLECTION].find_one({"_id": SETTINGS_ID}) or {}
    merged = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in doc:
            merged[key] = bool(doc[key])
    return merged


async def update_app_settings(db: AsyncIOMotorDatabase, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial update to the known settings keys and return the result."""
    update: dict[str, Any] = {}
    for key in DEFAULTS:
        if key in patch and patch[key] is not None:
            update[key] = bool(patch[key])
    update["updated_at"] = datetime.now(timezone.utc)
    await db[APP_SETTINGS_COLLECTION].update_one(
        {"_id": SETTINGS_ID}, {"$set": update}, upsert=True
    )
    return await get_app_settings(db)
