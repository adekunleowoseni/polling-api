from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from . import hash_ledger
from .auth import get_current_admin
from .database import get_db
from .models import HASH_LEDGER_COLLECTION
from .schemas import LedgerEntryOut, LedgerVerifyOut

router = APIRouter(prefix="/admin/ledger", tags=["admin-ledger"])


@router.get("/verify", response_model=LedgerVerifyOut)
async def verify_ledger(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> LedgerVerifyOut:
    result = await hash_ledger.verify_chain(db)
    return LedgerVerifyOut(**result)


@router.get("/export", response_model=list[LedgerEntryOut])
async def export_ledger(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[LedgerEntryOut]:
    cursor = db[HASH_LEDGER_COLLECTION].find().sort("seq", 1)
    docs = await cursor.to_list(length=1_000_000)
    return [LedgerEntryOut(**doc) for doc in docs]
