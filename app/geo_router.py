from fastapi import APIRouter, HTTPException

from .geo_data import LGA_LIST, OGUN_LGAS, OGUN_STATE, polling_units_for_ward
from .osun_geo_data import (
    OSUN_LGA_LIST,
    OSUN_LGAS,
    OSUN_STATE,
    osun_polling_units_for_ward,
)

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/states")
def list_states() -> list[dict[str, str]]:
    return [
        {"code": "ogun", "name": OGUN_STATE},
        {"code": "osun", "name": OSUN_STATE},
    ]


@router.get("/states/ogun/summary")
def ogun_geo_summary() -> dict[str, int | str]:
    return {
        "state": OGUN_STATE,
        "lga_count": len(LGA_LIST),
        "ward_count": sum(len(wards) for wards in OGUN_LGAS.values()),
    }


@router.get("/states/ogun/lgas")
def list_ogun_lgas() -> list[str]:
    return LGA_LIST


@router.get("/states/ogun/lgas/{lga}/wards")
def list_ogun_wards(lga: str) -> list[str]:
    wards = OGUN_LGAS.get(lga)
    if wards is None:
        raise HTTPException(status_code=404, detail="LGA not found in Ogun State.")
    return wards


@router.get("/states/ogun/lgas/{lga}/wards/{ward}/polling-units")
def list_ogun_polling_units(lga: str, ward: str) -> list[dict[str, str]]:
    units = polling_units_for_ward(lga, ward)
    if not units:
        raise HTTPException(status_code=404, detail="LGA or ward not found in Ogun State.")
    return units


@router.get("/states/osun/summary")
def osun_geo_summary() -> dict[str, int | str]:
    return {
        "state": OSUN_STATE,
        "lga_count": len(OSUN_LGA_LIST),
        "ward_count": sum(len(wards) for wards in OSUN_LGAS.values()),
    }


@router.get("/states/osun/lgas")
def list_osun_lgas() -> list[str]:
    return OSUN_LGA_LIST


@router.get("/states/osun/lgas/{lga}/wards")
def list_osun_wards(lga: str) -> list[str]:
    wards = OSUN_LGAS.get(lga)
    if wards is None:
        raise HTTPException(status_code=404, detail="LGA not found in Osun State.")
    return wards


@router.get("/states/osun/lgas/{lga}/wards/{ward}/polling-units")
def list_osun_polling_units(lga: str, ward: str) -> list[dict[str, str]]:
    units = osun_polling_units_for_ward(lga, ward)
    if not units:
        raise HTTPException(status_code=404, detail="LGA or ward not found in Osun State.")
    return units
