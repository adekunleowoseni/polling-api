"""
MongoDB collections and document shapes for database: poll-live-feed
"""

REGISTRATIONS_COLLECTION = "registrations"

AGENTS_COLLECTION = "agents"
"""
Agent documents:
  - _id, name, email, password_hash, api_token, lga, ward, created_at
  - data_claim_limit (default 1; admin can increase)
  - Accreditation (admin-verified before the agent may submit result sheets):
    accreditation_status ("none" | "pending" | "approved" | "rejected"),
    accreditation_doc_filename, accreditation_doc_sha256,
    accreditation_number, party_name, is_ec8a_signatory (agent-claimed),
    submitted_at, reviewed_by, reviewed_at, rejection_reason
"""

POLLING_UNITS_COLLECTION = "polling_units"
"""
Polling unit documents:
  - _id, agent_id, name, code, state, ward, lga
  - people_count (unique faces, no duplicates), peak_people_count
  - device_type, ingest_token, last_frame_at, created_at
"""

DETECTED_FACES_COLLECTION = "detected_faces"
"""
Stored face embeddings per polling unit (deduplication):
  - polling_unit_id, code, embedding, first_seen_at, last_seen_at
"""

FEED_SNAPS_COLLECTION = "feed_snaps"
"""
Saved stills from agent relay live feed:
  - polling_unit_id, code, name, state, ward, lga, agent_id
  - people_count, filename, created_at
"""

FEED_RECORDINGS_COLLECTION = "feed_recordings"
"""
Saved video recordings assembled from agent relay frames (low-fps MP4):
  - polling_unit_id, code, polling_unit_name, state, ward, lga, agent_id
  - status ("recording" | "completed")
  - started_at, ended_at, duration_seconds, frame_count, fps, width, height
  - file_size, filename (stored under storage/recordings/<_id>.mp4)
The video file itself lives on local disk; only metadata is stored here.
"""

ADMINS_COLLECTION = "admins"
"""
Super admin accounts:
  - name, email, password_hash, api_token, role, created_at
"""

DATA_PLANS_COLLECTION = "data_plans"
"""
Admin-enabled VTpass data plans agents may claim:
  - network (mtn|airtel|glo|9mobile)
  - service_id, variation_code, name, amount
  - enabled, updated_at
"""

DATA_CREDITS_COLLECTION = "data_credits"
"""
Agent data credit transactions via VTpass:
  - agent_id, phone, network, service_id, variation_code, plan_name, amount
  - request_id, status, vtpass_code, vtpass_response, created_at
"""

AIRTIME_PLANS_COLLECTION = "airtime_plans"
"""
Admin-controlled airtime denominations agents may purchase:
  - amount (e.g. 100, 200, 500, 1000 ...)
  - enabled, updated_at
"""

AIRTIME_CREDITS_COLLECTION = "airtime_credits"
"""
Agent airtime top-up transactions via VTpass:
  - agent_id, phone, network, service_id, amount
  - request_id, status, vtpass_code, vtpass_response, created_at
"""

APP_SETTINGS_COLLECTION = "app_settings"
"""
Global, admin-controlled application settings (single doc, _id="global"):
  - strict_one_data_claim_per_phone (bool): a phone can claim data only once
  - strict_one_airtime_claim_per_phone (bool): a phone can claim airtime only once
  - updated_at
"""

VOTE_RESULTS_COLLECTION = "vote_results"
"""
Agent-entered election results per polling unit (one row per unit):
  - polling_unit_id, code, polling_unit_name, state, ward, lga, agent_id
  - votes (integer vote count entered by the agent)
  - people_count_at_submit (snapshot of unit people_count when saved)
  - created_at, updated_at
"""

RESULT_SHEETS_COLLECTION = "result_sheets"
"""
Immutable, append-only EC8A result-sheet captures per polling unit.
Agents never edit or overwrite a submitted row — a correction inserts a new
document with supersedes_id pointing at the one it replaces, so the full
history stays intact:
  - polling_unit_id, code, polling_unit_name, state, ward, lga, agent_id
  - votes (candidate's vote count as read from the EC8A)
  - accredited_voters, registered_voters (optional, agent-observed at the unit)
  - photo_filename (stored under storage/result_sheets/<_id>.jpg), sha256
  - captured_lat, captured_lng, captured_accuracy_m (nullable; best-effort GPS)
  - device_captured_at (client-reported capture time), received_at (server time)
  - device_id (client-persisted UUID), app_version (frontend build tag)
  - people_count_at_capture (snapshot of unit people_count when saved)
  - supersedes_id (ObjectId of the row this correction replaces, or None)
  - official_votes, official_source ("manual" | "irev_auto"),
    official_checked_at, official_note — filled in later for comparison,
    never touches the agent-submitted fields above
  - irev_image_uploaded (bool|None) — whether INEC's IReV shows an uploaded
    result-sheet image for this unit, set by the IReV watchdog
  - external_pvt_source, external_pvt_votes, external_pvt_note — manually
    entered civil-society PVT figure for comparison (e.g. YIAGA Watching
    the Vote), no automated source available
  - Accreditation snapshot at capture time (immutable copy, see AGENTS_COLLECTION):
    agent_accreditation_number, agent_is_ec8a_signatory, agent_party_name
  - created_at
"""

IREV_PU_MAP_COLLECTION = "irev_pu_map"
"""
One-time mapping of our polling_unit `code` to INEC IReV's internal ids,
built by an admin-triggered sync once IReV is live for a given election:
  - code, ward_irev_id, pu_irev_id, matched_name, matched_at
"""

HASH_LEDGER_COLLECTION = "hash_ledger"
"""
Append-only cryptographic hash chain covering every result-sheet and
witness-statement submission, so the sequence itself is tamper-evident even
if the underlying documents were somehow altered in place:
  - seq (monotonic int), entity_type ("result_sheet" | "witness_statement")
  - entity_id, entity_sha256 (hash of the entity's immutable core fields)
  - prev_ledger_hash, ledger_hash = sha256(seq|entity_type|entity_id|entity_sha256|prev_ledger_hash)
  - created_at
"""

ACCESS_LOG_COLLECTION = "access_log"
"""
Audit trail of who viewed or edited a result sheet / witness statement,
beyond the original capture event — courts and opposing counsel probe
whether a record could have been swapped after the fact:
  - entity_type, entity_id, actor_type ("agent" | "admin"), actor_id,
    actor_name, action ("view" | "edit"), ip, created_at
"""

WITNESS_STATEMENTS_COLLECTION = "witness_statements"
"""
Immutable, append-only agent statements recorded the same day as an
incident, same versioning pattern as result_sheets (supersedes_id/version):
  - polling_unit_id, code, result_sheet_id (optional), agent_id
  - incident_category ("over_voting" | "violence" | "vote_buying" |
    "snatching" | "irev_missing" | "other")
  - narrative (free text), people_present ([{name, role, phone}] — covers
    security agents, journalists, other observers on site)
  - occurred_at (agent-entered), submitted_at (server time)
  - captured_lat, captured_lng (optional)
  - supersedes_id, version
"""
