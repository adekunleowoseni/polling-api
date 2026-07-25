"""Ensure super admin and state admins exist from environment settings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from .auth import hash_password, new_api_token
from .models import ADMINS_COLLECTION
from .settings import settings

SUPER_ADMIN_ROLE = "super_admin"
STATE_ADMIN_ROLE = "state_admin"

OGUN_STATE = "Ogun State"
OSUN_STATE = "Osun State"

# Tabs state admins may use — full ops for their state only (not global VTpass catalogs).
STATE_ADMIN_TABS = (
    "overview",
    "feeds",
    "snaps",
    "recordings",
    "agents",
    "votes",
)
SUPER_ADMIN_TABS = (
    "overview",
    "feeds",
    "snaps",
    "recordings",
    "agents",
    "votes",
    "data",
    "airtime",
)


def admin_allowed_tabs(admin: dict[str, Any] | str) -> list[str]:
    role = admin if isinstance(admin, str) else (admin.get("role") or SUPER_ADMIN_ROLE)
    if role == STATE_ADMIN_ROLE:
        return list(STATE_ADMIN_TABS)
    return list(SUPER_ADMIN_TABS)


def is_super_admin(admin: dict[str, Any]) -> bool:
    return (admin.get("role") or SUPER_ADMIN_ROLE) == SUPER_ADMIN_ROLE


def admin_state(admin: dict[str, Any]) -> str | None:
    if is_super_admin(admin):
        return None
    state = (admin.get("state") or "").strip()
    return state or None


async def _upsert_admin(
    db: AsyncIOMotorDatabase,
    *,
    email: str,
    name: str,
    password: str,
    role: str,
    state: str | None,
) -> None:
    email = email.lower().strip()
    if not email or not password:
        return

    now = datetime.now(timezone.utc)
    existing = await db[ADMINS_COLLECTION].find_one({"email": email})
    fields: dict[str, Any] = {
        "name": name,
        "role": role,
        "state": state,
        "password_hash": hash_password(password),
        "updated_at": now,
    }
    if existing:
        await db[ADMINS_COLLECTION].update_one({"_id": existing["_id"]}, {"$set": fields})
        return

    await db[ADMINS_COLLECTION].insert_one(
        {
            **fields,
            "email": email,
            "api_token": new_api_token(),
            "created_at": now,
        }
    )


async def ensure_super_admin(db: AsyncIOMotorDatabase) -> None:
    """Create/update super admin + Ogun/Osun state admins."""
    shared_password = (settings.super_admin_password or "").strip()
    if not shared_password:
        return

    super_email = (settings.super_admin_email or "").strip().lower()
    ogun_email = (settings.ogun_admin_email or "").strip().lower()
    osun_email = (settings.osun_admin_email or "").strip().lower()

    if not super_email:
        return

    # Super admin (full access)
    await _upsert_admin(
        db,
        email=super_email,
        name="Super Admin",
        password=shared_password,
        role=SUPER_ADMIN_ROLE,
        state=None,
    )

    # If an older install still has the previous default email as super_admin,
    # demote it to Ogun state admin so it doesn't keep full access.
    legacy = await db[ADMINS_COLLECTION].find_one({"email": "admin@ogun.monitor"})
    if legacy and legacy.get("role") == SUPER_ADMIN_ROLE:
        if super_email != "admin@ogun.monitor":
            await db[ADMINS_COLLECTION].update_one(
                {"_id": legacy["_id"]},
                {
                    "$set": {
                        "role": STATE_ADMIN_ROLE,
                        "state": OGUN_STATE,
                        "name": "Ogun State Admin",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

    ogun_password = (settings.ogun_admin_password or shared_password).strip()
    osun_password = (settings.osun_admin_password or shared_password).strip()

    # Never overwrite the super admin account with a state-admin role.
    if ogun_email and ogun_email != super_email:
        await _upsert_admin(
            db,
            email=ogun_email,
            name="Ogun State Admin",
            password=ogun_password,
            role=STATE_ADMIN_ROLE,
            state=OGUN_STATE,
        )
    if osun_email and osun_email != super_email:
        await _upsert_admin(
            db,
            email=osun_email,
            name="Osun State Admin",
            password=osun_password,
            role=STATE_ADMIN_ROLE,
            state=OSUN_STATE,
        )
