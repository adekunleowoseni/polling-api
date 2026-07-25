from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from .agent_helpers import agent_doc_to_out
from .app_settings import get_app_settings, update_app_settings
from .auth import hash_password, get_current_admin, verify_password
from .database import get_db
from .feed_manager import feed_manager
from .feed_snap_storage import snap_file_path
from .models import (
    ADMINS_COLLECTION,
    AGENTS_COLLECTION,
    AIRTIME_CREDITS_COLLECTION,
    DATA_CREDITS_COLLECTION,
    DETECTED_FACES_COLLECTION,
    FEED_RECORDINGS_COLLECTION,
    FEED_SNAPS_COLLECTION,
    POLLING_UNITS_COLLECTION,
    REGISTRATIONS_COLLECTION,
    VOTE_RESULTS_COLLECTION,
)
from .geo_data import OGUN_LGAS, validate_ogun_ward
from .osun_geo_data import OSUN_LGAS, validate_osun_ward
from .polling_units_router import _doc_to_out
from .recordings import delete_recordings_for_unit, finalize_recording
from .recording_storage import recording_file_path
from .vtpass_client import fetch_wallet_balance, vtpass_configured
from .schemas import (
    AdminAgentOut,
    AdminAgentSummary,
    AdminAgentUnitOut,
    AdminLogin,
    AdminOut,
    AdminOverview,
    AdminPasswordUpdate,
    AdminSessionOut,
    AgentAirtimeClaimLimitUpdate,
    AgentAssignmentUpdate,
    AgentDataClaimLimitUpdate,
    AgentOut,
    AppSettingsOut,
    AppSettingsUpdate,
    FeedRecordingOut,
    FeedSnapOut,
    PeopleCountUpdate,
    PollingUnitOut,
)

CLAIM_STATUSES = ("delivered", "successful", "success", "pending")


async def _agent_data_claims_used(db: AsyncIOMotorDatabase, agent_id: Any) -> int:
    return await db[DATA_CREDITS_COLLECTION].count_documents(
        {"agent_id": agent_id, "status": {"$in": list(CLAIM_STATUSES)}}
    )


def _agent_data_claim_limit(agent_doc: dict[str, Any]) -> int:
    try:
        return max(0, int(agent_doc.get("data_claim_limit", 1)))
    except (TypeError, ValueError):
        return 1


async def _agent_airtime_claims_used(db: AsyncIOMotorDatabase, agent_id: Any) -> int:
    return await db[AIRTIME_CREDITS_COLLECTION].count_documents(
        {"agent_id": agent_id, "status": {"$in": list(CLAIM_STATUSES)}}
    )


def _agent_airtime_claim_limit(agent_doc: dict[str, Any]) -> int:
    try:
        return max(0, int(agent_doc.get("airtime_claim_limit", 1)))
    except (TypeError, ValueError):
        return 1

router = APIRouter(prefix="/admin", tags=["admin"])


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _admin_out(doc: dict[str, Any]) -> AdminOut:
    return AdminOut(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        role=doc.get("role", "super_admin"),
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
    )


def _snap_out(doc: dict[str, Any]) -> FeedSnapOut:
    return FeedSnapOut(
        id=str(doc["_id"]),
        polling_unit_id=str(doc["polling_unit_id"]),
        polling_unit_name=doc.get("polling_unit_name", ""),
        code=doc["code"],
        state=doc.get("state", "Ogun State"),
        ward=doc["ward"],
        lga=doc["lga"],
        people_count=int(doc.get("people_count", 0)),
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
    )


def _recording_out(doc: dict[str, Any]) -> FeedRecordingOut:
    return FeedRecordingOut(
        id=str(doc["_id"]),
        polling_unit_id=str(doc["polling_unit_id"]),
        polling_unit_name=doc.get("polling_unit_name", ""),
        code=doc["code"],
        state=doc.get("state", "Ogun State"),
        ward=doc.get("ward", ""),
        lga=doc.get("lga", ""),
        status=doc.get("status", "completed"),
        started_at=_as_utc(doc["started_at"]) or doc["started_at"],
        ended_at=_as_utc(doc.get("ended_at")),
        duration_seconds=float(doc.get("duration_seconds", 0.0)),
        frame_count=int(doc.get("frame_count", 0)),
        fps=float(doc.get("fps", 0.0)),
        file_size=int(doc.get("file_size", 0)),
    )


async def _delete_snap(snap_id: str, db: AsyncIOMotorDatabase) -> bool:
    try:
        oid = ObjectId(snap_id)
    except InvalidId:
        return False

    doc = await db[FEED_SNAPS_COLLECTION].find_one({"_id": oid})
    if not doc:
        return False

    await db[FEED_SNAPS_COLLECTION].delete_one({"_id": oid})
    path = snap_file_path(snap_id)
    if path.is_file():
        path.unlink()
    return True


@router.post("/login", response_model=AdminSessionOut)
async def admin_login(
    payload: AdminLogin,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminSessionOut:
    email = payload.email.lower().strip()
    admin = await db[ADMINS_COLLECTION].find_one({"email": email})
    if not admin or not verify_password(payload.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return AdminSessionOut(admin=_admin_out(admin), api_token=admin["api_token"])


@router.get("/me", response_model=AdminOut)
async def admin_me(admin: dict[str, Any] = Depends(get_current_admin)) -> AdminOut:
    return _admin_out(admin)


@router.patch("/me/password")
async def admin_change_password(
    payload: AdminPasswordUpdate,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(payload.current_password, admin["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    await db[ADMINS_COLLECTION].update_one(
        {"_id": admin["_id"]},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    return {"status": "password_updated"}


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminOverview:
    _ = admin
    now = datetime.now(timezone.utc)
    cursor = db[POLLING_UNITS_COLLECTION].find()
    docs = await cursor.to_list(length=500)
    units = [_doc_to_out(d) for d in docs]
    live_feeds = sum(1 for u in units if u.stream_status == "live")
    total_people = sum(u.people_count for u in units if u.stream_status == "live")
    vote_pipeline = await db[VOTE_RESULTS_COLLECTION].aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$votes"}, "units": {"$sum": 1}}}]
    ).to_list(length=1)
    vote_totals = vote_pipeline[0] if vote_pipeline else {"total": 0, "units": 0}

    return AdminOverview(
        live_feeds=live_feeds,
        registered_units=len(units),
        total_people_on_site=total_people,
        feed_snapshots=await db[FEED_SNAPS_COLLECTION].count_documents({}),
        agents=await db[AGENTS_COLLECTION].count_documents({}),
        form_registrations=await db[REGISTRATIONS_COLLECTION].count_documents({}),
        total_votes=int(vote_totals.get("total") or 0),
        units_with_results=int(vote_totals.get("units") or 0),
        updated_at=now,
    )


@router.get("/polling-units", response_model=list[PollingUnitOut])
async def admin_list_polling_units(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[PollingUnitOut]:
    _ = admin
    cursor = db[POLLING_UNITS_COLLECTION].find().sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return [_doc_to_out(d) for d in docs]


@router.patch("/polling-units/{code}/people-count", response_model=PollingUnitOut)
async def admin_update_people_count(
    code: str,
    payload: PeopleCountUpdate,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> PollingUnitOut:
    _ = admin
    normalized = code.lower().strip()
    doc = await db[POLLING_UNITS_COLLECTION].find_one({"code": normalized})
    if not doc:
        raise HTTPException(status_code=404, detail="Polling unit not found.")

    corrected = payload.people_count
    peak = max(int(doc.get("peak_people_count", 0)), corrected)
    await db[POLLING_UNITS_COLLECTION].update_one(
        {"_id": doc["_id"]},
        {"$set": {"people_count": corrected, "peak_people_count": peak}},
    )
    from .polling_units_router import _stream_status

    stream_status = _stream_status(doc)
    await feed_manager.update_people_count(normalized, corrected, stream_status)

    updated = await db[POLLING_UNITS_COLLECTION].find_one({"_id": doc["_id"]})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read updated unit.")
    return _doc_to_out(updated)


@router.post("/polling-units/{code}/force-offline")
async def admin_force_offline(
    code: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    _ = admin
    normalized = code.lower().strip()
    doc = await db[POLLING_UNITS_COLLECTION].find_one({"code": normalized})
    if not doc:
        raise HTTPException(status_code=404, detail="Polling unit not found.")

    await db[POLLING_UNITS_COLLECTION].update_one(
        {"_id": doc["_id"]},
        {"$set": {"last_frame_at": None, "webrtc_live": False}},
    )
    await feed_manager.clear_frame(normalized)
    await finalize_recording(db, normalized)
    return {"status": "offline", "code": normalized}


async def _delete_polling_unit_by_code(
    normalized: str,
    db: AsyncIOMotorDatabase,
) -> None:
    doc = await db[POLLING_UNITS_COLLECTION].find_one({"code": normalized})
    if not doc:
        raise HTTPException(status_code=404, detail="Polling unit not found.")

    unit_id = doc["_id"]
    snap_cursor = db[FEED_SNAPS_COLLECTION].find({"polling_unit_id": unit_id})
    snap_docs = await snap_cursor.to_list(length=1000)
    for snap in snap_docs:
        await _delete_snap(str(snap["_id"]), db)

    await delete_recordings_for_unit(db, unit_id, normalized)
    await db[DETECTED_FACES_COLLECTION].delete_many({"polling_unit_id": unit_id})
    await db[POLLING_UNITS_COLLECTION].delete_one({"_id": unit_id})
    await feed_manager.clear_frame(normalized)


@router.delete("/polling-units/{code}")
async def admin_delete_polling_unit(
    code: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    _ = admin
    normalized = code.lower().strip()
    await _delete_polling_unit_by_code(normalized, db)
    return {"status": "deleted", "code": normalized}


@router.get("/feed-snaps", response_model=list[FeedSnapOut])
async def admin_list_feed_snaps(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
    lga: str | None = Query(None),
    ward: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
) -> list[FeedSnapOut]:
    _ = admin
    query: dict[str, Any] = {}
    if lga:
        query["lga"] = lga.strip()
    if ward:
        query["ward"] = ward.strip()

    cursor = db[FEED_SNAPS_COLLECTION].find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_snap_out(doc) for doc in docs]


@router.delete("/feed-snaps/{snap_id}")
async def admin_delete_feed_snap(
    snap_id: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    _ = admin
    if not await _delete_snap(snap_id, db):
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    return {"status": "deleted", "id": snap_id}


async def _get_recording_doc(recording_id: str, db: AsyncIOMotorDatabase) -> dict[str, Any]:
    try:
        oid = ObjectId(recording_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Recording not found.") from exc
    doc = await db[FEED_RECORDINGS_COLLECTION].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Recording not found.")
    return doc


@router.get("/recordings", response_model=list[FeedRecordingOut])
async def admin_list_recordings(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
    lga: str | None = Query(None),
    ward: str | None = Query(None),
    code: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
) -> list[FeedRecordingOut]:
    _ = admin
    query: dict[str, Any] = {}
    if lga:
        query["lga"] = lga.strip()
    if ward:
        query["ward"] = ward.strip()
    if code:
        query["code"] = code.strip().lower()

    cursor = db[FEED_RECORDINGS_COLLECTION].find(query).sort("started_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_recording_out(doc) for doc in docs]


@router.get("/recordings/{recording_id}/video")
async def admin_stream_recording(
    recording_id: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> FileResponse:
    _ = admin
    doc = await _get_recording_doc(recording_id, db)
    path = recording_file_path(str(doc["_id"]))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording file missing.")
    return FileResponse(path, media_type="video/mp4")


@router.get("/recordings/{recording_id}/download")
async def admin_download_recording(
    recording_id: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> FileResponse:
    _ = admin
    doc = await _get_recording_doc(recording_id, db)
    path = recording_file_path(str(doc["_id"]))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording file missing.")
    filename = f"{doc.get('code', 'recording')}-{recording_id}.mp4"
    return FileResponse(path, media_type="video/mp4", filename=filename)


@router.delete("/recordings/{recording_id}")
async def admin_delete_recording(
    recording_id: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    _ = admin
    doc = await _get_recording_doc(recording_id, db)
    # Finalize first if it is still actively recording, so the writer is closed.
    if doc.get("status") == "recording":
        await finalize_recording(db, str(doc["code"]))
    path = recording_file_path(recording_id)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
    await db[FEED_RECORDINGS_COLLECTION].delete_one({"_id": doc["_id"]})
    return {"status": "deleted", "id": recording_id}


async def _build_admin_agent_out(agent_doc: dict[str, Any], db: AsyncIOMotorDatabase) -> AdminAgentOut:
    unit_cursor = db[POLLING_UNITS_COLLECTION].find({"agent_id": agent_doc["_id"]}).sort(
        "created_at", -1
    )
    unit_docs = await unit_cursor.to_list(length=200)
    units = [
        AdminAgentUnitOut(
            id=str(u["_id"]),
            name=u["name"],
            code=u["code"],
            lga=u["lga"],
            ward=u["ward"],
            ingest_token=u.get("ingest_token", ""),
            stream_status=_doc_to_out(u).stream_status,
            people_count=int(u.get("people_count", 0)),
        )
        for u in unit_docs
    ]
    base = agent_doc_to_out(agent_doc)
    used = await _agent_data_claims_used(db, agent_doc["_id"])
    airtime_used = await _agent_airtime_claims_used(db, agent_doc["_id"])
    return AdminAgentOut(
        id=base.id,
        name=base.name,
        email=base.email,
        lga=base.lga,
        ward=base.ward,
        created_at=base.created_at,
        polling_units=units,
        data_claim_limit=_agent_data_claim_limit(agent_doc),
        data_claims_used=used,
        airtime_claim_limit=_agent_airtime_claim_limit(agent_doc),
        airtime_claims_used=airtime_used,
    )


@router.get("/agents", response_model=list[AdminAgentSummary])
async def admin_list_agents(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
    limit: int = Query(2000, ge=1, le=5000),
) -> list[AdminAgentSummary]:
    _ = admin
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=20)
    cursor = db[AGENTS_COLLECTION].find().sort("created_at", -1).limit(limit)
    agent_docs = await cursor.to_list(length=limit)
    results: list[AdminAgentSummary] = []

    for agent_doc in agent_docs:
        oid = agent_doc["_id"]
        unit_count = await db[POLLING_UNITS_COLLECTION].count_documents({"agent_id": oid})
        live_count = await db[POLLING_UNITS_COLLECTION].count_documents(
            {"agent_id": oid, "last_frame_at": {"$gte": cutoff}}
        )
        base = agent_doc_to_out(agent_doc)
        used = await _agent_data_claims_used(db, oid)
        airtime_used = await _agent_airtime_claims_used(db, oid)
        results.append(
            AdminAgentSummary(
                id=base.id,
                name=base.name,
                email=base.email,
                lga=base.lga,
                ward=base.ward,
                created_at=base.created_at,
                polling_unit_count=unit_count,
                live_unit_count=live_count,
                data_claim_limit=_agent_data_claim_limit(agent_doc),
                data_claims_used=used,
                airtime_claim_limit=_agent_airtime_claim_limit(agent_doc),
                airtime_claims_used=airtime_used,
            )
        )

    return results


@router.get("/agents/{agent_id}", response_model=AdminAgentOut)
async def admin_get_agent(
    agent_id: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminAgentOut:
    _ = admin
    try:
        oid = ObjectId(agent_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid agent id.") from exc

    agent_doc = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return await _build_admin_agent_out(agent_doc, db)


@router.patch("/agents/{agent_id}/data-claims", response_model=AdminAgentOut)
async def admin_set_data_claim_limit(
    agent_id: str,
    payload: AgentDataClaimLimitUpdate,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminAgentOut:
    _ = admin
    try:
        oid = ObjectId(agent_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid agent id.") from exc

    agent = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    await db[AGENTS_COLLECTION].update_one(
        {"_id": oid},
        {"$set": {"data_claim_limit": int(payload.data_claim_limit)}},
    )
    updated = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read updated agent.")
    return await _build_admin_agent_out(updated, db)


@router.patch("/agents/{agent_id}/airtime-claims", response_model=AdminAgentOut)
async def admin_set_airtime_claim_limit(
    agent_id: str,
    payload: AgentAirtimeClaimLimitUpdate,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AdminAgentOut:
    _ = admin
    try:
        oid = ObjectId(agent_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid agent id.") from exc

    agent = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    await db[AGENTS_COLLECTION].update_one(
        {"_id": oid},
        {"$set": {"airtime_claim_limit": int(payload.airtime_claim_limit)}},
    )
    updated = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read updated agent.")
    return await _build_admin_agent_out(updated, db)


@router.get("/vtpass/balance")
async def admin_vtpass_balance(
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    _ = admin
    if not vtpass_configured():
        return {"configured": False, "balance": None, "currency": "NGN"}
    try:
        result = await fetch_wallet_balance()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch VTpass balance: {exc}") from exc
    return {"configured": True, **result}


@router.get("/settings", response_model=AppSettingsOut)
async def admin_get_settings(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AppSettingsOut:
    _ = admin
    return AppSettingsOut(**await get_app_settings(db))


@router.patch("/settings", response_model=AppSettingsOut)
async def admin_update_settings(
    payload: AppSettingsUpdate,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AppSettingsOut:
    _ = admin
    updated = await update_app_settings(db, payload.model_dump(exclude_unset=True))
    return AppSettingsOut(**updated)


@router.patch("/agents/{agent_id}/assignment", response_model=AgentOut)
async def admin_assign_agent(
    agent_id: str,
    payload: AgentAssignmentUpdate,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AgentOut:
    _ = admin
    try:
        oid = ObjectId(agent_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid agent id.") from exc

    lga = payload.lga.strip()
    ward = payload.ward.strip()
    if lga in OGUN_LGAS:
        validate_ogun_ward(lga, ward)
    elif lga in OSUN_LGAS:
        validate_osun_ward(lga, ward)
    else:
        raise HTTPException(status_code=400, detail="Invalid LGA for Ogun or Osun State.")

    agent = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    await db[AGENTS_COLLECTION].update_one(
        {"_id": oid},
        {"$set": {"lga": lga, "ward": ward}},
    )
    updated = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read updated agent.")
    return agent_doc_to_out(updated)


@router.delete("/agents/{agent_id}")
async def admin_delete_agent(
    agent_id: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    _ = admin
    try:
        oid = ObjectId(agent_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid agent id.") from exc

    agent = await db[AGENTS_COLLECTION].find_one({"_id": oid})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")

    unit_cursor = db[POLLING_UNITS_COLLECTION].find({"agent_id": oid})
    units = await unit_cursor.to_list(length=500)
    for unit in units:
        await _delete_polling_unit_by_code(unit["code"], db)

    await db[AGENTS_COLLECTION].delete_one({"_id": oid})
    return {"status": "deleted", "id": agent_id}
