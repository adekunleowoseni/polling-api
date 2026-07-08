from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from livekit import api
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from .auth import get_current_agent
from .database import get_db
from .feed_manager import feed_manager
from .models import POLLING_UNITS_COLLECTION
from .recordings import finalize_recording
from .settings import settings

router = APIRouter(prefix="/webrtc", tags=["webrtc"])


class TokenRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class TokenResponse(BaseModel):
    enabled: bool
    url: str
    token: str
    room: str
    identity: str
    role: Literal["publisher", "viewer"]


def _room_name(code: str) -> str:
    return f"pu-{code.lower()}"


def _livekit_configured() -> bool:
    return bool(settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret)


def _mint_token(*, identity: str, name: str, room: str, can_publish: bool) -> str:
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=can_publish,
        can_subscribe=True,
        can_publish_data=can_publish,
    )
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .to_jwt()
    )


@router.get("/config")
async def webrtc_config() -> dict[str, Any]:
    return {
        "enabled": _livekit_configured(),
        "url": settings.livekit_url if _livekit_configured() else "",
    }


@router.post("/publisher-token", response_model=TokenResponse)
async def publisher_token(
    payload: TokenRequest,
    x_ingest_token: str = Header(..., alias="X-Ingest-Token"),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenResponse:
    if not _livekit_configured():
        raise HTTPException(status_code=503, detail="WebRTC is not configured on this server.")

    code = payload.code.lower().strip()
    doc = await db[POLLING_UNITS_COLLECTION].find_one({"code": code})
    if not doc:
        raise HTTPException(status_code=404, detail="Polling unit not found.")
    if str(doc.get("agent_id")) != str(agent["_id"]):
        raise HTTPException(status_code=403, detail="You do not own this polling unit.")
    if x_ingest_token != doc.get("ingest_token"):
        raise HTTPException(status_code=401, detail="Invalid ingest token.")

    room = _room_name(code)
    identity = f"agent-{agent['_id']}-{code}"
    token = _mint_token(
        identity=identity,
        name=str(agent.get("name") or "Agent"),
        room=room,
        can_publish=True,
    )
    return TokenResponse(
        enabled=True,
        url=settings.livekit_url,
        token=token,
        room=room,
        identity=identity,
        role="publisher",
    )


@router.post("/viewer-token", response_model=TokenResponse)
async def viewer_token(payload: TokenRequest) -> TokenResponse:
    if not _livekit_configured():
        raise HTTPException(status_code=503, detail="WebRTC is not configured on this server.")

    code = payload.code.lower().strip()
    room = _room_name(code)
    identity = f"viewer-{secrets.token_hex(8)}"
    token = _mint_token(
        identity=identity,
        name="Viewer",
        room=room,
        can_publish=False,
    )
    return TokenResponse(
        enabled=True,
        url=settings.livekit_url,
        token=token,
        room=room,
        identity=identity,
        role="viewer",
    )


@router.post("/{code}/start")
async def start_webrtc_stream(
    code: str,
    x_ingest_token: str = Header(..., alias="X-Ingest-Token"),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    code = code.lower().strip()
    doc = await db[POLLING_UNITS_COLLECTION].find_one({"code": code})
    if not doc:
        raise HTTPException(status_code=404, detail="Polling unit not found.")
    if str(doc.get("agent_id")) != str(agent["_id"]):
        raise HTTPException(status_code=403, detail="You do not own this polling unit.")
    if x_ingest_token != doc.get("ingest_token"):
        raise HTTPException(status_code=401, detail="Invalid ingest token.")

    now = datetime.now(timezone.utc)
    await db[POLLING_UNITS_COLLECTION].update_one(
        {"_id": doc["_id"]},
        {"$set": {"last_frame_at": now, "webrtc_live": True}},
    )
    await feed_manager.update_people_count(
        code,
        int(doc.get("people_count", 0)),
        stream_status="live",
    )
    return {"status": "live", "code": code, "last_frame_at": now.isoformat()}


@router.post("/{code}/stop")
async def stop_webrtc_stream(
    code: str,
    x_ingest_token: str = Header(..., alias="X-Ingest-Token"),
    agent: dict[str, Any] = Depends(get_current_agent),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    code = code.lower().strip()
    doc = await db[POLLING_UNITS_COLLECTION].find_one({"code": code})
    if not doc:
        raise HTTPException(status_code=404, detail="Polling unit not found.")
    if str(doc.get("agent_id")) != str(agent["_id"]):
        raise HTTPException(status_code=403, detail="You do not own this polling unit.")
    if x_ingest_token != doc.get("ingest_token"):
        raise HTTPException(status_code=401, detail="Invalid ingest token.")

    await db[POLLING_UNITS_COLLECTION].update_one(
        {"_id": doc["_id"]},
        {"$set": {"last_frame_at": None, "webrtc_live": False}},
    )
    await feed_manager.clear_frame(code)
    await finalize_recording(db, code)
    return {"status": "offline", "code": code}
