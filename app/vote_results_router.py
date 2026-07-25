from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .auth import get_current_admin, get_current_agent
from .admin_bootstrap import admin_state
from .database import get_db
from .models import POLLING_UNITS_COLLECTION, VOTE_RESULTS_COLLECTION
from .schemas import (
    VotePlaceStat,
    VoteResultOut,
    VoteResultsSummary,
    VoteResultSubmit,
    VoteUnitStat,
)

agent_router = APIRouter(prefix="/agents/me/results", tags=["agent-results"])
admin_router = APIRouter(prefix="/admin/results", tags=["admin-results"])


def _as_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _comparison_note(votes: int, people: int) -> str:
    diff = votes - people
    if people <= 0 and votes <= 0:
        return "No people counted yet and no votes entered."
    if people <= 0:
        return (
            f"{votes:,} vote(s) entered, but no people have been counted at this place yet. "
            "Compare carefully — the people counter may not have run."
        )
    if diff == 0:
        return f"Votes ({votes:,}) match the people counted on site ({people:,})."
    if diff > 0:
        return (
            f"Votes ({votes:,}) are {diff:,} more than people counted on site ({people:,}). "
            "This can happen, but leaders should review it."
        )
    return (
        f"Votes ({votes:,}) are {abs(diff):,} fewer than people counted on site ({people:,}). "
        "Some people on site may not have had their vote counted yet, or counts need review."
    )


def _place_note(label: str, votes: int, people: int) -> str:
    diff = votes - people
    if people <= 0:
        return f"{label}: {votes:,} vote(s). People count not available yet."
    if diff == 0:
        return f"{label}: votes match people counted ({votes:,})."
    if diff > 0:
        return f"{label}: {votes:,} votes vs {people:,} people (+{diff:,} votes)."
    return f"{label}: {votes:,} votes vs {people:,} people ({diff:,} votes)."


def _doc_to_out(doc: dict[str, Any], people_count: int | None = None) -> VoteResultOut:
    people = people_count if people_count is not None else int(doc.get("people_count_at_submit") or 0)
    return VoteResultOut(
        id=str(doc["_id"]),
        polling_unit_id=str(doc["polling_unit_id"]),
        code=doc["code"],
        polling_unit_name=doc.get("polling_unit_name") or doc.get("code") or "",
        state=doc.get("state") or "",
        ward=doc.get("ward") or "",
        lga=doc.get("lga") or "",
        votes=int(doc.get("votes") or 0),
        people_count=people,
        people_count_at_submit=int(doc.get("people_count_at_submit") or 0),
        updated_at=_as_utc(doc.get("updated_at")),
        agent_id=str(doc["agent_id"]) if doc.get("agent_id") else None,
    )


def _build_summary(
    results: list[dict[str, Any]],
    people_by_code: dict[str, int],
) -> VoteResultsSummary:
    unit_stats: list[VoteUnitStat] = []
    for doc in results:
        code = doc["code"]
        votes = int(doc.get("votes") or 0)
        people = int(people_by_code.get(code, doc.get("people_count_at_submit") or 0))
        unit_stats.append(
            VoteUnitStat(
                code=code,
                name=doc.get("polling_unit_name") or code,
                lga=doc.get("lga") or "",
                ward=doc.get("ward") or "",
                state=doc.get("state") or "",
                votes=votes,
                people_count=people,
                difference=votes - people,
                comparison_note=_comparison_note(votes, people),
            )
        )

    unit_stats.sort(key=lambda u: (-u.votes, u.lga, u.ward, u.name))

    lga_map: dict[str, dict[str, int]] = {}
    ward_map: dict[tuple[str, str], dict[str, int]] = {}
    for u in unit_stats:
        lg = lga_map.setdefault(u.lga or "Unknown", {"votes": 0, "people": 0, "units": 0})
        lg["votes"] += u.votes
        lg["people"] += u.people_count
        lg["units"] += 1
        wk = (u.lga or "Unknown", u.ward or "Unknown")
        wd = ward_map.setdefault(wk, {"votes": 0, "people": 0, "units": 0})
        wd["votes"] += u.votes
        wd["people"] += u.people_count
        wd["units"] += 1

    by_lga = [
        VotePlaceStat(
            label=lga,
            lga=lga,
            votes=vals["votes"],
            people_count=vals["people"],
            unit_count=vals["units"],
            difference=vals["votes"] - vals["people"],
            comparison_note=_place_note(lga, vals["votes"], vals["people"]),
        )
        for lga, vals in sorted(lga_map.items(), key=lambda kv: (-kv[1]["votes"], kv[0]))
    ]
    by_ward = [
        VotePlaceStat(
            label=f"{ward}, {lga}",
            lga=lga,
            ward=ward,
            votes=vals["votes"],
            people_count=vals["people"],
            unit_count=vals["units"],
            difference=vals["votes"] - vals["people"],
            comparison_note=_place_note(f"{ward} ({lga})", vals["votes"], vals["people"]),
        )
        for (lga, ward), vals in sorted(ward_map.items(), key=lambda kv: (-kv[1]["votes"], kv[0][0], kv[0][1]))
    ]

    total_votes = sum(u.votes for u in unit_stats)
    total_people = sum(u.people_count for u in unit_stats)
    overall_diff = total_votes - total_people
    overall_note = _comparison_note(total_votes, total_people)

    highest_unit = unit_stats[0] if unit_stats else None
    lowest_unit = min(unit_stats, key=lambda u: (u.votes, u.name)) if unit_stats else None
    highest_lga = by_lga[0] if by_lga else None
    lowest_lga = min(by_lga, key=lambda x: (x.votes, x.label)) if by_lga else None
    highest_ward = by_ward[0] if by_ward else None
    lowest_ward = min(by_ward, key=lambda x: (x.votes, x.label)) if by_ward else None

    if not unit_stats:
        plain = (
            "No vote results have been entered yet. When field agents submit results from their "
            "polling units, totals will appear here and can be compared with people counted on site."
        )
    else:
        parts = [
            f"Altogether, agents have entered {total_votes:,} vote(s) from {len(unit_stats):,} polling unit(s).",
            f"At those same units, the system has counted {total_people:,} people on site.",
        ]
        if overall_diff > 0:
            parts.append(
                f"Overall, votes are {overall_diff:,} higher than people counted. Review the tables below."
            )
        elif overall_diff < 0:
            parts.append(
                f"Overall, votes are {abs(overall_diff):,} lower than people counted. Some results may still be pending."
            )
        else:
            parts.append("Overall, total votes match total people counted at units with results.")
        if highest_unit:
            parts.append(
                f"Highest polling unit: {highest_unit.name} ({highest_unit.ward}, {highest_unit.lga}) "
                f"with {highest_unit.votes:,} votes."
            )
        if lowest_unit:
            parts.append(
                f"Lowest polling unit: {lowest_unit.name} ({lowest_unit.ward}, {lowest_unit.lga}) "
                f"with {lowest_unit.votes:,} votes."
            )
        if highest_lga:
            parts.append(f"Highest LGA: {highest_lga.lga} with {highest_lga.votes:,} votes.")
        if lowest_lga:
            parts.append(f"Lowest LGA: {lowest_lga.lga} with {lowest_lga.votes:,} votes.")
        if highest_ward:
            parts.append(f"Highest ward: {highest_ward.label} with {highest_ward.votes:,} votes.")
        if lowest_ward:
            parts.append(f"Lowest ward: {lowest_ward.label} with {lowest_ward.votes:,} votes.")
        plain = " ".join(parts)

    return VoteResultsSummary(
        total_votes=total_votes,
        units_with_results=len(unit_stats),
        total_people_counted=total_people,
        overall_difference=overall_diff,
        overall_note=overall_note,
        plain_summary=plain,
        by_polling_unit=unit_stats,
        by_lga=by_lga,
        by_ward=by_ward,
        highest_unit=highest_unit,
        lowest_unit=lowest_unit,
        highest_lga=highest_lga,
        lowest_lga=lowest_lga,
        highest_ward=highest_ward,
        lowest_ward=lowest_ward,
    )


@agent_router.get("", response_model=list[VoteResultOut])
async def agent_list_results(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[VoteResultOut]:
    cursor = db[VOTE_RESULTS_COLLECTION].find({"agent_id": agent["_id"]}).sort("updated_at", -1)
    docs = await cursor.to_list(length=500)
    codes = [d["code"] for d in docs]
    people_by_code: dict[str, int] = {}
    if codes:
        unit_cursor = db[POLLING_UNITS_COLLECTION].find({"code": {"$in": codes}})
        for u in await unit_cursor.to_list(length=500):
            people_by_code[u["code"]] = int(u.get("people_count") or 0)
    return [_doc_to_out(d, people_by_code.get(d["code"])) for d in docs]


@agent_router.put("", response_model=VoteResultOut)
async def agent_upsert_result(
    payload: VoteResultSubmit,
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> VoteResultOut:
    code = payload.code.lower().strip()
    unit = await db[POLLING_UNITS_COLLECTION].find_one({"code": code, "agent_id": agent["_id"]})
    if not unit:
        raise HTTPException(
            status_code=404,
            detail="Polling unit not found, or you do not own this unit.",
        )

    now = datetime.now(timezone.utc)
    people = int(unit.get("people_count") or 0)
    doc = {
        "polling_unit_id": unit["_id"],
        "code": code,
        "polling_unit_name": unit.get("name") or code,
        "state": unit.get("state") or "",
        "ward": unit.get("ward") or "",
        "lga": unit.get("lga") or "",
        "agent_id": agent["_id"],
        "votes": int(payload.votes),
        "people_count_at_submit": people,
        "updated_at": now,
    }
    existing = await db[VOTE_RESULTS_COLLECTION].find_one({"code": code})
    if existing:
        await db[VOTE_RESULTS_COLLECTION].update_one({"_id": existing["_id"]}, {"$set": doc})
        saved = await db[VOTE_RESULTS_COLLECTION].find_one({"_id": existing["_id"]})
    else:
        doc["created_at"] = now
        insert = await db[VOTE_RESULTS_COLLECTION].insert_one(doc)
        saved = await db[VOTE_RESULTS_COLLECTION].find_one({"_id": insert.inserted_id})
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to save result.")
    return _doc_to_out(saved, people)


@admin_router.get("/summary", response_model=VoteResultsSummary)
async def admin_results_summary(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> VoteResultsSummary:
    from .admin_bootstrap import OGUN_STATE, OSUN_STATE
    from .geo_data import OGUN_LGAS
    from .osun_geo_data import OSUN_LGAS

    query: dict[str, Any] = {}
    state = admin_state(admin)
    if state:
        lgas = list(OGUN_LGAS.keys()) if state == OGUN_STATE else list(OSUN_LGAS.keys()) if state == OSUN_STATE else []
        if lgas:
            query = {"$or": [{"state": state}, {"lga": {"$in": lgas}}]}
        else:
            query = {"state": state}
    cursor = db[VOTE_RESULTS_COLLECTION].find(query)
    docs = await cursor.to_list(length=5000)
    codes = [d["code"] for d in docs]
    people_by_code: dict[str, int] = {}
    if codes:
        unit_cursor = db[POLLING_UNITS_COLLECTION].find({"code": {"$in": codes}})
        for u in await unit_cursor.to_list(length=5000):
            people_by_code[u["code"]] = int(u.get("people_count") or 0)
    return _build_summary(docs, people_by_code)
