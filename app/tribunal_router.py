from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .admin_bootstrap import admin_state
from .auth import get_current_admin
from .database import get_db
from .models import RESULT_SHEETS_COLLECTION, WITNESS_STATEMENTS_COLLECTION
from .result_sheets_router import _doc_to_out as _result_sheet_to_out
from .schemas import FlaggedUnitOut, TribunalReportOut
from .witness_statements_router import _doc_to_out as _witness_statement_to_out

router = APIRouter(prefix="/admin", tags=["admin-tribunal"])


def _state_scope_query(admin: dict[str, Any]) -> dict[str, Any]:
    from .admin_bootstrap import OGUN_STATE, OSUN_STATE
    from .geo_data import OGUN_LGAS
    from .osun_geo_data import OSUN_LGAS

    state = admin_state(admin)
    if not state:
        return {}
    lgas = list(OGUN_LGAS.keys()) if state == OGUN_STATE else list(OSUN_LGAS.keys()) if state == OSUN_STATE else []
    return {"$or": [{"state": state}, {"lga": {"$in": lgas}}]} if lgas else {"state": state}


def _irregularities(latest: dict[str, Any], witness_count_by_category: dict[str, int]) -> list[str]:
    notes: list[str] = []
    votes = int(latest.get("votes") or 0)
    accredited = latest.get("accredited_voters")
    official = latest.get("official_votes")
    external_votes = latest.get("external_pvt_votes")

    if accredited is not None and votes > int(accredited):
        notes.append(f"Over-voting: {votes:,} votes recorded against {int(accredited):,} accredited voters.")
    if official is not None and votes != int(official):
        notes.append(f"Figure mismatch: agent recorded {votes:,}, official figure shows {int(official):,}.")
    if latest.get("irev_image_uploaded") is False:
        notes.append("No result-sheet image found on IReV for this unit at last check.")
    if external_votes is not None and votes != int(external_votes):
        source = latest.get("external_pvt_source") or "external PVT"
        notes.append(f"Figure differs from {source}: agent recorded {votes:,}, {source} shows {int(external_votes):,}.")
    for category, count in witness_count_by_category.items():
        if category == "other":
            continue
        notes.append(f"{count} witness statement(s) reporting {category.replace('_', ' ')}.")
    return notes


@router.get("/polling-units/{code}/tribunal-report", response_model=TribunalReportOut)
async def get_tribunal_report(
    code: str,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TribunalReportOut:
    normalized_code = code.lower().strip()

    cursor = db[RESULT_SHEETS_COLLECTION].find({"code": normalized_code}).sort("created_at", -1)
    result_sheet_docs = await cursor.to_list(length=1000)
    if not result_sheet_docs:
        raise HTTPException(status_code=404, detail="No result sheets found for this polling unit.")

    latest = result_sheet_docs[0]

    witness_pipeline = [
        {"$match": {"code": normalized_code}},
        {"$sort": {"submitted_at": -1}},
        {"$group": {"_id": "$agent_id", "doc": {"$first": "$$ROOT"}}},
    ]
    witness_rows = await db[WITNESS_STATEMENTS_COLLECTION].aggregate(witness_pipeline).to_list(length=1000)
    witness_docs = [row["doc"] for row in witness_rows]

    from .models import AGENTS_COLLECTION

    agent_ids = {d["agent_id"] for d in witness_docs if d.get("agent_id")}
    agents_by_id: dict[Any, str] = {}
    if agent_ids:
        agent_docs = await db[AGENTS_COLLECTION].find({"_id": {"$in": list(agent_ids)}}).to_list(length=len(agent_ids))
        agents_by_id = {a["_id"]: a.get("name") for a in agent_docs}

    witness_count_by_category: dict[str, int] = {}
    for d in witness_docs:
        cat = d.get("incident_category") or "other"
        witness_count_by_category[cat] = witness_count_by_category.get(cat, 0) + 1

    return TribunalReportOut(
        code=normalized_code,
        polling_unit_name=latest.get("polling_unit_name") or normalized_code,
        state=latest.get("state") or "",
        ward=latest.get("ward") or "",
        lga=latest.get("lga") or "",
        registered_voters=latest.get("registered_voters"),
        accredited_voters=latest.get("accredited_voters"),
        agent_votes=int(latest.get("votes") or 0),
        official_votes=latest.get("official_votes"),
        official_source=latest.get("official_source"),
        irev_image_uploaded=latest.get("irev_image_uploaded"),
        external_pvt_source=latest.get("external_pvt_source"),
        external_pvt_votes=latest.get("external_pvt_votes"),
        result_sheets=[_result_sheet_to_out(d) for d in result_sheet_docs],
        witness_statements=[_witness_statement_to_out(d, agent_name=agents_by_id.get(d.get("agent_id"))) for d in witness_docs],
        irregularity_summary=_irregularities(latest, witness_count_by_category),
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/tribunal-reports/flagged", response_model=list[FlaggedUnitOut])
async def list_flagged_units(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[FlaggedUnitOut]:
    query = _state_scope_query(admin)
    pipeline: list[dict[str, Any]] = []
    if query:
        pipeline.append({"$match": query})
    pipeline += [
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$code", "doc": {"$first": "$$ROOT"}}},
    ]
    rows = await db[RESULT_SHEETS_COLLECTION].aggregate(pipeline).to_list(length=5000)

    flagged: list[FlaggedUnitOut] = []
    for row in rows:
        doc = row["doc"]
        flags: list[str] = []
        votes = int(doc.get("votes") or 0)
        accredited = doc.get("accredited_voters")
        official = doc.get("official_votes")

        if accredited is not None and votes > int(accredited):
            flags.append("over_voting")
        if official is not None and votes != int(official):
            flags.append("figure_mismatch")
        if doc.get("irev_image_uploaded") is False:
            flags.append("irev_missing")

        if flags:
            flagged.append(
                FlaggedUnitOut(
                    code=doc["code"],
                    polling_unit_name=doc.get("polling_unit_name") or doc["code"],
                    state=doc.get("state") or "",
                    ward=doc.get("ward") or "",
                    lga=doc.get("lga") or "",
                    flags=flags,
                    severity=len(flags),
                )
            )

    flagged.sort(key=lambda f: (-f.severity, f.state, f.lga, f.ward))
    return flagged
