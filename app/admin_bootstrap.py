"""Ensure at least one super admin exists from environment settings."""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from .auth import hash_password, new_api_token
from .models import ADMINS_COLLECTION
from .settings import settings


async def ensure_super_admin(db: AsyncIOMotorDatabase) -> None:
    email = settings.super_admin_email.lower().strip()
    if not email or not settings.super_admin_password:
        return

    existing = await db[ADMINS_COLLECTION].find_one({"email": email})
    if existing:
        return

    now = datetime.now(timezone.utc)
    await db[ADMINS_COLLECTION].insert_one(
        {
            "name": "Super Admin",
            "email": email,
            "password_hash": hash_password(settings.super_admin_password),
            "api_token": new_api_token(),
            "role": "super_admin",
            "created_at": now,
        }
    )
