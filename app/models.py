"""
MongoDB collections and document shapes for database: poll-live-feed
"""

REGISTRATIONS_COLLECTION = "registrations"

AGENTS_COLLECTION = "agents"
"""
Agent documents:
  - _id, name, email, password_hash, api_token, lga, ward, created_at
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

ADMINS_COLLECTION = "admins"
"""
Super admin accounts:
  - name, email, password_hash, api_token, role, created_at
"""
