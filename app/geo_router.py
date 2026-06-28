from fastapi import APIRouter, HTTPException

from .geo_data import LGA_LIST, OGUN_LGAS, OGUN_STATE

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/states")
def list_states() -> list[dict[str, str]]:
    return [{"code": "ogun", "name": OGUN_STATE}]


@router.get("/states/ogun/lgas")
def list_ogun_lgas() -> list[str]:
    return LGA_LIST


@router.get("/states/ogun/lgas/{lga}/wards")
def list_ogun_wards(lga: str) -> list[str]:
    wards = OGUN_LGAS.get(lga)
    if wards is None:
        raise HTTPException(status_code=404, detail="LGA not found in Ogun State.")
    return wards
