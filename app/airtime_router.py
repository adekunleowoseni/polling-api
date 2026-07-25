from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .app_settings import get_app_settings
from .auth import get_current_agent, require_super_admin
from .database import get_db
from .models import AGENTS_COLLECTION, AIRTIME_CREDITS_COLLECTION, AIRTIME_PLANS_COLLECTION
from .schemas import (
    AirtimeClaimQuotaOut,
    AirtimeCreditOut,
    AirtimeCreditRequest,
    AirtimePlanOut,
    AirtimePlansUpdate,
)
from .vtpass_client import (
    AIRTIME_SERVICE_IDS,
    NETWORK_LABELS,
    make_request_id,
    purchase_airtime,
    vtpass_configured,
)

# Statuses that consume one airtime claim slot (failed does not).
CLAIM_STATUSES = ("delivered", "successful", "success", "pending")

agent_router = APIRouter(prefix="/agents/me/airtime", tags=["agent-airtime"])
admin_router = APIRouter(prefix="/admin/airtime", tags=["admin-airtime"])


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone.strip())
    if digits.startswith("234") and len(digits) == 13:
        digits = "0" + digits[3:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits
    raise HTTPException(status_code=400, detail="Enter a valid Nigerian phone number (e.g. 08012345678).")


def _normalize_network(network: str) -> str:
    key = network.strip().lower().replace(" ", "")
    if key in ("9mobile", "etisalat", "9-mobile"):
        key = "9mobile"
    if key not in AIRTIME_SERVICE_IDS:
        raise HTTPException(status_code=400, detail="Unsupported network. Use mtn, airtel, glo, or 9mobile.")
    return key


async def _claims_used(db: AsyncIOMotorDatabase, agent_id: Any) -> int:
    return await db[AIRTIME_CREDITS_COLLECTION].count_documents(
        {"agent_id": agent_id, "status": {"$in": list(CLAIM_STATUSES)}}
    )


def _claim_limit(agent: dict[str, Any]) -> int:
    try:
        return max(0, int(agent.get("airtime_claim_limit", 1)))
    except (TypeError, ValueError):
        return 1


def _plan_doc_to_out(doc: dict[str, Any]) -> AirtimePlanOut:
    return AirtimePlanOut(
        amount=float(doc.get("amount", 0)),
        enabled=bool(doc.get("enabled", True)),
    )


def _credit_doc_to_out(doc: dict[str, Any], agent: dict[str, Any] | None = None) -> AirtimeCreditOut:
    return AirtimeCreditOut(
        id=str(doc["_id"]),
        phone=doc["phone"],
        network=doc["network"],
        amount=float(doc.get("amount", 0)),
        request_id=doc["request_id"],
        status=doc.get("status") or "unknown",
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
        agent_id=str(doc["agent_id"]) if doc.get("agent_id") else None,
        agent_name=(agent or {}).get("name"),
        agent_email=(agent or {}).get("email"),
    )


# ---------------------------------------------------------------------------
# Admin: manage airtime denominations + view all credits
# ---------------------------------------------------------------------------

@admin_router.get("/status")
async def airtime_status(admin: dict[str, Any] = Depends(require_super_admin)) -> dict[str, Any]:
    _ = admin
    return {"configured": vtpass_configured()}


@admin_router.get("/networks")
async def list_networks(admin: dict[str, Any] = Depends(require_super_admin)) -> list[dict[str, str]]:
    _ = admin
    return [
        {"id": k, "label": NETWORK_LABELS.get(k, k.upper()), "service_id": v}
        for k, v in AIRTIME_SERVICE_IDS.items()
    ]


@admin_router.get("/amounts", response_model=list[AirtimePlanOut])
async def list_amounts(
    admin: dict[str, Any] = Depends(require_super_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[AirtimePlanOut]:
    _ = admin
    cursor = db[AIRTIME_PLANS_COLLECTION].find().sort("amount", 1)
    docs = await cursor.to_list(length=500)
    return [_plan_doc_to_out(d) for d in docs]


@admin_router.put("/amounts", response_model=list[AirtimePlanOut])
async def save_amounts(
    payload: AirtimePlansUpdate,
    admin: dict[str, Any] = Depends(require_super_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[AirtimePlanOut]:
    _ = admin
    now = datetime.now(timezone.utc)
    # Deduplicate by amount, keep last occurrence.
    by_amount: dict[float, bool] = {}
    for item in payload.plans:
        by_amount[float(item.amount)] = bool(item.enabled)

    await db[AIRTIME_PLANS_COLLECTION].delete_many({})
    docs = [
        {"amount": amount, "enabled": enabled, "updated_at": now}
        for amount, enabled in sorted(by_amount.items())
    ]
    if docs:
        await db[AIRTIME_PLANS_COLLECTION].insert_many(docs)
    return [_plan_doc_to_out(d) for d in docs]


@admin_router.get("/credits", response_model=list[AirtimeCreditOut])
async def admin_list_credits(
    admin: dict[str, Any] = Depends(require_super_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[AirtimeCreditOut]:
    _ = admin
    cursor = db[AIRTIME_CREDITS_COLLECTION].find().sort("created_at", -1).limit(200)
    docs = await cursor.to_list(length=200)
    agent_ids = {d["agent_id"] for d in docs if d.get("agent_id")}
    agents: dict[Any, dict[str, Any]] = {}
    if agent_ids:
        agent_cursor = db[AGENTS_COLLECTION].find({"_id": {"$in": list(agent_ids)}})
        for a in await agent_cursor.to_list(length=500):
            agents[a["_id"]] = a
    return [_credit_doc_to_out(d, agents.get(d.get("agent_id"))) for d in docs]


# ---------------------------------------------------------------------------
# Agent: quota, allowed amounts, history, purchase
# ---------------------------------------------------------------------------

@agent_router.get("/quota", response_model=AirtimeClaimQuotaOut)
async def agent_airtime_quota(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AirtimeClaimQuotaOut:
    limit = _claim_limit(agent)
    used = await _claims_used(db, agent["_id"])
    return AirtimeClaimQuotaOut(
        airtime_claim_limit=limit,
        airtime_claims_used=used,
        airtime_claims_remaining=max(0, limit - used),
    )


@agent_router.get("/amounts", response_model=list[AirtimePlanOut])
async def agent_enabled_amounts(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[AirtimePlanOut]:
    _ = agent
    cursor = db[AIRTIME_PLANS_COLLECTION].find({"enabled": True}).sort("amount", 1)
    docs = await cursor.to_list(length=200)
    return [_plan_doc_to_out(d) for d in docs]


@agent_router.get("/credits", response_model=list[AirtimeCreditOut])
async def agent_credit_history(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[AirtimeCreditOut]:
    cursor = (
        db[AIRTIME_CREDITS_COLLECTION]
        .find({"agent_id": agent["_id"]})
        .sort("created_at", -1)
        .limit(50)
    )
    docs = await cursor.to_list(length=50)
    return [_credit_doc_to_out(d, agent) for d in docs]


@agent_router.post("/credit", response_model=AirtimeCreditOut)
async def credit_agent_airtime(
    payload: AirtimeCreditRequest,
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AirtimeCreditOut:
    if not vtpass_configured():
        raise HTTPException(status_code=503, detail="Airtime is not configured. Contact admin.")

    limit = _claim_limit(agent)
    used = await _claims_used(db, agent["_id"])
    if used >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"You have used all airtime claims ({used}/{limit}). "
                "Ask admin to increase your claim allowance."
            ),
        )

    phone = _normalize_phone(payload.phone)
    network = _normalize_network(payload.network)
    amount = float(payload.amount)

    settings_doc = await get_app_settings(db)
    if settings_doc.get("strict_one_airtime_claim_per_phone"):
        existing = await db[AIRTIME_CREDITS_COLLECTION].find_one(
            {"phone": phone, "status": {"$in": list(CLAIM_STATUSES)}}
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="This phone number has already claimed airtime. Each number can claim only once.",
            )

    denom = await db[AIRTIME_PLANS_COLLECTION].find_one({"amount": amount, "enabled": True})
    if not denom:
        raise HTTPException(
            status_code=400,
            detail="This airtime amount is not enabled by admin. Choose an allowed amount.",
        )

    service_id = AIRTIME_SERVICE_IDS[network]
    request_id = make_request_id()
    now = datetime.now(timezone.utc)
    credit_doc: dict[str, Any] = {
        "agent_id": agent["_id"],
        "phone": phone,
        "network": network,
        "service_id": service_id,
        "amount": amount,
        "request_id": request_id,
        "status": "pending",
        "vtpass_code": None,
        "vtpass_response": None,
        "created_at": now,
    }
    insert = await db[AIRTIME_CREDITS_COLLECTION].insert_one(credit_doc)

    try:
        vt_res = await purchase_airtime(
            service_id=service_id,
            phone=phone,
            amount=amount,
            request_id=request_id,
        )
    except Exception as exc:
        await db[AIRTIME_CREDITS_COLLECTION].update_one(
            {"_id": insert.inserted_id},
            {"$set": {"status": "failed", "vtpass_response": {"error": str(exc)}}},
        )
        raise HTTPException(status_code=502, detail=f"VTpass request failed: {exc}") from exc

    code = str(vt_res.get("code") or "")
    tx = (vt_res.get("content") or {}).get("transactions") or {}
    tx_status = str(tx.get("status") or "").lower()
    if code == "000" and tx_status in {"delivered", "successful", "success", ""}:
        status = "delivered"
    elif code == "000":
        status = tx_status or "successful"
    elif code in {"099", "001"}:
        status = "pending"
    else:
        status = "failed"

    await db[AIRTIME_CREDITS_COLLECTION].update_one(
        {"_id": insert.inserted_id},
        {"$set": {"status": status, "vtpass_code": code, "vtpass_response": vt_res}},
    )
    updated = await db[AIRTIME_CREDITS_COLLECTION].find_one({"_id": insert.inserted_id})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read airtime record.")

    if status == "failed":
        detail = vt_res.get("response_description") or "Airtime top-up failed."
        raise HTTPException(status_code=400, detail=str(detail))

    return _credit_doc_to_out(updated, agent)
