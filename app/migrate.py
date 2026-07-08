"""Ensure indexes and collections exist in the configured MongoDB database."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    ADMINS_COLLECTION,
    AGENTS_COLLECTION,
    DATA_CREDITS_COLLECTION,
    DATA_PLANS_COLLECTION,
    DETECTED_FACES_COLLECTION,
    FEED_RECORDINGS_COLLECTION,
    FEED_SNAPS_COLLECTION,
    POLLING_UNITS_COLLECTION,
    REGISTRATIONS_COLLECTION,
)
from .settings import settings


async def ensure_schema(db: AsyncIOMotorDatabase) -> None:
    await db[REGISTRATIONS_COLLECTION].create_index("created_at")
    await db[POLLING_UNITS_COLLECTION].create_index("code", unique=True)
    await db[POLLING_UNITS_COLLECTION].create_index("agent_id")
    await db[AGENTS_COLLECTION].create_index("email", unique=True)
    await db[AGENTS_COLLECTION].create_index("api_token", unique=True)
    await db[AGENTS_COLLECTION].create_index([("lga", 1), ("ward", 1)])
    await db[DETECTED_FACES_COLLECTION].create_index(
        [("polling_unit_id", 1), ("first_seen_at", -1)]
    )
    await db[FEED_SNAPS_COLLECTION].create_index([("lga", 1), ("ward", 1), ("created_at", -1)])
    await db[FEED_SNAPS_COLLECTION].create_index([("polling_unit_id", 1), ("created_at", -1)])
    await db[FEED_RECORDINGS_COLLECTION].create_index([("lga", 1), ("ward", 1), ("started_at", -1)])
    await db[FEED_RECORDINGS_COLLECTION].create_index([("code", 1), ("started_at", -1)])
    await db[FEED_RECORDINGS_COLLECTION].create_index([("polling_unit_id", 1), ("started_at", -1)])
    await db[FEED_RECORDINGS_COLLECTION].create_index("status")
    await db[ADMINS_COLLECTION].create_index("email", unique=True)
    await db[ADMINS_COLLECTION].create_index("api_token", unique=True)
    await db[DATA_PLANS_COLLECTION].create_index(
        [("network", 1), ("variation_code", 1)],
        unique=True,
    )
    await db[DATA_CREDITS_COLLECTION].create_index("agent_id")
    await db[DATA_CREDITS_COLLECTION].create_index("request_id", unique=True)
    await db[DATA_CREDITS_COLLECTION].create_index([("created_at", -1)])


async def run_migration() -> str:
    from .database import get_database

    db = get_database()
    await ensure_schema(db)
    return settings.mongodb_db_name


if __name__ == "__main__":
    import asyncio

    name = asyncio.run(run_migration())
    print(f"Schema ready in database: {name}")
