from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# INEC's IReV portal (inecelectionresults.ng) assigns a fresh API host and
# election_id per election and is only reachable while that election's
# window is live — as of writing, neither the historical 2023 API host nor
# the general domain resolves. A super admin configures `api_base`/
# `election_id` from the admin dashboard (Settings) once they've captured
# them from devtools during a live election; left blank, every function
# below is a safe no-op. The request shapes here follow the one documented
# pattern from a public 2023 scraper
# (https://github.com/mykeels/inec-presidential-elections-2023) and MUST be
# re-verified against devtools network calls once IReV is live before
# relying on them.


@dataclass
class IrevConfig:
    api_base: str
    election_id: str

    @property
    def configured(self) -> bool:
        return bool(self.api_base and self.election_id)

    @property
    def base_url(self) -> str:
        return f"{self.api_base.rstrip('/')}/elections/{self.election_id}"


@dataclass
class OfficialResult:
    votes: int | None
    image_uploaded: bool
    raw: dict[str, Any]


async def fetch_state_lgas(config: IrevConfig, state_irev_id: str) -> list[dict[str, Any]] | None:
    """List LGAs under a state, as INEC's IReV reports them. See module note above."""
    if not config.configured:
        return None

    url = f"{config.base_url}/lga/state/{state_irev_id}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()
    except Exception:
        logger.warning("IReV state lookup failed for state_irev_id=%s", state_irev_id, exc_info=True)
        return None

    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        logger.warning("IReV state lookup returned unexpected shape for state_irev_id=%s", state_irev_id)
        return None
    return items


async def fetch_lga_wards(config: IrevConfig, lga_irev_id: str) -> list[dict[str, Any]] | None:
    """List wards under an LGA, as INEC's IReV reports them. See module note above."""
    if not config.configured:
        return None

    url = f"{config.base_url}/wards"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, params={"lga": lga_irev_id})
            res.raise_for_status()
            data = res.json()
    except Exception:
        logger.warning("IReV LGA lookup failed for lga_irev_id=%s", lga_irev_id, exc_info=True)
        return None

    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        logger.warning("IReV LGA lookup returned unexpected shape for lga_irev_id=%s", lga_irev_id)
        return None
    return items


async def fetch_ward_polling_units(config: IrevConfig, ward_irev_id: str) -> list[dict[str, Any]] | None:
    """List polling units under a ward, as INEC's IReV reports them.

    Used one-time by the mapping sync to match our polling-unit codes against
    IReV's internal ids. Returns None (never raises) if IReV isn't configured
    or the request fails for any reason — DNS, timeout, or a changed response
    shape are all treated the same: "not available right now".
    """
    if not config.configured:
        return None

    url = f"{config.base_url}/pus"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, params={"ward": ward_irev_id})
            res.raise_for_status()
            data = res.json()
    except Exception:
        logger.warning("IReV ward lookup failed for ward_irev_id=%s", ward_irev_id, exc_info=True)
        return None

    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        logger.warning("IReV ward lookup returned unexpected shape for ward_irev_id=%s", ward_irev_id)
        return None
    return items


async def fetch_official_result(config: IrevConfig, pu_irev_id: str) -> OfficialResult | None:
    """Fetch the officially uploaded figure for one polling unit, if any.

    Never raises: any failure (unconfigured, unreachable, unexpected shape)
    returns None so callers can leave the existing figure untouched and fall
    back to manual entry.
    """
    if not config.configured:
        return None

    url = f"{config.base_url}/pus/{pu_irev_id}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()
    except Exception:
        logger.warning("IReV result lookup failed for pu_irev_id=%s", pu_irev_id, exc_info=True)
        return None

    if not isinstance(data, dict):
        return None

    votes_raw = data.get("votes") or data.get("result") or data.get("total_votes")
    try:
        votes = int(votes_raw) if votes_raw is not None else None
    except (TypeError, ValueError):
        votes = None

    image_uploaded = bool(data.get("image_url") or data.get("result_sheet_url") or data.get("uploaded"))
    return OfficialResult(votes=votes, image_uploaded=image_uploaded, raw=data)
