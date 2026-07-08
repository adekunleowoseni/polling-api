from __future__ import annotations

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import AIRTIME_PLANS_COLLECTION
from .vtpass_client import DEFAULT_AIRTIME_AMOUNTS

logger = logging.getLogger(__name__)


async def ensure_airtime_defaults(db: AsyncIOMotorDatabase) -> None:
    """Seed the default airtime denominations once, if none exist yet.

    Admins can freely edit/enable/disable amounts afterwards; this only runs
    when the collection is empty so it never overwrites admin changes.
    """
    existing = await db[AIRTIME_PLANS_COLLECTION].count_documents({})
    if existing:
        return
    now = datetime.now(timezone.utc)
    docs = [
        {"amount": float(amount), "enabled": True, "updated_at": now}
        for amount in DEFAULT_AIRTIME_AMOUNTS
    ]
    if docs:
        await db[AIRTIME_PLANS_COLLECTION].insert_many(docs)
        logger.info("Seeded %d default airtime denominations", len(docs))
