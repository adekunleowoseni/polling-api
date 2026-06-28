from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase

from .ai_extractor import extract_with_document_ai
from .database import get_database, get_db
from .feed_manager import feed_manager
from .models import POLLING_UNITS_COLLECTION, REGISTRATIONS_COLLECTION
from .admin_bootstrap import ensure_super_admin
from .admin_router import router as admin_router
from .agents_router import router as agents_router
from .migrate import ensure_schema
from .feed_snap_storage import ensure_snaps_dir
from .feed_snaps_router import router as feed_snaps_router
from .geo_router import router as geo_router
from .polling_units_router import router as polling_units_router
from .schemas import (
    DailyTrend,
    LiveActivity,
    LiveDashboard,
    PollingUnitStat,
    RegistrationCreate,
    RegistrationOut,
    VideoFeedDashboard,
)
from .settings import settings

app = FastAPI(title="Registration Scanner API")

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(polling_units_router)
app.include_router(agents_router)
app.include_router(admin_router)
app.include_router(geo_router)
app.include_router(feed_snaps_router)


@app.on_event("startup")
async def on_startup() -> None:
    ensure_snaps_dir()
    db = get_database()
    await ensure_schema(db)
    await ensure_super_admin(db)


def _doc_to_out(doc: dict[str, Any]) -> RegistrationOut:
    return RegistrationOut(
        id=str(doc["_id"]),
        name=doc.get("name"),
        phone=doc.get("phone"),
        email=doc.get("email"),
        ward=doc.get("ward"),
        lga=doc.get("lga"),
        polling_unit=doc.get("polling_unit"),
        address=doc.get("address"),
        form_date=doc.get("form_date"),
        raw_ai_output=doc.get("raw_ai_output") or {},
        created_at=doc["created_at"],
    )


def validate_document_ai_config() -> None:
    if not (
        settings.google_cloud_project_id
        and settings.google_cloud_location
        and settings.google_documentai_processor_id
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "Document AI is not configured. Set GOOGLE_CLOUD_PROJECT_ID, "
                "GOOGLE_CLOUD_LOCATION, and GOOGLE_DOCUMENTAI_PROCESSOR_ID."
            ),
        )


@app.post("/upload-form", response_model=RegistrationOut)
async def upload_form(
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> RegistrationOut:
    if file.content_type not in {"image/jpeg", "image/png", "application/pdf"}:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, or PDF files are allowed.")

    validate_document_ai_config()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    parsed_fields, raw_output = extract_with_document_ai(content, file.content_type)
    payload = RegistrationCreate(**parsed_fields, raw_ai_output=raw_output)

    doc = {
        "name": payload.name,
        "phone": payload.phone,
        "email": str(payload.email) if payload.email is not None else None,
        "ward": payload.ward,
        "lga": payload.lga,
        "polling_unit": payload.polling_unit,
        "address": payload.address,
        "form_date": payload.form_date,
        "raw_ai_output": payload.raw_ai_output,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db[REGISTRATIONS_COLLECTION].insert_one(doc)
    inserted = await db[REGISTRATIONS_COLLECTION].find_one({"_id": result.inserted_id})
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to read inserted document.")
    return _doc_to_out(inserted)


@app.get("/registrations", response_model=list[RegistrationOut])
async def list_registrations(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[RegistrationOut]:
    cursor = db[REGISTRATIONS_COLLECTION].find().sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return [_doc_to_out(d) for d in docs]


@app.get("/analytics/trends", response_model=list[DailyTrend])
async def registration_trends(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[DailyTrend]:
    pipeline: list[dict[str, Any]] = [
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at", "timezone": "UTC"},
                },
                "total": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    rows = await db[REGISTRATIONS_COLLECTION].aggregate(pipeline).to_list(length=None)
    return [DailyTrend(date=str(row["_id"]), total=int(row["total"])) for row in rows]


@app.get("/analytics/live", response_model=LiveDashboard)
async def live_dashboard(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> LiveDashboard:
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    coll = db[REGISTRATIONS_COLLECTION]

    total_registrations = await coll.count_documents({})
    today_count = await coll.count_documents({"created_at": {"$gte": start_of_today}})

    pu_pipeline: list[dict[str, Any]] = [
        {
            "$group": {
                "_id": {
                    "polling_unit": {
                        "$ifNull": ["$polling_unit", {"$ifNull": ["$ward", "Unassigned"]}],
                    },
                    "ward": {"$ifNull": ["$ward", "Unknown Ward"]},
                    "lga": "$lga",
                },
                "total": {"$sum": 1},
                "last_activity": {"$max": "$created_at"},
            }
        },
        {"$sort": {"last_activity": -1}},
        {"$limit": 100},
    ]
    pu_rows = await coll.aggregate(pu_pipeline).to_list(length=100)
    polling_units = [
        PollingUnitStat(
            polling_unit=str(row["_id"]["polling_unit"]),
            ward=row["_id"]["ward"],
            lga=row["_id"].get("lga"),
            total=int(row["total"]),
            last_activity=row.get("last_activity"),
        )
        for row in pu_rows
    ]

    ward_pipeline: list[dict[str, Any]] = [
        {"$match": {"ward": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$ward"}},
    ]
    ward_rows = await coll.aggregate(ward_pipeline).to_list(length=None)
    active_wards = len(ward_rows)

    recent_docs = await coll.find().sort("created_at", -1).limit(25).to_list(length=25)
    recent_activity = [
        LiveActivity(
            id=str(doc["_id"]),
            name=doc.get("name"),
            ward=doc.get("ward"),
            lga=doc.get("lga"),
            polling_unit=doc.get("polling_unit"),
            created_at=doc["created_at"],
        )
        for doc in recent_docs
    ]

    return LiveDashboard(
        state="Ogun",
        total_registrations=total_registrations,
        today_count=today_count,
        active_polling_units=len(polling_units),
        active_wards=active_wards,
        polling_units=polling_units,
        recent_activity=recent_activity,
        updated_at=now,
    )


@app.get("/analytics/video-feeds", response_model=VideoFeedDashboard)
async def video_feed_dashboard(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> VideoFeedDashboard:
    from .polling_units_router import _doc_to_out

    now = datetime.now(timezone.utc)
    cursor = db[POLLING_UNITS_COLLECTION].find().sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    units = [_doc_to_out(d) for d in docs]
    total_people = sum(u.people_count for u in units if u.stream_status == "live")
    live_feeds = sum(1 for u in units if u.stream_status == "live")

    return VideoFeedDashboard(
        state="Ogun",
        total_people=total_people,
        live_feeds=live_feeds,
        registered_units=len(units),
        units=units,
        updated_at=now,
    )


@app.websocket("/ws/feeds")
async def feeds_websocket(websocket: WebSocket) -> None:
    await feed_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        feed_manager.disconnect(websocket)
