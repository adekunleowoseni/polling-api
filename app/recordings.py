"""Orchestration between the RecordingManager (media) and MongoDB (metadata)."""

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from .geo_data import OGUN_STATE
from .models import FEED_RECORDINGS_COLLECTION
from .recording_manager import MAX_FRAMES_PER_FILE, recording_manager
from .recording_storage import recording_file_path

logger = logging.getLogger(__name__)


async def _create_recording_doc(db: AsyncIOMotorDatabase, unit: dict[str, Any]) -> str:
    recording_id = ObjectId()
    from datetime import datetime, timezone

    doc = {
        "_id": recording_id,
        "polling_unit_id": unit["_id"],
        "code": unit["code"],
        "polling_unit_name": unit.get("name", ""),
        "state": unit.get("state", OGUN_STATE),
        "ward": unit.get("ward", ""),
        "lga": unit.get("lga", ""),
        "agent_id": unit.get("agent_id"),
        "status": "recording",
        "started_at": datetime.now(timezone.utc),
        "ended_at": None,
        "duration_seconds": 0.0,
        "frame_count": 0,
        "fps": 0.0,
        "width": 0,
        "height": 0,
        "file_size": 0,
    }
    await db[FEED_RECORDINGS_COLLECTION].insert_one(doc)
    return str(recording_id)


async def append_recording_frame(
    db: AsyncIOMotorDatabase, unit: dict[str, Any], jpeg: bytes
) -> None:
    """Start a recording for this unit if needed, then append a frame.

    Never raises — recording problems must not break live ingest.
    """
    code = str(unit["code"]).lower()
    try:
        if not recording_manager.has_session(code):
            recording_id = await _create_recording_doc(db, unit)
            await recording_manager.start_session(code, recording_id)
        await recording_manager.add_frame(code, jpeg)

        # Rotate to a fresh file if the current one gets very long.
        if recording_manager.frame_count(code) >= MAX_FRAMES_PER_FILE:
            await finalize_recording(db, code)
    except Exception:  # noqa: BLE001 - defensive: ingest must keep working
        logger.exception("Failed to append recording frame for %s", code)


async def finalize_recording(db: AsyncIOMotorDatabase, code: str) -> None:
    """Close the active recording for a code and persist its final metadata."""
    code = code.lower()
    try:
        stats = await recording_manager.finalize(code)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to finalize recording for %s", code)
        return
    if stats is None:
        return

    # Drop empty recordings (stream started but no frame was ever written).
    if stats.frame_count == 0 or stats.file_size == 0:
        await db[FEED_RECORDINGS_COLLECTION].delete_one({"_id": ObjectId(stats.recording_id)})
        path = recording_file_path(stats.recording_id)
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        return

    await db[FEED_RECORDINGS_COLLECTION].update_one(
        {"_id": ObjectId(stats.recording_id)},
        {
            "$set": {
                "status": "completed",
                "ended_at": stats.ended_at,
                "duration_seconds": stats.duration_seconds,
                "frame_count": stats.frame_count,
                "fps": stats.fps,
                "width": stats.width,
                "height": stats.height,
                "file_size": stats.file_size,
            }
        },
    )


async def finalize_idle_recordings(db: AsyncIOMotorDatabase) -> None:
    for code in recording_manager.idle_codes():
        logger.info("Finalizing idle recording for %s", code)
        await finalize_recording(db, code)


async def finalize_all_recordings(db: AsyncIOMotorDatabase) -> None:
    for code in recording_manager.active_codes():
        await finalize_recording(db, code)


async def delete_recordings_for_unit(db: AsyncIOMotorDatabase, unit_id: Any, code: str) -> None:
    """Finalize any active recording and delete all recordings + files for a unit."""
    await finalize_recording(db, code)
    cursor = db[FEED_RECORDINGS_COLLECTION].find({"polling_unit_id": unit_id})
    docs = await cursor.to_list(length=10000)
    for doc in docs:
        rec_id = str(doc["_id"])
        path = recording_file_path(rec_id)
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
    await db[FEED_RECORDINGS_COLLECTION].delete_many({"polling_unit_id": unit_id})
