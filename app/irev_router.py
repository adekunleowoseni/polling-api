from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .admin_bootstrap import OGUN_STATE, OSUN_STATE, admin_state
from .auth import get_current_admin
from .database import get_db
from .irev_watchdog import get_irev_config, sync_pu_mapping
from .models import IREV_PU_MAP_COLLECTION, RESULT_SHEETS_COLLECTION

router = APIRouter(prefix="/admin/irev", tags=["admin-irev"])


@router.get("/status")
async def irev_status(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    config, enabled, poll_interval = await get_irev_config(db)
    mapped_units = await db[IREV_PU_MAP_COLLECTION].count_documents({})
    auto_filled = await db[RESULT_SHEETS_COLLECTION].count_documents({"official_source": "irev_auto"})
    return {
        "enabled": enabled,
        "configured": config.configured,
        "irev_api_base": config.api_base or None,
        "irev_election_id": config.election_id or None,
        "poll_interval_seconds": poll_interval,
        "mapped_polling_units": mapped_units,
        "auto_filled_result_sheets": auto_filled,
    }


@router.post("/sync-mapping")
async def trigger_sync_mapping(
    state_irev_id: str = Body(..., embed=True),
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    state = admin_state(admin) or OGUN_STATE
    if state not in (OGUN_STATE, OSUN_STATE):
        raise HTTPException(status_code=400, detail="Sign in as an Ogun or Osun admin to run this sync.")

    result = await sync_pu_mapping(db, state_irev_id, state=state)
    return {"state": state, **result}
