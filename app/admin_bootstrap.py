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

# Tabs state admins may use in the dashboard.
STATE_ADMIN_TABS = ("overview", "feeds", "snaps", "agents", "votes")
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
        "updated_at": now,
    }
    if existing:
        # Keep existing password unless this is a brand-new role assignment from bootstrap
        # and password was never set properly — always refresh role/state/name.
        await db[ADMINS_COLLECTION].update_one({"_id": existing["_id"]}, {"$set": fields})
        return

    await db[ADMINS_COLLECTION].insert_one(
        {
            **fields,
            "email": email,
            "password_hash": hash_password(password),
            "api_token": new_api_token(),
            "created_at": now,
        }
    )


async def ensure_super_admin(db: AsyncIOMotorDatabase) -> None:
    """Create/update super admin + Ogun/Osun state admins."""
    shared_password = settings.super_admin_password
    if not shared_password:
        return

    # Super admin (full access)
    await _upsert_admin(
        db,
        email=settings.super_admin_email,
        name="Super Admin",
        password=shared_password,
        role=SUPER_ADMIN_ROLE,
        state=None,
    )

    # If an older install still has the previous default email as super_admin,
    # demote it to Ogun state admin so it doesn't keep full access.
    legacy = await db[ADMINS_COLLECTION].find_one({"email": "admin@ogun.monitor"})
    if legacy and legacy.get("role") == SUPER_ADMIN_ROLE:
        new_super = settings.super_admin_email.lower().strip()
        if new_super != "admin@ogun.monitor":
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

    await _upsert_admin(
        db,
        email=settings.ogun_admin_email,
        name="Ogun State Admin",
        password=ogun_password,
        role=STATE_ADMIN_ROLE,
        state=OGUN_STATE,
    )
    await _upsert_admin(
        db,
        email=settings.osun_admin_email,
        name="Osun State Admin",
        password=osun_password,
        role=STATE_ADMIN_ROLE,
        state=OSUN_STATE,
    )
