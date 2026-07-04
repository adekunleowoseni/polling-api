from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .settings import settings

LAGOS = ZoneInfo("Africa/Lagos")

# VTpass service IDs for mobile data.
NETWORK_SERVICE_IDS: dict[str, str] = {
    "mtn": "mtn-data",
    "airtel": "airtel-data",
    "glo": "glo-data",
    "9mobile": "etisalat-data",
}

NETWORK_LABELS: dict[str, str] = {
    "mtn": "MTN",
    "airtel": "Airtel",
    "glo": "Glo",
    "9mobile": "9mobile",
}


def vtpass_configured() -> bool:
    return bool(settings.vtpass_api_key and settings.vtpass_secret_key and settings.vtpass_public_key)


def make_request_id() -> str:
    """VTpass request_id: first 12 chars = YYYYMMDDHHmm (Africa/Lagos), then random."""
    stamp = datetime.now(LAGOS).strftime("%Y%m%d%H%M")
    return f"{stamp}{secrets.token_hex(8)}"


def _get_headers() -> dict[str, str]:
    return {
        "api-key": settings.vtpass_api_key,
        "public-key": settings.vtpass_public_key,
    }


def _post_headers() -> dict[str, str]:
    return {
        "api-key": settings.vtpass_api_key,
        "secret-key": settings.vtpass_secret_key,
        "Content-Type": "application/json",
    }


async def fetch_variations(service_id: str) -> list[dict[str, Any]]:
    if not vtpass_configured():
        raise RuntimeError("VTpass is not configured.")

    url = f"{settings.vtpass_base_url.rstrip('/')}/service-variations"
    async with httpx.AsyncClient(timeout=45.0) as client:
        res = await client.get(url, params={"serviceID": service_id}, headers=_get_headers())
        res.raise_for_status()
        data = res.json()

    content = data.get("content") or {}
    variations = content.get("variations") or content.get("varations") or []
    plans: list[dict[str, Any]] = []
    for item in variations:
        code = str(item.get("variation_code") or "").strip()
        name = str(item.get("name") or code).strip()
        amount_raw = item.get("variation_amount") or item.get("amount") or "0"
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            amount = 0.0
        if not code:
            continue
        plans.append(
            {
                "variation_code": code,
                "name": name,
                "amount": amount,
            }
        )
    return plans


async def purchase_data(
    *,
    service_id: str,
    variation_code: str,
    phone: str,
    amount: float,
    request_id: str,
) -> dict[str, Any]:
    if not vtpass_configured():
        raise RuntimeError("VTpass is not configured.")

    url = f"{settings.vtpass_base_url.rstrip('/')}/pay"
    payload = {
        "request_id": request_id,
        "serviceID": service_id,
        "billersCode": phone,
        "variation_code": variation_code,
        "amount": amount,
        "phone": phone,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, json=payload, headers=_post_headers())
        res.raise_for_status()
        return res.json()
