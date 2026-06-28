from __future__ import annotations



from datetime import datetime, timezone

from typing import Any



from fastapi import APIRouter, Depends, HTTPException

from motor.motor_asyncio import AsyncIOMotorDatabase



from .agent_helpers import agent_doc_to_out

from .auth import get_current_agent, hash_password, new_api_token, verify_password

from .database import get_db

from .geo_data import validate_ogun_ward

from .models import AGENTS_COLLECTION

from .polling_units_router import _doc_to_out

from .schemas import AgentLogin, AgentOut, AgentPollingUnitOut, AgentRegister, AgentSessionOut



router = APIRouter(prefix="/agents", tags=["agents"])





@router.post("/register", response_model=AgentSessionOut, status_code=201)

async def register_agent(

    payload: AgentRegister,

    db: AsyncIOMotorDatabase = Depends(get_db),

) -> AgentSessionOut:

    email = payload.email.lower().strip()

    existing = await db[AGENTS_COLLECTION].find_one({"email": email})

    if existing:

        raise HTTPException(status_code=409, detail="An agent with this email already exists.")



    lga = payload.lga.strip()

    ward = payload.ward.strip()

    validate_ogun_ward(lga, ward)



    now = datetime.now(timezone.utc)

    api_token = new_api_token()

    doc = {

        "name": payload.name.strip(),

        "email": email,

        "password_hash": hash_password(payload.password),

        "api_token": api_token,

        "lga": lga,

        "ward": ward,

        "created_at": now,

    }

    result = await db[AGENTS_COLLECTION].insert_one(doc)

    inserted = await db[AGENTS_COLLECTION].find_one({"_id": result.inserted_id})

    if not inserted:

        raise HTTPException(status_code=500, detail="Failed to create agent account.")



    return AgentSessionOut(agent=agent_doc_to_out(inserted), api_token=api_token)





@router.post("/login", response_model=AgentSessionOut)

async def login_agent(

    payload: AgentLogin,

    db: AsyncIOMotorDatabase = Depends(get_db),

) -> AgentSessionOut:

    email = payload.email.lower().strip()

    agent = await db[AGENTS_COLLECTION].find_one({"email": email})

    if not agent or not verify_password(payload.password, agent["password_hash"]):

        raise HTTPException(status_code=401, detail="Invalid email or password.")



    return AgentSessionOut(agent=agent_doc_to_out(agent), api_token=agent["api_token"])





@router.get("/me", response_model=AgentOut)

async def get_me(agent: dict[str, Any] = Depends(get_current_agent)) -> AgentOut:

    return agent_doc_to_out(agent)





@router.get("/me/polling-units", response_model=list[AgentPollingUnitOut])
async def list_my_polling_units(
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from .models import POLLING_UNITS_COLLECTION

    cursor = (
        db[POLLING_UNITS_COLLECTION]
        .find({"agent_id": agent["_id"]})
        .sort("created_at", -1)
    )
    docs = await cursor.to_list(length=500)
    return [
        AgentPollingUnitOut(
            **_doc_to_out(d).model_dump(),
            ingest_token=d.get("ingest_token", ""),
        )
        for d in docs
    ]


