from __future__ import annotations

from datetime import timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from .database import get_db
from .feed_snap_storage import snap_file_path
from .models import FEED_SNAPS_COLLECTION
from .schemas import FeedSnapOut

router = APIRouter(prefix="/feed-snaps", tags=["feed-snaps"])


def _as_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _doc_to_out(doc: dict[str, Any]) -> FeedSnapOut:
    return FeedSnapOut(
        id=str(doc["_id"]),
        polling_unit_id=str(doc["polling_unit_id"]),
        polling_unit_name=doc.get("polling_unit_name", doc.get("name", "")),
        code=doc["code"],
        state=doc.get("state", "Ogun State"),
        ward=doc["ward"],
        lga=doc["lga"],
        people_count=int(doc.get("people_count", 0)),
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
    )


@router.get("", response_model=list[FeedSnapOut])
async def list_feed_snaps(
    lga: str = Query(..., min_length=1),
    ward: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[FeedSnapOut]:
    query: dict[str, Any] = {"lga": lga.strip()}
    if ward:
        query["ward"] = ward.strip()

    cursor = db[FEED_SNAPS_COLLECTION].find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return [_doc_to_out(doc) for doc in docs]


@router.get("/{snap_id}/image")
async def get_feed_snap_image(
    snap_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> FileResponse:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(snap_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Snapshot not found.") from exc

    doc = await db[FEED_SNAPS_COLLECTION].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Snapshot not found.")

    path = snap_file_path(snap_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot image file missing.")

    return FileResponse(path, media_type="image/jpeg")
