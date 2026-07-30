from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from . import hash_ledger
from .admin_bootstrap import admin_state
from .auth import get_current_admin, get_current_agent
from .database import get_db
from .models import WITNESS_STATEMENTS_COLLECTION
from .polling_units_router import _get_owned_unit
from .schemas import WitnessPersonPresent, WitnessStatementOut

agent_router = APIRouter(prefix="/agents/me/witness-statements", tags=["witness-statements"])
admin_router = APIRouter(prefix="/admin/witness-statements", tags=["admin-witness-statements"])

INCIDENT_CATEGORIES = {
    "over_voting",
    "violence",
    "vote_buying",
    "snatching",
    "irev_missing",
    "other",
}


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _doc_to_out(doc: dict[str, Any], agent_name: str | None = None) -> WitnessStatementOut:
    return WitnessStatementOut(
        id=str(doc["_id"]),
        polling_unit_id=str(doc["polling_unit_id"]),
        code=doc["code"],
        polling_unit_name=doc.get("polling_unit_name") or doc.get("code") or "",
        state=doc.get("state") or "",
        ward=doc.get("ward") or "",
        lga=doc.get("lga") or "",
        agent_id=str(doc["agent_id"]) if doc.get("agent_id") else None,
        agent_name=agent_name,
        result_sheet_id=str(doc["result_sheet_id"]) if doc.get("result_sheet_id") else None,
        incident_category=doc.get("incident_category") or "other",
        narrative=doc.get("narrative") or "",
        people_present=[WitnessPersonPresent(**p) for p in (doc.get("people_present") or [])],
        occurred_at=_as_utc(doc.get("occurred_at")),
        submitted_at=_as_utc(doc.get("submitted_at")) or doc["submitted_at"],
        captured_lat=doc.get("captured_lat"),
        captured_lng=doc.get("captured_lng"),
        supersedes_id=str(doc["supersedes_id"]) if doc.get("supersedes_id") else None,
        version=int(doc.get("version") or 1),
    )


@agent_router.post("", response_model=WitnessStatementOut, status_code=201)
async def submit_witness_statement(
    code: str = Form(...),
    incident_category: str = Form(...),
    narrative: str = Form(..., min_length=10, max_length=5000),
    result_sheet_id: str | None = Form(default=None),
    people_present: str | None = Form(default=None, description="JSON array of {name, role, phone}"),
    occurred_at: datetime | None = Form(default=None),
    lat: float | None = Form(default=None, ge=-90, le=90),
    lng: float | None = Form(default=None, ge=-180, le=180),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> WitnessStatementOut:
    if incident_category not in INCIDENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"incident_category must be one of {sorted(INCIDENT_CATEGORIES)}.")

    unit = await _get_owned_unit(code, agent, db)

    people: list[dict[str, Any]] = []
    if people_present:
        try:
            raw_people = json.loads(people_present)
            people = [WitnessPersonPresent(**p).model_dump() for p in raw_people]
        except Exception as exc:
            raise HTTPException(status_code=400, detail="people_present must be a JSON array of {name, role, phone}.") from exc

    from bson import ObjectId
    from bson.errors import InvalidId

    result_sheet_oid = None
    if result_sheet_id:
        try:
            result_sheet_oid = ObjectId(result_sheet_id)
        except InvalidId as exc:
            raise HTTPException(status_code=400, detail="Invalid result_sheet_id.") from exc

    normalized_code = code.lower().strip()
    now = datetime.now(timezone.utc)

    previous = await db[WITNESS_STATEMENTS_COLLECTION].find_one(
        {"code": normalized_code, "agent_id": agent["_id"]}, sort=[("submitted_at", -1)]
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
        "result_sheet_id": result_sheet_oid,
        "incident_category": incident_category,
        "narrative": narrative,
        "people_present": people,
        "occurred_at": occurred_at,
        "submitted_at": now,
        "captured_lat": lat,
        "captured_lng": lng,
        "supersedes_id": previous["_id"] if previous else None,
        "version": version,
    }
    result = await db[WITNESS_STATEMENTS_COLLECTION].insert_one(doc)
    statement_id = str(result.inserted_id)

    narrative_hash = hashlib.sha256(narrative.encode()).hexdigest()
    await hash_ledger.append_entry(
        db, entity_type="witness_statement", entity_id=statement_id, entity_sha256=narrative_hash
    )

    inserted = await db[WITNESS_STATEMENTS_COLLECTION].find_one({"_id": result.inserted_id})
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to read saved witness statement.")
    return _doc_to_out(inserted, agent_name=agent.get("name"))


@agent_router.get("", response_model=list[WitnessStatementOut])
async def list_my_witness_statements(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[WitnessStatementOut]:
    cursor = db[WITNESS_STATEMENTS_COLLECTION].find({"agent_id": agent["_id"]}).sort("submitted_at", -1)
    docs = await cursor.to_list(length=1000)
    return [_doc_to_out(d, agent_name=agent.get("name")) for d in docs]


@admin_router.get("", response_model=list[WitnessStatementOut])
async def admin_list_witness_statements(
    code: str | None = Query(default=None),
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[WitnessStatementOut]:
    from .admin_bootstrap import OGUN_STATE, OSUN_STATE
    from .geo_data import OGUN_LGAS
    from .models import AGENTS_COLLECTION
    from .osun_geo_data import OSUN_LGAS

    query: dict[str, Any] = {}
    state = admin_state(admin)
    if state:
        lgas = list(OGUN_LGAS.keys()) if state == OGUN_STATE else list(OSUN_LGAS.keys()) if state == OSUN_STATE else []
        query = {"$or": [{"state": state}, {"lga": {"$in": lgas}}]} if lgas else {"state": state}
    if code:
        query["code"] = code.lower().strip()

    cursor = db[WITNESS_STATEMENTS_COLLECTION].find(query).sort("submitted_at", -1)
    docs = await cursor.to_list(length=5000)

    agent_ids = {d["agent_id"] for d in docs if d.get("agent_id")}
    agents_by_id: dict[Any, str] = {}
    if agent_ids:
        agent_docs = await db[AGENTS_COLLECTION].find({"_id": {"$in": list(agent_ids)}}).to_list(length=len(agent_ids))
        agents_by_id = {a["_id"]: a.get("name") for a in agent_docs}

    return [_doc_to_out(d, agent_name=agents_by_id.get(d.get("agent_id"))) for d in docs]
