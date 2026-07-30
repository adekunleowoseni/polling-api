from __future__ import annotations



from datetime import datetime, timezone

from typing import Any



import hashlib

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from motor.motor_asyncio import AsyncIOMotorDatabase



from .accreditation_storage import accreditation_file_path, ensure_accreditation_dir

from .agent_helpers import agent_doc_to_out

from .auth import get_current_agent, hash_password, new_api_token, verify_password

from .database import get_db

from .geo_data import OGUN_LGAS, validate_ogun_ward
from .osun_geo_data import OSUN_LGAS, validate_osun_ward

from .models import AGENTS_COLLECTION

from .polling_units_router import _doc_to_out

from .schemas import (
    AccreditationOut,
    AgentLogin,
    AgentOut,
    AgentPollingUnitOut,
    AgentRegister,
    AgentSessionOut,
)
from datetime import datetime, timezone



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

    if lga in OGUN_LGAS:
        validate_ogun_ward(lga, ward)
    elif lga in OSUN_LGAS:
        validate_osun_ward(lga, ward)
    else:
        raise HTTPException(status_code=400, detail="Invalid LGA for Ogun or Osun State.")



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

        "accreditation_status": "none",

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


def _accreditation_out(doc: dict) -> AccreditationOut:
    return AccreditationOut(
        accreditation_status=doc.get("accreditation_status") or "none",
        accreditation_number=doc.get("accreditation_number"),
        party_name=doc.get("party_name"),
        is_ec8a_signatory=doc.get("is_ec8a_signatory"),
        submitted_at=doc.get("submitted_at"),
        reviewed_at=doc.get("reviewed_at"),
        rejection_reason=doc.get("rejection_reason"),
        has_document=bool(doc.get("accreditation_doc_filename")),
    )


@router.get("/me/accreditation", response_model=AccreditationOut)
async def get_my_accreditation(agent: dict = Depends(get_current_agent)) -> AccreditationOut:
    return _accreditation_out(agent)


@router.post("/me/accreditation", response_model=AccreditationOut, status_code=201)
async def submit_my_accreditation(
    accreditation_number: str | None = None,
    party_name: str | None = None,
    is_ec8a_signatory: bool = False,
    document: UploadFile = File(...),
    agent: dict = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AccreditationOut:
    if document.content_type not in {"image/jpeg", "image/png", "image/jpg", "application/pdf"}:
        raise HTTPException(status_code=400, detail="Accreditation document must be a JPEG, PNG, or PDF.")

    raw = await document.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty document.")

    agent_id = str(agent["_id"])
    ext_by_type = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg"}
    ext = ext_by_type[document.content_type]
    sha256 = hashlib.sha256(raw).hexdigest()

    ensure_accreditation_dir()
    accreditation_file_path(agent_id, ext).write_bytes(raw)

    now = datetime.now(timezone.utc)
    await db[AGENTS_COLLECTION].update_one(
        {"_id": agent["_id"]},
        {
            "$set": {
                "accreditation_status": "pending",
                "accreditation_doc_filename": f"{agent_id}.{ext}",
                "accreditation_doc_sha256": sha256,
                "accreditation_number": accreditation_number,
                "party_name": party_name,
                "is_ec8a_signatory": is_ec8a_signatory,
                "submitted_at": now,
                "reviewed_by": None,
                "reviewed_at": None,
                "rejection_reason": None,
            }
        },
    )
    updated = await db[AGENTS_COLLECTION].find_one({"_id": agent["_id"]})
    return _accreditation_out(updated or {})


