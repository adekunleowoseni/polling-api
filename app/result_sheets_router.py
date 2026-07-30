from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from . import hash_ledger
from .access_log import list_access_log, log_access
from .auth import get_current_admin, get_current_agent
from .admin_bootstrap import admin_state
from .database import get_db
from .models import RESULT_SHEETS_COLLECTION
from .polling_units_router import _get_owned_unit
from .result_sheet_storage import ensure_result_sheets_dir, result_sheet_file_path
from .schemas import (
    AccessLogEntryOut,
    LedgerEntryOut,
    ResultSheetCertificateOut,
    ResultSheetExternalPvtUpdate,
    ResultSheetOfficialUpdate,
    ResultSheetOut,
)

agent_router = APIRouter(prefix="/agents/me/result-sheets", tags=["result-sheets"])
admin_router = APIRouter(prefix="/admin/result-sheets", tags=["admin-result-sheets"])


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _discrepancy_note(doc: dict[str, Any]) -> tuple[bool, int | None, str | None]:
    votes = int(doc.get("votes") or 0)
    accredited = doc.get("accredited_voters")
    official = doc.get("official_votes")

    over_accreditation = accredited is not None and votes > int(accredited)

    official_diff: int | None = None
    note_parts: list[str] = []
    if over_accreditation:
        note_parts.append(
            f"Votes ({votes:,}) exceed accredited voters ({int(accredited):,}) — possible over-voting."
        )
    if official is not None:
        official_diff = votes - int(official)
        if official_diff == 0:
            note_parts.append("Matches the official figure.")
        else:
            note_parts.append(
                f"Our figure ({votes:,}) differs from the official figure "
                f"({int(official):,}) by {abs(official_diff):,}."
            )
    if doc.get("irev_image_uploaded") is False:
        note_parts.append("No result-sheet image found on IReV for this unit.")

    return over_accreditation, official_diff, " ".join(note_parts) or None


def _doc_to_out(doc: dict[str, Any]) -> ResultSheetOut:
    over_accreditation, official_diff, discrepancy_note = _discrepancy_note(doc)
    return ResultSheetOut(
        id=str(doc["_id"]),
        polling_unit_id=str(doc["polling_unit_id"]),
        code=doc["code"],
        polling_unit_name=doc.get("polling_unit_name") or doc.get("code") or "",
        state=doc.get("state") or "",
        ward=doc.get("ward") or "",
        lga=doc.get("lga") or "",
        agent_id=str(doc["agent_id"]) if doc.get("agent_id") else None,
        votes=int(doc.get("votes") or 0),
        accredited_voters=doc.get("accredited_voters"),
        registered_voters=doc.get("registered_voters"),
        sha256=doc.get("sha256") or "",
        captured_lat=doc.get("captured_lat"),
        captured_lng=doc.get("captured_lng"),
        captured_accuracy_m=doc.get("captured_accuracy_m"),
        device_captured_at=_as_utc(doc.get("device_captured_at")),
        received_at=_as_utc(doc.get("received_at")) or doc["received_at"],
        device_id=doc.get("device_id"),
        app_version=doc.get("app_version"),
        people_count_at_capture=int(doc.get("people_count_at_capture") or 0),
        supersedes_id=str(doc["supersedes_id"]) if doc.get("supersedes_id") else None,
        version=int(doc.get("version") or 1),
        official_votes=doc.get("official_votes"),
        official_source=doc.get("official_source"),
        official_checked_at=_as_utc(doc.get("official_checked_at")),
        official_note=doc.get("official_note"),
        irev_image_uploaded=doc.get("irev_image_uploaded"),
        external_pvt_source=doc.get("external_pvt_source"),
        external_pvt_votes=doc.get("external_pvt_votes"),
        external_pvt_note=doc.get("external_pvt_note"),
        agent_accreditation_number=doc.get("agent_accreditation_number"),
        agent_is_ec8a_signatory=doc.get("agent_is_ec8a_signatory"),
        agent_party_name=doc.get("agent_party_name"),
        created_at=_as_utc(doc.get("created_at")) or doc["received_at"],
        over_accreditation=over_accreditation,
        official_diff=official_diff,
        discrepancy_note=discrepancy_note,
    )


@agent_router.post("", response_model=ResultSheetOut, status_code=201)
async def submit_result_sheet(
    code: str = Form(...),
    votes: int = Form(..., ge=0, le=1_000_000),
    accredited_voters: int | None = Form(default=None, ge=0, le=1_000_000),
    registered_voters: int | None = Form(default=None, ge=0, le=1_000_000),
    lat: float | None = Form(default=None, ge=-90, le=90),
    lng: float | None = Form(default=None, ge=-180, le=180),
    accuracy_m: float | None = Form(default=None, ge=0),
    device_captured_at: datetime | None = Form(default=None),
    device_id: str | None = Form(default=None, max_length=200),
    app_version: str | None = Form(default=None, max_length=40),
    photo: UploadFile = File(...),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResultSheetOut:
    if agent.get("accreditation_status") != "approved":
        raise HTTPException(
            status_code=403,
            detail=(
                "Your party accreditation has not been approved yet. Upload your "
                "accreditation document and wait for admin approval before submitting "
                "result sheets."
            ),
        )

    unit = await _get_owned_unit(code, agent, db)

    if photo.content_type not in {"image/jpeg", "image/png", "image/jpg"}:
        raise HTTPException(status_code=400, detail="Result sheet photo must be JPEG or PNG.")

    raw = await photo.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty photo.")

    normalized_code = code.lower().strip()
    now = datetime.now(timezone.utc)
    sha256 = hashlib.sha256(raw).hexdigest()

    previous = await db[RESULT_SHEETS_COLLECTION].find_one(
        {"code": normalized_code}, sort=[("created_at", -1)]
    )
    version = int(previous.get("version") or 1) + 1 if previous else 1

    doc = {
        "polling_unit_id": unit["_id"],
        "code": normalized_code,
        "polling_unit_name": unit.get("name") or normalized_code,
        "state": unit.get("state") or "",
        "ward": unit.get("ward") or "",
        "lga": unit.get("lga") or "",
        "agent_id": agent["_id"],
        "votes": int(votes),
        "accredited_voters": accredited_voters,
        "registered_voters": registered_voters,
        "sha256": sha256,
        "captured_lat": lat,
        "captured_lng": lng,
        "captured_accuracy_m": accuracy_m,
        "device_captured_at": device_captured_at,
        "received_at": now,
        "device_id": device_id,
        "app_version": app_version,
        "people_count_at_capture": int(unit.get("people_count") or 0),
        "supersedes_id": previous["_id"] if previous else None,
        "version": version,
        "official_votes": None,
        "official_source": None,
        "official_checked_at": None,
        "official_note": None,
        "irev_image_uploaded": None,
        "external_pvt_source": None,
        "external_pvt_votes": None,
        "external_pvt_note": None,
        "agent_accreditation_number": agent.get("accreditation_number"),
        "agent_is_ec8a_signatory": agent.get("is_ec8a_signatory"),
        "agent_party_name": agent.get("party_name"),
        "created_at": now,
    }
    result = await db[RESULT_SHEETS_COLLECTION].insert_one(doc)
    sheet_id = str(result.inserted_id)

    ensure_result_sheets_dir()
    result_sheet_file_path(sheet_id).write_bytes(raw)

    await hash_ledger.append_entry(db, entity_type="result_sheet", entity_id=sheet_id, entity_sha256=sha256)

    inserted = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": result.inserted_id})
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to read saved result sheet.")
    return _doc_to_out(inserted)


@agent_router.get("", response_model=list[ResultSheetOut])
async def list_my_result_sheets(
    history: bool = Query(default=False),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[ResultSheetOut]:
    if history:
        cursor = db[RESULT_SHEETS_COLLECTION].find({"agent_id": agent["_id"]}).sort(
            [("code", 1), ("created_at", -1)]
        )
        docs = await cursor.to_list(length=1000)
        return [_doc_to_out(d) for d in docs]

    pipeline = [
        {"$match": {"agent_id": agent["_id"]}},
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$code", "doc": {"$first": "$$ROOT"}}},
    ]
    rows = await db[RESULT_SHEETS_COLLECTION].aggregate(pipeline).to_list(length=1000)
    docs = [row["doc"] for row in rows]
    docs.sort(key=lambda d: d.get("created_at") or datetime.min, reverse=True)
    return [_doc_to_out(d) for d in docs]


@agent_router.get("/{sheet_id}/photo")
async def get_my_result_sheet_photo(
    sheet_id: str,
    request: Request,
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> FileResponse:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(sheet_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Result sheet not found.") from exc

    doc = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": oid, "agent_id": agent["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Result sheet not found.")

    path = result_sheet_file_path(sheet_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Result sheet image file missing.")

    await log_access(
        db,
        entity_type="result_sheet",
        entity_id=sheet_id,
        actor_type="agent",
        actor_id=str(agent["_id"]),
        actor_name=agent.get("name") or agent.get("email") or "agent",
        action="view",
        ip=_client_ip(request),
    )
    return FileResponse(path, media_type="image/jpeg")


@admin_router.get("", response_model=list[ResultSheetOut])
async def admin_list_result_sheets(
    history: bool = Query(default=False),
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[ResultSheetOut]:
    from .admin_bootstrap import OGUN_STATE, OSUN_STATE
    from .geo_data import OGUN_LGAS
    from .osun_geo_data import OSUN_LGAS

    query: dict[str, Any] = {}
    state = admin_state(admin)
    if state:
        lgas = list(OGUN_LGAS.keys()) if state == OGUN_STATE else list(OSUN_LGAS.keys()) if state == OSUN_STATE else []
        query = {"$or": [{"state": state}, {"lga": {"$in": lgas}}]} if lgas else {"state": state}

    if history:
        cursor = db[RESULT_SHEETS_COLLECTION].find(query).sort([("code", 1), ("created_at", -1)])
        docs = await cursor.to_list(length=5000)
        return [_doc_to_out(d) for d in docs]

    pipeline: list[dict[str, Any]] = []
    if query:
        pipeline.append({"$match": query})
    pipeline += [
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$code", "doc": {"$first": "$$ROOT"}}},
    ]
    rows = await db[RESULT_SHEETS_COLLECTION].aggregate(pipeline).to_list(length=5000)
    docs = [row["doc"] for row in rows]
    docs.sort(key=lambda d: d.get("created_at") or datetime.min, reverse=True)
    return [_doc_to_out(d) for d in docs]


@admin_router.get("/{sheet_id}/photo")
async def admin_get_result_sheet_photo(
    sheet_id: str,
    request: Request,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> FileResponse:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(sheet_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Result sheet not found.") from exc

    doc = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Result sheet not found.")

    path = result_sheet_file_path(sheet_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Result sheet image file missing.")

    await log_access(
        db,
        entity_type="result_sheet",
        entity_id=sheet_id,
        actor_type="admin",
        actor_id=str(admin["_id"]),
        actor_name=admin.get("name") or admin.get("email") or "admin",
        action="view",
        ip=_client_ip(request),
    )
    return FileResponse(path, media_type="image/jpeg")


@admin_router.patch("/{sheet_id}/official-figure", response_model=ResultSheetOut)
async def set_official_figure(
    sheet_id: str,
    payload: ResultSheetOfficialUpdate,
    request: Request,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResultSheetOut:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(sheet_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Result sheet not found.") from exc

    doc = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Result sheet not found.")

    now = datetime.now(timezone.utc)
    await db[RESULT_SHEETS_COLLECTION].update_one(
        {"_id": oid},
        {
            "$set": {
                "official_votes": payload.official_votes,
                "official_note": payload.official_note,
                "official_source": "manual",
                "official_checked_at": now,
            }
        },
    )
    await log_access(
        db,
        entity_type="result_sheet",
        entity_id=sheet_id,
        actor_type="admin",
        actor_id=str(admin["_id"]),
        actor_name=admin.get("name") or admin.get("email") or "admin",
        action="edit",
        ip=_client_ip(request),
    )
    updated = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": oid})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read updated result sheet.")
    return _doc_to_out(updated)


@admin_router.patch("/{sheet_id}/external-pvt", response_model=ResultSheetOut)
async def set_external_pvt_figure(
    sheet_id: str,
    payload: ResultSheetExternalPvtUpdate,
    request: Request,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResultSheetOut:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(sheet_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Result sheet not found.") from exc

    doc = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Result sheet not found.")

    await db[RESULT_SHEETS_COLLECTION].update_one(
        {"_id": oid},
        {
            "$set": {
                "external_pvt_source": payload.external_pvt_source,
                "external_pvt_votes": payload.external_pvt_votes,
                "external_pvt_note": payload.external_pvt_note,
            }
        },
    )
    await log_access(
        db,
        entity_type="result_sheet",
        entity_id=sheet_id,
        actor_type="admin",
        actor_id=str(admin["_id"]),
        actor_name=admin.get("name") or admin.get("email") or "admin",
        action="edit",
        ip=_client_ip(request),
    )
    updated = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": oid})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read updated result sheet.")
    return _doc_to_out(updated)


@admin_router.get("/{sheet_id}/certificate", response_model=ResultSheetCertificateOut)
async def get_result_sheet_certificate(
    sheet_id: str,
    request: Request,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ResultSheetCertificateOut:
    from bson import ObjectId
    from bson.errors import InvalidId

    from .models import AGENTS_COLLECTION

    try:
        oid = ObjectId(sheet_id)
    except InvalidId as exc:
        raise HTTPException(status_code=404, detail="Result sheet not found.") from exc

    doc = await db[RESULT_SHEETS_COLLECTION].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Result sheet not found.")

    ledger_entry = await hash_ledger.get_entry_for_entity(db, sheet_id)
    access_entries = await list_access_log(db, sheet_id)

    agent_name = None
    agent_email = None
    if doc.get("agent_id"):
        agent_doc = await db[AGENTS_COLLECTION].find_one({"_id": doc["agent_id"]})
        if agent_doc:
            agent_name = agent_doc.get("name")
            agent_email = agent_doc.get("email")

    await log_access(
        db,
        entity_type="result_sheet",
        entity_id=sheet_id,
        actor_type="admin",
        actor_id=str(admin["_id"]),
        actor_name=admin.get("name") or admin.get("email") or "admin",
        action="view",
        ip=_client_ip(request),
    )

    return ResultSheetCertificateOut(
        result_sheet=_doc_to_out(doc),
        ledger_entry=LedgerEntryOut(**ledger_entry) if ledger_entry else None,
        access_log=[AccessLogEntryOut(**entry) for entry in access_entries],
        agent_name=agent_name,
        agent_email=agent_email,
        generated_at=datetime.now(timezone.utc),
    )
