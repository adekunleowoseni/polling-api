from __future__ import annotations

import asyncio
import difflib
import logging
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from . import irev_client
from .app_settings import get_app_settings
from .irev_client import IrevConfig
from .models import IREV_PU_MAP_COLLECTION, POLLING_UNITS_COLLECTION, RESULT_SHEETS_COLLECTION

logger = logging.getLogger(__name__)


async def get_irev_config(db: AsyncIOMotorDatabase) -> tuple[IrevConfig, bool, int]:
    """Read the super-admin-managed IReV config from app_settings.

    Returns (config, enabled, poll_interval_seconds). `config.configured` may
    be False even when `enabled` is True if the admin hasn't filled in both
    fields yet — callers should check both.
    """
    doc = await get_app_settings(db)
    config = IrevConfig(api_base=doc["irev_api_base"], election_id=doc["irev_election_id"])
    return config, bool(doc["irev_enabled"]), int(doc["irev_poll_interval_seconds"])


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower().strip() if ch.isalnum())


def _best_match(target: str, candidates: list[dict[str, Any]], name_key: str = "name") -> dict[str, Any] | None:
    target_norm = _normalize(target)
    if not target_norm:
        return None
    by_norm = {_normalize(str(c.get(name_key, ""))): c for c in candidates}
    if target_norm in by_norm:
        return by_norm[target_norm]
    close = difflib.get_close_matches(target_norm, list(by_norm.keys()), n=1, cutoff=0.75)
    return by_norm[close[0]] if close else None


async def sync_pu_mapping(db: AsyncIOMotorDatabase, state_irev_id: str, *, state: str) -> dict[str, Any]:
    """Best-effort match of our registered polling units to IReV's ids.

    Only useful once a super admin has set irev_api_base/irev_election_id
    (Settings tab) for a live election and `state_irev_id` has been captured
    from IReV's own devtools network calls for the target state. Matches by
    name (LGA, ward) then by official pu_code/name (polling unit), skipping
    anything it can't confidently match rather than guessing. Returns counts
    for the caller to report back to the admin.
    """
    config, enabled, _ = await get_irev_config(db)
    if not enabled or not config.configured:
        return {
            "matched": 0,
            "skipped": 0,
            "error": "IReV watchdog is not enabled/configured. Set the API base, election ID, "
            "and enable it under admin Settings first.",
        }

    units = await db[POLLING_UNITS_COLLECTION].find({"state": state}).to_list(length=10000)
    if not units:
        return {"matched": 0, "skipped": 0}

    by_lga: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        by_lga.setdefault(unit.get("lga") or "", []).append(unit)

    irev_lgas = await irev_client.fetch_state_lgas(config, state_irev_id)
    if irev_lgas is None:
        return {"matched": 0, "skipped": len(units), "error": "Could not reach IReV for this state right now."}

    matched = 0
    skipped = 0
    for lga_name, lga_units in by_lga.items():
        lga_match = _best_match(lga_name, irev_lgas)
        if not lga_match:
            skipped += len(lga_units)
            continue

        irev_wards = await irev_client.fetch_lga_wards(config, str(lga_match.get("id") or lga_match.get("_id")))
        if irev_wards is None:
            skipped += len(lga_units)
            continue

        by_ward: dict[str, list[dict[str, Any]]] = {}
        for unit in lga_units:
            by_ward.setdefault(unit.get("ward") or "", []).append(unit)

        for ward_name, ward_units in by_ward.items():
            ward_match = _best_match(ward_name, irev_wards)
            if not ward_match:
                skipped += len(ward_units)
                continue

            ward_irev_id = str(ward_match.get("id") or ward_match.get("_id"))
            irev_pus = await irev_client.fetch_ward_polling_units(config, ward_irev_id)
            if irev_pus is None:
                skipped += len(ward_units)
                continue

            for unit in ward_units:
                pu_match = _best_match(unit.get("pu_code") or unit.get("name") or "", irev_pus, "code") \
                    or _best_match(unit.get("name") or "", irev_pus, "name")
                if not pu_match:
                    skipped += 1
                    continue

                await db[IREV_PU_MAP_COLLECTION].update_one(
                    {"code": unit["code"]},
                    {
                        "$set": {
                            "code": unit["code"],
                            "ward_irev_id": ward_irev_id,
                            "pu_irev_id": str(pu_match.get("id") or pu_match.get("_id")),
                            "matched_name": pu_match.get("name") or pu_match.get("code"),
                            "matched_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
                matched += 1

    return {"matched": matched, "skipped": skipped}


async def poll_once(db: AsyncIOMotorDatabase) -> int:
    """Fill in `official_votes` for mapped result sheets that don't have a
    manually-entered figure yet. Never overwrites official_source="manual".
    Returns the number of rows updated.
    """
    config, enabled, _ = await get_irev_config(db)
    if not enabled or not config.configured:
        return 0

    pipeline = [
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$code", "doc": {"$first": "$$ROOT"}}},
    ]
    rows = await db[RESULT_SHEETS_COLLECTION].aggregate(pipeline).to_list(length=5000)
    pending = [row["doc"] for row in rows if not row["doc"].get("official_source")]
    if not pending:
        return 0

    codes = [d["code"] for d in pending]
    mappings = await db[IREV_PU_MAP_COLLECTION].find({"code": {"$in": codes}}).to_list(length=5000)
    mapping_by_code = {m["code"]: m for m in mappings}

    updated = 0
    for doc in pending:
        mapping = mapping_by_code.get(doc["code"])
        if not mapping:
            continue
        result = await irev_client.fetch_official_result(config, mapping["pu_irev_id"])
        if result is None or result.votes is None:
            continue
        await db[RESULT_SHEETS_COLLECTION].update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "official_votes": result.votes,
                    "official_source": "irev_auto",
                    "official_checked_at": datetime.now(timezone.utc),
                }
            },
        )
        updated += 1
    return updated


async def irev_watchdog_loop(get_database) -> None:
    """Background task mirroring the recording sweeper pattern in main.py.

    Entirely inert (no requests, no writes) whenever the super admin hasn't
    enabled + configured IReV in Settings, which is the default state.
    Re-reads config from the database every cycle so a change made in the
    admin dashboard takes effect without a restart.
    """
    while True:
        db = get_database()
        try:
            _, enabled, poll_interval = await get_irev_config(db)
        except Exception:
            logger.exception("IReV watchdog failed to read config; retrying shortly")
            await asyncio.sleep(60)
            continue

        await asyncio.sleep(max(60, poll_interval))
        if not enabled:
            continue
        try:
            updated = await poll_once(db)
            if updated:
                logger.info("IReV watchdog updated %d result sheet(s).", updated)
        except Exception:
            logger.exception("IReV watchdog iteration failed")
