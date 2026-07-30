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
    state: str | None = None
    created_at: datetime
    accreditation_status: str = "none"


class AgentAssignmentUpdate(BaseModel):
    lga: str = Field(..., min_length=2, max_length=80)
    ward: str = Field(..., min_length=2, max_length=80)


class AgentSessionOut(BaseModel):
    agent: AgentOut
    api_token: str


class AccreditationOut(BaseModel):
    accreditation_status: str = "none"
    accreditation_number: str | None = None
    party_name: str | None = None
    is_ec8a_signatory: bool | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    has_document: bool = False


class AccreditationRejectRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class AdminAccreditationOut(BaseModel):
    agent_id: str
    agent_name: str
    agent_email: str
    lga: str | None = None
    ward: str | None = None
    state: str | None = None
    accreditation_status: str
    accreditation_number: str | None = None
    party_name: str | None = None
    is_ec8a_signatory: bool | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


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


class FeedRecordingOut(BaseModel):
    id: str
    polling_unit_id: str
    polling_unit_name: str
    code: str
    state: str
    ward: str
    lga: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: float = 0.0
    frame_count: int = 0
    fps: float = 0.0
    file_size: int = 0


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    state: str | None = None
    allowed_tabs: list[str] = []
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
    total_votes: int = 0
    units_with_results: int = 0
    updated_at: datetime


class VoteResultSubmit(BaseModel):
    code: str = Field(..., min_length=2, max_length=80)
    votes: int = Field(..., ge=0, le=1_000_000)


class VoteResultOut(BaseModel):
    id: str
    polling_unit_id: str
    code: str
    polling_unit_name: str
    state: str
    ward: str
    lga: str
    votes: int
    people_count: int = 0
    people_count_at_submit: int = 0
    updated_at: datetime
    agent_id: str | None = None


class VoteUnitStat(BaseModel):
    code: str
    name: str
    lga: str
    ward: str
    state: str = ""
    votes: int
    people_count: int
    difference: int
    comparison_note: str


class VotePlaceStat(BaseModel):
    label: str
    state: str = ""
    lga: str = ""
    ward: str = ""
    votes: int
    people_count: int
    unit_count: int
    difference: int
    comparison_note: str


class VoteResultsSummary(BaseModel):
    total_votes: int
    units_with_results: int
    total_people_counted: int
    overall_difference: int
    overall_note: str
    plain_summary: str
    by_polling_unit: list[VoteUnitStat]
    by_lga: list[VotePlaceStat]
    by_ward: list[VotePlaceStat]
    by_state: list[VotePlaceStat] = []
    highest_unit: VoteUnitStat | None = None
    lowest_unit: VoteUnitStat | None = None
    highest_lga: VotePlaceStat | None = None
    lowest_lga: VotePlaceStat | None = None
    highest_ward: VotePlaceStat | None = None
    lowest_ward: VotePlaceStat | None = None


class ResultSheetOut(BaseModel):
    id: str
    polling_unit_id: str
    code: str
    polling_unit_name: str
    state: str
    ward: str
    lga: str
    agent_id: str | None = None
    votes: int
    accredited_voters: int | None = None
    registered_voters: int | None = None
    sha256: str
    captured_lat: float | None = None
    captured_lng: float | None = None
    captured_accuracy_m: float | None = None
    device_captured_at: datetime | None = None
    received_at: datetime
    device_id: str | None = None
    app_version: str | None = None
    people_count_at_capture: int = 0
    supersedes_id: str | None = None
    version: int = 1
    official_votes: int | None = None
    official_source: str | None = None
    official_checked_at: datetime | None = None
    official_note: str | None = None
    irev_image_uploaded: bool | None = None
    external_pvt_source: str | None = None
    external_pvt_votes: int | None = None
    external_pvt_note: str | None = None
    agent_accreditation_number: str | None = None
    agent_is_ec8a_signatory: bool | None = None
    agent_party_name: str | None = None
    created_at: datetime
    over_accreditation: bool = False
    official_diff: int | None = None
    discrepancy_note: str | None = None


class ResultSheetOfficialUpdate(BaseModel):
    official_votes: int = Field(..., ge=0, le=1_000_000)
    official_note: str | None = Field(default=None, max_length=500)


class ResultSheetExternalPvtUpdate(BaseModel):
    external_pvt_source: str = Field(..., min_length=1, max_length=120)
    external_pvt_votes: int = Field(..., ge=0, le=1_000_000)
    external_pvt_note: str | None = Field(default=None, max_length=500)


class AccessLogEntryOut(BaseModel):
    action: str
    actor_type: str
    actor_name: str
    ip: str | None = None
    created_at: datetime


class LedgerEntryOut(BaseModel):
    seq: int
    entity_type: str
    entity_id: str
    entity_sha256: str
    prev_ledger_hash: str
    ledger_hash: str
    created_at: datetime


class LedgerVerifyOut(BaseModel):
    valid: bool
    entries: int
    broken_at_seq: int | None = None


class ResultSheetCertificateOut(BaseModel):
    result_sheet: ResultSheetOut
    ledger_entry: LedgerEntryOut | None = None
    access_log: list[AccessLogEntryOut] = []
    agent_name: str | None = None
    agent_email: str | None = None
    generated_at: datetime


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
    state: str | None = None
    created_at: datetime
    polling_units: list[AdminAgentUnitOut] = []
    data_claim_limit: int = 1
    data_claims_used: int = 0
    airtime_claim_limit: int = 1
    airtime_claims_used: int = 0


class AdminAgentSummary(BaseModel):
    id: str
    name: str
    email: str
    lga: str | None = None
    ward: str | None = None
    state: str | None = None
    created_at: datetime
    polling_unit_count: int
    live_unit_count: int
    data_claim_limit: int = 1
    data_claims_used: int = 0
    airtime_claim_limit: int = 1
    airtime_claims_used: int = 0


class AgentDataClaimLimitUpdate(BaseModel):
    data_claim_limit: int = Field(..., ge=0, le=1000)


class AgentAirtimeClaimLimitUpdate(BaseModel):
    airtime_claim_limit: int = Field(..., ge=0, le=1000)


class DataClaimQuotaOut(BaseModel):
    data_claim_limit: int
    data_claims_used: int
    data_claims_remaining: int


class AirtimeClaimQuotaOut(BaseModel):
    airtime_claim_limit: int
    airtime_claims_used: int
    airtime_claims_remaining: int


class AirtimePlanOut(BaseModel):
    amount: float
    enabled: bool = True


class AirtimePlanItem(BaseModel):
    amount: float = Field(..., gt=0, le=100000)
    enabled: bool = True


class AirtimePlansUpdate(BaseModel):
    plans: list[AirtimePlanItem]


class AirtimeCreditRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    network: str = Field(..., min_length=2, max_length=20)
    amount: float = Field(..., gt=0, le=100000)


class AirtimeCreditOut(BaseModel):
    id: str
    phone: str
    network: str
    amount: float
    request_id: str
    status: str
    created_at: datetime
    agent_id: str | None = None
    agent_name: str | None = None
    agent_email: str | None = None


class AppSettingsOut(BaseModel):
    strict_one_data_claim_per_phone: bool = False
    strict_one_airtime_claim_per_phone: bool = False
    irev_enabled: bool = False
    irev_api_base: str = ""
    irev_election_id: str = ""
    irev_poll_interval_seconds: int = 300


class AppSettingsUpdate(BaseModel):
    strict_one_data_claim_per_phone: bool | None = None
    strict_one_airtime_claim_per_phone: bool | None = None
    irev_enabled: bool | None = None
    irev_api_base: str | None = Field(default=None, max_length=200)
    irev_election_id: str | None = Field(default=None, max_length=100)
    irev_poll_interval_seconds: int | None = Field(default=None, ge=60, le=3600)


class AgentPollingUnitOut(PollingUnitOut):
    ingest_token: str


class DataPlanOut(BaseModel):
    network: str
    service_id: str
    variation_code: str
    name: str
    amount: float
    enabled: bool = True


class DataPlanEnableItem(BaseModel):
    network: str = Field(..., min_length=2, max_length=20)
    variation_code: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=200)
    amount: float = Field(..., ge=0)
    enabled: bool = True


class DataPlansUpdate(BaseModel):
    plans: list[DataPlanEnableItem]


class DataCreditRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    network: str = Field(..., min_length=2, max_length=20)
    variation_code: str = Field(..., min_length=1, max_length=80)


class DataCreditOut(BaseModel):
    id: str
    phone: str
    network: str
    plan_name: str
    variation_code: str
    amount: float
    request_id: str
    status: str
    created_at: datetime
    agent_id: str | None = None
    agent_name: str | None = None
    agent_email: str | None = None


class WitnessPersonPresent(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)


class WitnessStatementOut(BaseModel):
    id: str
    polling_unit_id: str
    code: str
    polling_unit_name: str
    state: str
    ward: str
    lga: str
    agent_id: str | None = None
    agent_name: str | None = None
    result_sheet_id: str | None = None
    incident_category: str
    narrative: str
    people_present: list[WitnessPersonPresent] = []
    occurred_at: datetime | None = None
    submitted_at: datetime
    captured_lat: float | None = None
    captured_lng: float | None = None
    supersedes_id: str | None = None
    version: int = 1


class TribunalReportOut(BaseModel):
    code: str
    polling_unit_name: str
    state: str
    ward: str
    lga: str
    registered_voters: int | None = None
    accredited_voters: int | None = None
    agent_votes: int | None = None
    official_votes: int | None = None
    official_source: str | None = None
    irev_image_uploaded: bool | None = None
    external_pvt_source: str | None = None
    external_pvt_votes: int | None = None
    result_sheets: list[ResultSheetOut] = []
    witness_statements: list[WitnessStatementOut] = []
    irregularity_summary: list[str] = []
    generated_at: datetime


class FlaggedUnitOut(BaseModel):
    code: str
    polling_unit_name: str
    state: str
    ward: str
    lga: str
    flags: list[str]
    severity: int
