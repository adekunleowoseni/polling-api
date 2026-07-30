from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import APP_SETTINGS_COLLECTION

SETTINGS_ID = "global"

DEFAULTS: dict[str, Any] = {
    "strict_one_data_claim_per_phone": False,
    "strict_one_airtime_claim_per_phone": False,
    # INEC IReV watchdog — super-admin managed (see irev_client.py / irev_watchdog.py).
    # irev_api_base/irev_election_id only exist while IReV is live for a given
    # election; a super admin captures them from devtools and pastes them in
    # here, then flips irev_enabled on. Left blank/off, the watchdog no-ops.
    "irev_enabled": False,
    "irev_api_base": "",
    "irev_election_id": "",
    "irev_poll_interval_seconds": 300,
}


def _coerce(default: Any, value: Any) -> Any:
    if isinstance(default, bool):
        return bool(value)
    if isinstance(default, int):
        return int(value)
    return str(value)


async def get_app_settings(db: AsyncIOMotorDatabase) -> dict[str, Any]:
    """Return the global settings doc merged over defaults."""
    doc = await db[APP_SETTINGS_COLLECTION].find_one({"_id": SETTINGS_ID}) or {}
    merged = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key in doc and doc[key] is not None:
            merged[key] = _coerce(default, doc[key])
    return merged


async def update_app_settings(db: AsyncIOMotorDatabase, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial update to the known settings keys and return the result."""
    update: dict[str, Any] = {}
    for key, default in DEFAULTS.items():
        if key in patch and patch[key] is not None:
            update[key] = _coerce(default, patch[key])
    update["updated_at"] = datetime.now(timezone.utc)
    await db[APP_SETTINGS_COLLECTION].update_one(
        {"_id": SETTINGS_ID}, {"$set": update}, upsert=True
    )
    return await get_app_settings(db)
