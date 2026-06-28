from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from .auth import get_current_agent
from .database import get_db
from .face_dedup import process_frame_with_face_dedup
from .feed_manager import feed_manager
from .feed_snap_storage import ensure_snaps_dir, snap_file_path
from .models import DETECTED_FACES_COLLECTION, FEED_SNAPS_COLLECTION, POLLING_UNITS_COLLECTION
from .geo_data import OGUN_LGAS, OGUN_STATE
from .schemas import FeedSnapOut, PeopleCountUpdate, PollingUnitCreate, PollingUnitOut, PollingUnitRegisterOut

router = APIRouter(prefix="/polling-units", tags=["polling-units"])

STREAM_LIVE_SECONDS = 20


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _stream_status(last_frame_at: datetime | None) -> str:
    if not last_frame_at:
        return "offline"
    aware = _as_utc(last_frame_at)
    if aware and datetime.now(timezone.utc) - aware <= timedelta(seconds=STREAM_LIVE_SECONDS):
        return "live"
    return "offline"


def _doc_to_out(doc: dict[str, Any]) -> PollingUnitOut:
    last_frame_at = doc.get("last_frame_at")
    return PollingUnitOut(
        id=str(doc["_id"]),
        name=doc["name"],
        code=doc["code"],
        state=doc.get("state", OGUN_STATE),
        ward=doc["ward"],
        lga=doc["lga"],
        people_count=int(doc.get("people_count", 0)),
        peak_people_count=int(doc.get("peak_people_count", 0)),
        stream_status=_stream_status(last_frame_at),
        device_type=doc.get("device_type", "meta_rayban"),
        last_frame_at=_as_utc(last_frame_at),
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
    )


async def _get_owned_unit(
    code: str,
    agent: dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> dict[str, Any]:
    normalized = code.lower().strip()
    doc = await db[POLLING_UNITS_COLLECTION].find_one(
        {"code": normalized, "agent_id": agent["_id"]}
    )
    if doc:
        return doc

    existing = await db[POLLING_UNITS_COLLECTION].find_one({"code": normalized})
    if existing:
        raise HTTPException(
            status_code=403,
            detail="This polling unit belongs to another agent. Sign in with the account that created it.",
        )
    raise HTTPException(status_code=404, detail=f"Polling unit '{normalized}' was not found.")


async def _load_known_embeddings(
    polling_unit_id: Any,
    db: AsyncIOMotorDatabase,
) -> list[list[float]]:
    cursor = db[DETECTED_FACES_COLLECTION].find(
        {"polling_unit_id": polling_unit_id},
        {"embedding": 1},
    )
    docs = await cursor.to_list(length=10000)
    return [d["embedding"] for d in docs if d.get("embedding")]


@router.post("", response_model=PollingUnitRegisterOut, status_code=201)
async def register_polling_unit(
    payload: PollingUnitCreate,
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PollingUnitRegisterOut:
    code = payload.code.lower().strip()
    existing = await db[POLLING_UNITS_COLLECTION].find_one({"code": code})
    if existing:
        raise HTTPException(status_code=409, detail="Polling unit code already registered.")

    state = payload.state.strip()
    lga = payload.lga.strip()
    ward = payload.ward.strip()
    if state != OGUN_STATE:
        raise HTTPException(status_code=400, detail="Only Ogun State is supported at this time.")
    if lga not in OGUN_LGAS:
        raise HTTPException(status_code=400, detail="Invalid LGA for Ogun State.")
    if ward not in OGUN_LGAS[lga]:
        raise HTTPException(status_code=400, detail="Invalid ward for the selected LGA.")

    agent_lga = agent.get("lga")
    agent_ward = agent.get("ward")
    if agent_lga and agent_ward and (lga != agent_lga or ward != agent_ward):
        raise HTTPException(
            status_code=403,
            detail=f"You are assigned to {agent_ward}, {agent_lga}. Register units only in your assigned area.",
        )

    now = datetime.now(timezone.utc)
    ingest_token = secrets.token_urlsafe(32)
    doc = {
        "agent_id": agent["_id"],
        "name": payload.name.strip(),
        "code": code,
        "state": state,
        "ward": ward,
        "lga": lga,
        "people_count": 0,
        "peak_people_count": 0,
        "device_type": payload.device_type,
        "ingest_token": ingest_token,
        "last_frame_at": None,
        "created_at": now,
    }
    result = await db[POLLING_UNITS_COLLECTION].insert_one(doc)
    inserted = await db[POLLING_UNITS_COLLECTION].find_one({"_id": result.inserted_id})
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to read registered polling unit.")

    out = _doc_to_out(inserted)
    return PollingUnitRegisterOut(**out.model_dump(), ingest_token=ingest_token)


@router.post("/{code}/verify-ingest")
async def verify_ingest_token(
    code: str,
    x_ingest_token: str = Header(..., alias="X-Ingest-Token"),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    doc = await _get_owned_unit(code, agent, db)
    if x_ingest_token != doc.get("ingest_token"):
        raise HTTPException(status_code=401, detail="Invalid ingest token.")
    return {"status": "valid", "code": code.lower()}


@router.post("/{code}/ingest")
async def ingest_frame(
    code: str,
    frame: UploadFile = File(...),
    x_ingest_token: str = Header(..., alias="X-Ingest-Token"),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    doc = await _get_owned_unit(code, agent, db)
    if x_ingest_token != doc.get("ingest_token"):
        raise HTTPException(status_code=401, detail="Invalid ingest token.")

    if frame.content_type not in {"image/jpeg", "image/png", "image/jpg"}:
        raise HTTPException(status_code=400, detail="Frame must be JPEG or PNG.")

    raw = await frame.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty frame.")

    known_embeddings = await _load_known_embeddings(doc["_id"], db)
    current_unique = int(doc.get("people_count", 0))

    try:
        result, new_embeddings = process_frame_with_face_dedup(
            raw, known_embeddings, current_unique
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    if new_embeddings:
        await db[DETECTED_FACES_COLLECTION].insert_many(
            [
                {
                    "polling_unit_id": doc["_id"],
                    "code": code.lower(),
                    "embedding": emb,
                    "first_seen_at": now,
                    "last_seen_at": now,
                }
                for emb in new_embeddings
            ]
        )

    unique_total = result.unique_total
    peak = max(int(doc.get("peak_people_count", 0)), unique_total)
    await db[POLLING_UNITS_COLLECTION].update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "people_count": unique_total,
                "peak_people_count": peak,
                "last_frame_at": now,
            }
        },
    )
    await feed_manager.store_frame(code.lower(), result.annotated_jpeg, unique_total)

    return {
        "code": code.lower(),
        "people_count": unique_total,
        "new_faces_this_frame": result.new_faces,
        "faces_in_frame": result.faces_in_frame,
        "peak_people_count": peak,
        "stream_status": "live",
        "last_frame_at": now.isoformat(),
    }


@router.patch("/{code}/people-count", response_model=PollingUnitOut)
async def correct_people_count(
    code: str,
    payload: PeopleCountUpdate,
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PollingUnitOut:
    doc = await _get_owned_unit(code, agent, db)
    now = datetime.now(timezone.utc)
    corrected = payload.people_count
    peak = max(int(doc.get("peak_people_count", 0)), corrected)

    await db[POLLING_UNITS_COLLECTION].update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "people_count": corrected,
                "peak_people_count": peak,
                "people_count_corrected_at": now,
            }
        },
    )

    stream_status = _stream_status(doc.get("last_frame_at"))
    await feed_manager.update_people_count(code.lower(), corrected, stream_status)

    updated = await db[POLLING_UNITS_COLLECTION].find_one({"_id": doc["_id"]})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read updated polling unit.")
    return _doc_to_out(updated)


@router.post("/{code}/snaps", response_model=FeedSnapOut, status_code=201)
async def save_feed_snap(
    code: str,
    photo: UploadFile = File(...),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> FeedSnapOut:
    doc = await _get_owned_unit(code, agent, db)

    if photo.content_type not in {"image/jpeg", "image/png", "image/jpg"}:
        raise HTTPException(status_code=400, detail="Photo must be JPEG or PNG.")

    raw = await photo.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty photo.")

    now = datetime.now(timezone.utc)
    people_count = int(doc.get("people_count", 0))
    snap_doc = {
        "polling_unit_id": doc["_id"],
        "code": code.lower(),
        "polling_unit_name": doc["name"],
        "state": doc.get("state", OGUN_STATE),
        "ward": doc["ward"],
        "lga": doc["lga"],
        "agent_id": agent["_id"],
        "people_count": people_count,
        "created_at": now,
    }
    result = await db[FEED_SNAPS_COLLECTION].insert_one(snap_doc)
    snap_id = str(result.inserted_id)

    ensure_snaps_dir()
    snap_file_path(snap_id).write_bytes(raw)

    inserted = await db[FEED_SNAPS_COLLECTION].find_one({"_id": result.inserted_id})
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to read saved snapshot.")

    return FeedSnapOut(
        id=snap_id,
        polling_unit_id=str(doc["_id"]),
        polling_unit_name=doc["name"],
        code=code.lower(),
        state=doc.get("state", OGUN_STATE),
        ward=doc["ward"],
        lga=doc["lga"],
        people_count=people_count,
        created_at=now,
    )


@router.get("/{code}/snapshot")
async def get_snapshot(code: str, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    doc = await db[POLLING_UNITS_COLLECTION].find_one({"code": code.lower()})
    if not doc:
        raise HTTPException(status_code=404, detail="Polling unit not found.")
    stored = feed_manager.get_frame(code.lower())
    if not stored.jpeg:
        raise HTTPException(status_code=404, detail="No live frame available yet.")
    return Response(content=stored.jpeg, media_type="image/jpeg")
