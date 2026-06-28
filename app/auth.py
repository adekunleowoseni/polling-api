from __future__ import annotations

import secrets
from typing import Any

import bcrypt
from fastapi import Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .database import get_db
from .models import AGENTS_COLLECTION


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def new_api_token() -> str:
    return secrets.token_urlsafe(32)


async def get_current_agent(
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    agent = await db[AGENTS_COLLECTION].find_one({"api_token": x_agent_token})
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or missing agent token.")
    return agent


async def get_optional_agent(
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any] | None:
    if not x_agent_token:
        return None
    return await db[AGENTS_COLLECTION].find_one({"api_token": x_agent_token})


async def get_current_admin(
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    from .models import ADMINS_COLLECTION

    admin = await db[ADMINS_COLLECTION].find_one({"api_token": x_admin_token})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token.")
    return admin
