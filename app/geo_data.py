"""Ogun State administrative divisions (INEC electoral wards)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

OGUN_STATE = "Ogun State"

# LGA name -> list of electoral wards
OGUN_LGAS: dict[str, list[str]] = {
    "Abeokuta North": [
        "Ikereku", "Ikija", "Ago Oko", "Elega", "Ilugun", "Gbagura", "Ika",
        "Lafenwa", "Sabo", "Oke Ago Owu", "Totoro", "Itaoshin", "Olorunda",
        "Imale", "Isaga", "Ibara Orile",
    ],
    "Abeokuta South": [
        "Ake I", "Ake II", "Ake III", "Keesi/Emere", "Ijero", "Itoko",
        "Ijaiye/Idi Apa", "Erunba", "Ago Egun", "Sodeke I", "Sodeke II",
        "Imo/Isabo", "Ibore", "Ibara I", "Ibara II",
    ],
    "Ado-Odo/Ota": [
        "Ota I", "Ota II", "Ota III", "Sango", "Ijoko", "Atan", "Iju", "Ilogbo",
        "Ado Odo I", "Ado Odo II", "Ere", "Alapoti", "Ketu Alapere", "Igbesa",
        "Agbara I", "Agbara II",
    ],
    "Egbado North": [
        "Ido Foi", "Aiye Toro I", "Aiye Toro II", "Sunwa", "Iboro Joga", "Imasai",
        "Ebute Igbooro", "Ehunbe", "Ibuha", "Ijoho", "Ibese",
    ],
    "Egbado South": [
        "Ilaro I", "Ilaro II", "Ilaro III", "Iwoye", "Idogo", "Okeodan",
        "Owode I", "Owode II", "Ilobi", "Ajilete",
    ],
    "Ewekoro": [
        "Abalabi", "Asa/Yobo", "Arigbajo", "Itori", "Elere/Onigbedu", "Papalanto",
        "Wasimi", "Mosan", "Owowo", "Obada Oko",
    ],
    "Ifo": [
        "Ifo I", "Ifo II", "Ifo III", "Agbado", "Iseri", "Ajuwon", "Oke Aro",
        "Osunsun", "Sunren", "Coker", "Ibogun",
    ],
    "Ijebu East": [
        "Ijebu Mushin I", "Ijebu Mushin II", "Ijebu Ife I", "Ijebu Ife II", "Owu",
        "Ikija", "Itele", "Ogbere", "Imobi I", "Imobi II", "Ajebandele",
    ],
    "Ijebu North": [
        "Atikori", "Japara/Ojowo", "Omen", "Osun", "Oke Agbo", "Oke Sopin",
        "Oru/Awa", "Ago Iwoye I", "Ago Iwoye II", "Ako Onigbagbo", "Mamu",
    ],
    "Ijebu North East": [
        "Atan/Imuku", "Odosimadegun Odosebora", "Iwewiro", "Odesenlu", "Igede",
        "Oju Ona", "Isoyin", "Ilese", "Oke Eri", "Erunwon",
    ],
    "Ijebu Ode": [
        "Isoku/Ososa", "Odo Esa", "Itantebo", "Ijede Imepe I", "Ijede Imepe II",
        "Porogun I", "Porogun II", "Ijasi", "Odo Ise", "Isiwo", "Itamapako",
    ],
    "Ikenne": [
        "Ikenne I", "Ikenne II", "Iperu I", "Iperu II", "Iperu III", "Ogere I",
        "Ogere II", "Ilasa I", "Ilasa II", "Ilisa/Oralu",
    ],
    "Imeko Afon": [
        "Imeko", "Oke Agbede", "Idofa", "Iwoye", "Ilara", "Afon", "Otapele",
        "Kajola", "Olorunda", "Ijoyin",
    ],
    "Ipokia": [
        "Ipokia I", "Ipokia II", "Agosasa", "Ijofin Idosa", "Tube", "Agada",
        "Mauni I", "Mauni II", "Ajegunle", "Ifonyintedo", "Idiroko", "Ihumbo",
    ],
    "Obafemi Owode": [
        "Mokoloki", "Ofada", "Owode", "Ajura", "Moloko-Asipa", "Onidundu", "Oba",
        "Egbada", "Obafemi", "Kajola", "Ajebo", "Alapako",
    ],
    "Odeda": [
        "Odeda", "Balogun Itesi", "Olodo", "Alagbagba", "Ilugun", "Osiele",
        "Obantoko", "Alabata", "Obete", "Opeji",
    ],
    "Odogbolu": [
        "Imosan", "Imodi", "Okun Owa", "Odogbolu I", "Odogbolu II", "Aiyepe",
        "Osasa", "Idowa", "Ibefun", "Ilado", "Ogbo/Morarika", "Ala/Igbile",
        "Jobore", "Omu",
    ],
    "Ogun Waterside": [
        "Iwopin", "Oni", "Ibiade", "Lukogbe", "Abigi", "Efire", "Ayede",
        "Ayila Itebu", "Makun Irokun", "Ode Omi",
    ],
    "Remo North": [
        "Ayegbami", "Igan/Ajina", "Moborode/Oke Ola", "Odofin/Imagbo", "Ilara",
        "Akaka", "Ipara", "Orile Oko", "Ode I", "Ode II",
    ],
    "Sagamu": [
        "Oko/Epe/Itula I", "Oko Epe Itula II", "Aiyegbami", "Sabo I", "Sabo II",
        "Isokun", "Ijagba", "Latawa", "Ode Lemo", "Ogijo", "Surulere", "Isote",
        "Simawa", "Agbowa", "Ibido/Ituwa/Alara",
    ],
}

LGA_LIST = list(OGUN_LGAS.keys())

POLLING_UNITS_JSON = Path(__file__).resolve().parent / "data" / "ogun_polling_units.json"

# Placeholder count for wards without official INEC data yet.
POLLING_UNITS_PER_WARD = 20


@lru_cache(maxsize=1)
def _load_polling_units_catalog() -> dict[str, dict[str, list[dict[str, str]]]]:
    if not POLLING_UNITS_JSON.is_file():
        return {}
    try:
        raw = json.loads(POLLING_UNITS_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def polling_units_for_ward(lga: str, ward: str) -> list[dict[str, str]]:
    """Return selectable polling units for an LGA/ward."""
    lga_name = lga.strip()
    ward_name = ward.strip()
    if lga_name not in OGUN_LGAS or ward_name not in OGUN_LGAS[lga_name]:
        return []

    catalog = _load_polling_units_catalog()
    official = catalog.get(lga_name, {}).get(ward_name)
    if official:
        return list(official)

    return [
        {
            "code": f"PU{i:03d}",
            "name": f"Polling unit {i:03d} — {ward_name}",
        }
        for i in range(1, POLLING_UNITS_PER_WARD + 1)
    ]


def find_polling_unit(lga: str, ward: str, pu_code: str) -> dict[str, str] | None:
    needle = pu_code.strip()
    needle_compact = needle.upper().replace(" ", "")
    if needle_compact.startswith("PU") and len(needle_compact) < 5:
        num = needle_compact[2:]
        if num.isdigit():
            needle_compact = f"PU{int(num):03d}"

    for unit in polling_units_for_ward(lga, ward):
        unit_code = unit["code"].upper().replace(" ", "")
        if unit["code"] == needle or unit["name"] == needle or unit_code == needle_compact:
            return unit
    return None


def validate_ogun_ward(lga: str, ward: str) -> None:
    from fastapi import HTTPException

    lga_name = lga.strip()
    ward_name = ward.strip()
    if lga_name not in OGUN_LGAS:
        raise HTTPException(status_code=400, detail="Invalid LGA for Ogun State.")
    if ward_name not in OGUN_LGAS[lga_name]:
        raise HTTPException(status_code=400, detail="Invalid ward for the selected LGA.")


def validate_ogun_polling_unit(lga: str, ward: str, name: str, code: str) -> dict[str, str]:
    """Ensure name/code match a catalog polling unit for the ward."""
    from fastapi import HTTPException

    validate_ogun_ward(lga, ward)
    catalog = polling_units_for_ward(lga, ward)
    name_stripped = name.strip()
    code_lower = code.lower().strip()

    for unit in catalog:
        unit_code = unit["code"]
        unit_code_lower = unit_code.lower()
        if unit["name"] == name_stripped:
            return unit
        if unit_code_lower == code_lower:
            return unit
        if unit_code == name_stripped or unit_code_lower == name_stripped.lower():
            return unit
        if code_lower.endswith(unit_code_lower) or f"-{unit_code_lower}" in code_lower:
            return unit

    raise HTTPException(
        status_code=400,
        detail="Select a valid polling unit from the list for this ward.",
    )
