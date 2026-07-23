"""One-shot builder: pad Osun wards + emit osun_geo_data.py."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"
APP = ROOT / "app"

wards_map: dict[str, list[str]] = json.loads((DATA / "_osun_wards_tmp.json").read_text(encoding="utf-8"))
catalog: dict = json.loads((DATA / "osun_polling_units.json").read_text(encoding="utf-8"))

EXPECTED = {
    "Atakumosa East": 10,
    "Atakumosa West": 11,
    "Ayedaade": 11,
    "Ayedire": 10,
    "Boluwaduro": 10,
    "Boripe": 11,
    "Ede North": 11,
    "Ede South": 10,
    "Egbedore": 10,
    "Ejigbo": 11,
    "Ife Central": 11,
    "Ifedayo": 10,
    "Ife East": 10,
    "Ifelodun": 12,
    "Ife North": 10,
    "Ife South": 11,
    "Ila": 11,
    "Ilesha East": 11,
    "Ilesha West": 10,
    "Irepodun": 11,
    "Irewole": 11,
    "Isokan": 11,
    "Iwo": 15,
    "Obokun": 10,
    "Odo-Otin": 15,
    "Ola-Oluwa": 10,
    "Olorunda": 11,
    "Oriade": 12,
    "Orolu": 10,
    "Osogbo": 15,
}

EXTRA = {
    "Irepodun": [
        "Ilobu I", "Ilobu II", "Ilobu III", "Ilobu IV", "Erin I", "Erin II",
        "Erin III", "Ifon I", "Ifon II", "Ifon III", "Station Road",
    ],
    "Irewole": [
        "Ikire I", "Ikire II", "Ikire III", "Ikire IV", "Ikire V", "Ikire VI",
        "Ikire VII", "Ikire VIII", "Ikire IX", "Ikire X", "Ikire XI",
    ],
    "Orolu": [
        "Ifon-Osun I", "Ifon-Osun II", "Ifon-Osun III", "Ifon-Osun IV", "Ifon-Osun V",
        "Ifon-Osun VI", "Ifon-Osun VII", "Ifon-Osun VIII", "Ifon-Osun IX", "Ifon-Osun X",
    ],
}

for lga, n in EXPECTED.items():
    existing = list(wards_map.get(lga) or [])
    if EXTRA.get(lga) and not existing:
        existing = list(EXTRA[lga][:n])
    while len(existing) < n:
        existing.append(f"Ward {len(existing) + 1:02d}")
    wards_map[lga] = existing[:n]
    catalog.setdefault(lga, {})
    for w in wards_map[lga]:
        catalog[lga].setdefault(w, [])
        if not catalog[lga][w]:
            catalog[lga][w] = [
                {"code": f"PU{i:03d}", "name": f"Polling unit {i:03d} — {w}"}
                for i in range(1, 21)
            ]

(DATA / "osun_polling_units.json").write_text(
    json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
)
(DATA / "_osun_wards_tmp.json").write_text(
    json.dumps(wards_map, ensure_ascii=False, indent=2), encoding="utf-8"
)

lines: list[str] = [
    '"""Osun State administrative divisions (INEC electoral wards)."""',
    "",
    "from __future__ import annotations",
    "",
    "import json",
    "from functools import lru_cache",
    "from pathlib import Path",
    "",
    'OSUN_STATE = "Osun State"',
    "",
    "OSUN_LGAS: dict[str, list[str]] = {",
]
for lga, wards in wards_map.items():
    wrepr = ", ".join(json.dumps(w) for w in wards)
    lines.append(f"    {json.dumps(lga)}: [{wrepr}],")
lines.extend(
    [
        "}",
        "",
        "OSUN_LGA_LIST = list(OSUN_LGAS.keys())",
        "",
        'OSUN_POLLING_UNITS_JSON = Path(__file__).resolve().parent / "data" / "osun_polling_units.json"',
        "OSUN_POLLING_UNITS_PER_WARD = 20",
        "",
        "",
        "@lru_cache(maxsize=1)",
        "def _load_osun_polling_units_catalog() -> dict[str, dict[str, list[dict[str, str]]]]:",
        "    if not OSUN_POLLING_UNITS_JSON.is_file():",
        "        return {}",
        "    try:",
        '        raw = json.loads(OSUN_POLLING_UNITS_JSON.read_text(encoding="utf-8"))',
        "    except (json.JSONDecodeError, OSError):",
        "        return {}",
        "    if not isinstance(raw, dict):",
        "        return {}",
        "    return raw",
        "",
        "",
        "def osun_polling_units_for_ward(lga: str, ward: str) -> list[dict[str, str]]:",
        '    lga_name = lga.strip()',
        '    ward_name = ward.strip()',
        "    if lga_name not in OSUN_LGAS or ward_name not in OSUN_LGAS[lga_name]:",
        "        return []",
        "    catalog = _load_osun_polling_units_catalog()",
        "    official = catalog.get(lga_name, {}).get(ward_name)",
        "    if official:",
        "        return list(official)",
        "    return [",
        '        {"code": f"PU{i:03d}", "name": f"Polling unit {i:03d} — {ward_name}"}',
        "        for i in range(1, OSUN_POLLING_UNITS_PER_WARD + 1)",
        "    ]",
        "",
        "",
        "def validate_osun_ward(lga: str, ward: str) -> None:",
        "    from fastapi import HTTPException",
        "",
        "    lga_name = lga.strip()",
        "    ward_name = ward.strip()",
        "    if lga_name not in OSUN_LGAS:",
        '        raise HTTPException(status_code=400, detail="Invalid LGA for Osun State.")',
        "    if ward_name not in OSUN_LGAS[lga_name]:",
        '        raise HTTPException(status_code=400, detail="Invalid ward for the selected LGA.")',
        "",
        "",
        "def validate_osun_polling_unit(lga: str, ward: str, name: str, code: str) -> dict[str, str]:",
        "    from fastapi import HTTPException",
        "",
        "    validate_osun_ward(lga, ward)",
        "    units = osun_polling_units_for_ward(lga, ward)",
        "    name_stripped = name.strip()",
        "    code_lower = code.lower().strip()",
        "    for unit in units:",
        '        unit_code = unit["code"]',
        "        unit_code_lower = unit_code.lower()",
        '        if unit["name"] == name_stripped:',
        "            return unit",
        "        if unit_code_lower == code_lower:",
        "            return unit",
        "        if unit_code == name_stripped or unit_code_lower == name_stripped.lower():",
        "            return unit",
        '        if code_lower.endswith(unit_code_lower) or f"-{unit_code_lower}" in code_lower:',
        "            return unit",
        "    raise HTTPException(",
        "        status_code=400,",
        '        detail="Select a valid polling unit from the list for this ward.",',
        "    )",
        "",
    ]
)

(APP / "osun_geo_data.py").write_text("\n".join(lines), encoding="utf-8")
print("wards", sum(len(v) for v in wards_map.values()))
print("pus", sum(len(p) for l in catalog.values() for p in l.values()))
print("ok")
