from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .auth import get_current_admin, get_current_agent
from .database import get_db
from .models import AGENTS_COLLECTION, DATA_CREDITS_COLLECTION, DATA_PLANS_COLLECTION
from .schemas import (
    DataClaimQuotaOut,
    DataCreditOut,
    DataCreditRequest,
    DataPlanOut,
    DataPlansUpdate,
)
from .vtpass_client import (
    NETWORK_LABELS,
    NETWORK_SERVICE_IDS,
    fetch_variations,
    make_request_id,
    purchase_data,
    vtpass_configured,
)

# Statuses that consume one claim slot (failed does not).
CLAIM_STATUSES = ("delivered", "successful", "success", "pending")


async def _claims_used(db: AsyncIOMotorDatabase, agent_id: Any) -> int:
    return await db[DATA_CREDITS_COLLECTION].count_documents(
        {"agent_id": agent_id, "status": {"$in": list(CLAIM_STATUSES)}}
    )


def _claim_limit(agent: dict[str, Any]) -> int:
    try:
        return max(0, int(agent.get("data_claim_limit", 1)))
    except (TypeError, ValueError):
        return 1

agent_router = APIRouter(prefix="/agents/me/data", tags=["agent-data"])
admin_router = APIRouter(prefix="/admin/data", tags=["admin-data"])


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
    if key not in NETWORK_SERVICE_IDS:
        raise HTTPException(status_code=400, detail="Unsupported network. Use mtn, airtel, glo, or 9mobile.")
    return key


def _plan_doc_to_out(doc: dict[str, Any]) -> DataPlanOut:
    return DataPlanOut(
        network=doc["network"],
        service_id=doc["service_id"],
        variation_code=doc["variation_code"],
        name=doc["name"],
        amount=float(doc.get("amount", 0)),
        enabled=bool(doc.get("enabled", True)),
    )


def _credit_doc_to_out(doc: dict[str, Any], agent: dict[str, Any] | None = None) -> DataCreditOut:
    return DataCreditOut(
        id=str(doc["_id"]),
        phone=doc["phone"],
        network=doc["network"],
        plan_name=doc.get("plan_name") or doc.get("variation_code") or "",
        variation_code=doc["variation_code"],
        amount=float(doc.get("amount", 0)),
        request_id=doc["request_id"],
        status=doc.get("status") or "unknown",
        created_at=_as_utc(doc["created_at"]) or doc["created_at"],
        agent_id=str(doc["agent_id"]) if doc.get("agent_id") else None,
        agent_name=(agent or {}).get("name"),
        agent_email=(agent or {}).get("email"),
    )


@admin_router.get("/networks")
async def list_networks(admin: dict[str, Any] = Depends(get_current_admin)) -> list[dict[str, str]]:
    _ = admin
    return [{"id": k, "label": v, "service_id": NETWORK_SERVICE_IDS[k]} for k, v in NETWORK_LABELS.items()]


@admin_router.get("/catalog/{network}", response_model=list[DataPlanOut])
async def catalog_for_network(
    network: str,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> list[DataPlanOut]:
    _ = admin
    if not vtpass_configured():
        raise HTTPException(status_code=503, detail="VTpass is not configured on this server.")
    net = _normalize_network(network)
    service_id = NETWORK_SERVICE_IDS[net]
    try:
        variations = await fetch_variations(service_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load plans from VTpass: {exc}") from exc

    return [
        DataPlanOut(
            network=net,
            service_id=service_id,
            variation_code=v["variation_code"],
            name=v["name"],
            amount=float(v["amount"]),
            enabled=False,
        )
        for v in variations
    ]


@admin_router.get("/plans", response_model=list[DataPlanOut])
async def list_enabled_plans(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[DataPlanOut]:
    _ = admin
    cursor = db[DATA_PLANS_COLLECTION].find().sort([("network", 1), ("amount", 1)])
    docs = await cursor.to_list(length=500)
    return [_plan_doc_to_out(d) for d in docs]


@admin_router.put("/plans", response_model=list[DataPlanOut])
async def save_enabled_plans(
    payload: DataPlansUpdate,
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[DataPlanOut]:
    _ = admin
    now = datetime.now(timezone.utc)
    await db[DATA_PLANS_COLLECTION].delete_many({})
    docs: list[dict[str, Any]] = []
    for item in payload.plans:
        net = _normalize_network(item.network)
        docs.append(
            {
                "network": net,
                "service_id": NETWORK_SERVICE_IDS[net],
                "variation_code": item.variation_code.strip(),
                "name": item.name.strip(),
                "amount": float(item.amount),
                "enabled": bool(item.enabled),
                "updated_at": now,
            }
        )
    if docs:
        await db[DATA_PLANS_COLLECTION].insert_many(docs)
    return [_plan_doc_to_out(d) for d in docs]


@admin_router.get("/credits", response_model=list[DataCreditOut])
async def admin_list_credits(
    admin: dict[str, Any] = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[DataCreditOut]:
    _ = admin
    cursor = db[DATA_CREDITS_COLLECTION].find().sort("created_at", -1).limit(200)
    docs = await cursor.to_list(length=200)
    agent_ids = {d["agent_id"] for d in docs if d.get("agent_id")}
    agents: dict[Any, dict[str, Any]] = {}
    if agent_ids:
        agent_cursor = db[AGENTS_COLLECTION].find({"_id": {"$in": list(agent_ids)}})
        for a in await agent_cursor.to_list(length=500):
            agents[a["_id"]] = a
    return [_credit_doc_to_out(d, agents.get(d.get("agent_id"))) for d in docs]


@admin_router.get("/status")
async def vtpass_status(admin: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    _ = admin
    return {"configured": vtpass_configured()}


@agent_router.get("/quota", response_model=DataClaimQuotaOut)
async def agent_data_quota(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> DataClaimQuotaOut:
    limit = _claim_limit(agent)
    used = await _claims_used(db, agent["_id"])
    return DataClaimQuotaOut(
        data_claim_limit=limit,
        data_claims_used=used,
        data_claims_remaining=max(0, limit - used),
    )


@agent_router.get("/plans", response_model=list[DataPlanOut])
async def agent_enabled_plans(
    network: str | None = None,
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[DataPlanOut]:
    _ = agent
    query: dict[str, Any] = {"enabled": True}
    if network:
        query["network"] = _normalize_network(network)
    cursor = db[DATA_PLANS_COLLECTION].find(query).sort([("network", 1), ("amount", 1)])
    docs = await cursor.to_list(length=200)
    return [_plan_doc_to_out(d) for d in docs]


@agent_router.get("/credits", response_model=list[DataCreditOut])
async def agent_credit_history(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[DataCreditOut]:
    cursor = (
        db[DATA_CREDITS_COLLECTION]
        .find({"agent_id": agent["_id"]})
        .sort("created_at", -1)
        .limit(50)
    )
    docs = await cursor.to_list(length=50)
    return [_credit_doc_to_out(d, agent) for d in docs]


@agent_router.post("/credit", response_model=DataCreditOut)
async def credit_agent_data(
    payload: DataCreditRequest,
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> DataCreditOut:
    if not vtpass_configured():
        raise HTTPException(status_code=503, detail="Data credit is not configured. Contact admin.")

    limit = _claim_limit(agent)
    used = await _claims_used(db, agent["_id"])
    if used >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"You have used all data claims ({used}/{limit}). "
                "Ask admin to increase your claim allowance."
            ),
        )

    phone = _normalize_phone(payload.phone)
    network = _normalize_network(payload.network)
    variation_code = payload.variation_code.strip()

    plan = await db[DATA_PLANS_COLLECTION].find_one(
        {
            "network": network,
            "variation_code": variation_code,
            "enabled": True,
        }
    )
    if not plan:
        raise HTTPException(
            status_code=400,
            detail="This data plan is not enabled by admin. Choose an allowed plan.",
        )

    request_id = make_request_id()
    now = datetime.now(timezone.utc)
    credit_doc: dict[str, Any] = {
        "agent_id": agent["_id"],
        "phone": phone,
        "network": network,
        "service_id": plan["service_id"],
        "variation_code": variation_code,
        "plan_name": plan["name"],
        "amount": float(plan["amount"]),
        "request_id": request_id,
        "status": "pending",
        "vtpass_code": None,
        "vtpass_response": None,
        "created_at": now,
    }
    insert = await db[DATA_CREDITS_COLLECTION].insert_one(credit_doc)

    try:
        vt_res = await purchase_data(
            service_id=plan["service_id"],
            variation_code=variation_code,
            phone=phone,
            amount=float(plan["amount"]),
            request_id=request_id,
        )
    except Exception as exc:
        await db[DATA_CREDITS_COLLECTION].update_one(
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

    await db[DATA_CREDITS_COLLECTION].update_one(
        {"_id": insert.inserted_id},
        {
            "$set": {
                "status": status,
                "vtpass_code": code,
                "vtpass_response": vt_res,
            }
        },
    )
    updated = await db[DATA_CREDITS_COLLECTION].find_one({"_id": insert.inserted_id})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read credit record.")

    if status == "failed":
        detail = vt_res.get("response_description") or "Data credit failed."
        raise HTTPException(status_code=400, detail=str(detail))

    return _credit_doc_to_out(updated, agent)
