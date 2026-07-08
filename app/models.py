"""
MongoDB collections and document shapes for database: poll-live-feed
"""

REGISTRATIONS_COLLECTION = "registrations"

AGENTS_COLLECTION = "agents"
"""
Agent documents:
  - _id, name, email, password_hash, api_token, lga, ward, created_at
  - data_claim_limit (default 1; admin can increase)
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
