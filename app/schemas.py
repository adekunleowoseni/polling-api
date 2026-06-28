from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegistrationCreate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    ward: str | None = None
    lga: str | None = None
    polling_unit: str | None = None
    address: str | None = None
    form_date: str | None = None
    raw_ai_output: dict[str, Any]


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="MongoDB ObjectId as hex string")
    name: str | None
    phone: str | None
    email: str | None
    ward: str | None
    lga: str | None
    polling_unit: str | None
    address: str | None
    form_date: str | None
    raw_ai_output: dict[str, Any]
    created_at: datetime


class DailyTrend(BaseModel):
    date: str
    total: int


class PollingUnitStat(BaseModel):
    polling_unit: str
    ward: str | None
    lga: str | None
    total: int
    last_activity: datetime | None


class LiveActivity(BaseModel):
    id: str
    name: str | None
    ward: str | None
    lga: str | None
    polling_unit: str | None
    created_at: datetime


class LiveDashboard(BaseModel):
    state: str = "Ogun"
    total_registrations: int
    today_count: int
    active_polling_units: int
    active_wards: int
    polling_units: list[PollingUnitStat]
    recent_activity: list[LiveActivity]
    updated_at: datetime


class PollingUnitCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    state: str = Field(default="Ogun State", min_length=2, max_length=80)
    ward: str = Field(..., min_length=2, max_length=80)
    lga: str = Field(..., min_length=2, max_length=80)
    code: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    device_type: str = Field(default="meta_rayban", description="meta_rayban or phone_camera")


class PollingUnitOut(BaseModel):
    id: str
    name: str
    code: str
    state: str
    ward: str
    lga: str
    people_count: int
    peak_people_count: int
    stream_status: str
    device_type: str
    last_frame_at: datetime | None
    created_at: datetime


class PollingUnitRegisterOut(PollingUnitOut):
    ingest_token: str


class PeopleCountUpdate(BaseModel):
    people_count: int = Field(..., ge=0, le=10000, description="Corrected unique people count")


class VideoFeedDashboard(BaseModel):
    state: str = "Ogun"
    total_people: int
    live_feeds: int
    registered_units: int
    units: list[PollingUnitOut]
    updated_at: datetime


class AgentRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    lga: str = Field(..., min_length=2, max_length=80)
    ward: str = Field(..., min_length=2, max_length=80)


class AgentLogin(BaseModel):
    email: EmailStr
    password: str


class AgentOut(BaseModel):
    id: str
    name: str
    email: str
    lga: str | None = None
    ward: str | None = None
    created_at: datetime


class AgentAssignmentUpdate(BaseModel):
    lga: str = Field(..., min_length=2, max_length=80)
    ward: str = Field(..., min_length=2, max_length=80)


class AgentSessionOut(BaseModel):
    agent: AgentOut
    api_token: str


class FeedSnapOut(BaseModel):
    id: str
    polling_unit_id: str
    polling_unit_name: str
    code: str
    state: str
    ward: str
    lga: str
    people_count: int
    created_at: datetime


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: datetime


class AdminSessionOut(BaseModel):
    admin: AdminOut
    api_token: str


class AdminOverview(BaseModel):
    live_feeds: int
    registered_units: int
    total_people_on_site: int
    feed_snapshots: int
    agents: int
    form_registrations: int
    updated_at: datetime


class AdminPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminAgentUnitOut(BaseModel):
    id: str
    name: str
    code: str
    lga: str
    ward: str
    ingest_token: str
    stream_status: str
    people_count: int


class AdminAgentOut(BaseModel):
    id: str
    name: str
    email: str
    lga: str | None = None
    ward: str | None = None
    created_at: datetime
    polling_units: list[AdminAgentUnitOut] = []


class AdminAgentSummary(BaseModel):
    id: str
    name: str
    email: str
    lga: str | None = None
    ward: str | None = None
    created_at: datetime
    polling_unit_count: int
    live_unit_count: int


class AgentPollingUnitOut(PollingUnitOut):
    ingest_token: str
