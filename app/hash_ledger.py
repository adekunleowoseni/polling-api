from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import HASH_LEDGER_COLLECTION

GENESIS_HASH = "0" * 64


def _compute_ledger_hash(seq: int, entity_type: str, entity_id: str, entity_sha256: str, prev_ledger_hash: str) -> str:
    payload = f"{seq}|{entity_type}|{entity_id}|{entity_sha256}|{prev_ledger_hash}"
    return hashlib.sha256(payload.encode()).hexdigest()


async def append_entry(
    db: AsyncIOMotorDatabase,
    *,
    entity_type: str,
    entity_id: str,
    entity_sha256: str,
) -> dict[str, Any]:
    """Append one entry to the tamper-evident hash chain.

    Each entry's ledger_hash depends on every entry before it, so altering
    or removing any past entry breaks the chain from that point forward —
    detectable by verify_chain() without needing an external anchor.
    """
    last = await db[HASH_LEDGER_COLLECTION].find_one(sort=[("seq", -1)])
    seq = int(last["seq"]) + 1 if last else 1
    prev_ledger_hash = last["ledger_hash"] if last else GENESIS_HASH

    ledger_hash = _compute_ledger_hash(seq, entity_type, entity_id, entity_sha256, prev_ledger_hash)
    doc = {
        "seq": seq,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_sha256": entity_sha256,
        "prev_ledger_hash": prev_ledger_hash,
        "ledger_hash": ledger_hash,
        "created_at": datetime.now(timezone.utc),
    }
    await db[HASH_LEDGER_COLLECTION].insert_one(doc)
    return doc


async def get_entry_for_entity(db: AsyncIOMotorDatabase, entity_id: str) -> dict[str, Any] | None:
    return await db[HASH_LEDGER_COLLECTION].find_one({"entity_id": entity_id})


async def verify_chain(db: AsyncIOMotorDatabase) -> dict[str, Any]:
    """Walk the whole ledger and recompute every hash.

    Returns {"valid": bool, "entries": int, "broken_at_seq": int|None}. A
    break means either a row was edited in place or the sequence was
    tampered with — this is the evidence-of-integrity check for tribunal
    purposes, not just a "trust us" claim.
    """
    cursor = db[HASH_LEDGER_COLLECTION].find().sort("seq", 1)
    entries = await cursor.to_list(length=1_000_000)

    prev_ledger_hash = GENESIS_HASH
    for entry in entries:
        expected = _compute_ledger_hash(
            entry["seq"], entry["entity_type"], entry["entity_id"], entry["entity_sha256"], prev_ledger_hash
        )
        if expected != entry["ledger_hash"] or entry["prev_ledger_hash"] != prev_ledger_hash:
            return {"valid": False, "entries": len(entries), "broken_at_seq": entry["seq"]}
        prev_ledger_hash = entry["ledger_hash"]

    return {"valid": True, "entries": len(entries), "broken_at_seq": None}
