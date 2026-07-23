"""Osun State administrative divisions (INEC electoral wards)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

OSUN_STATE = "Osun State"

OSUN_LGAS: dict[str, list[str]] = {
    "Atakumosa East": ["Iwara", "Igangan", "Ipole", "Iperindo", "Eti-Oni", "Ayegunle", "Forest Reserve I", "Forest Reserve II", "Faforiji", "Ajebandele"],
    "Atakumosa West": ["Osu I", "Osu II", "Osu III", "Ibodi", "Ifelodun", "Ita Gunmodi", "Oke Bode", "Isa Obi", "Muroko", "Ifewara I", "Ifewara II"],
    "Ayedaade": ["Balogun", "Otun Balogun", "Olufi", "Otun-Olufi", "Ijegbe/Oke-Eso/Oke-Owu Ijugbe", "Lagere/Amola", "Gbongan Rural", "Ode-Omu Rural", "Obalufon", "Anlugbua", "Araromi-Owu"],
    "Ayedire": ["Oluponna I", "Oluponna II", "Oluponna III", "Oke-Osun", "Ileogbo I", "Ileogbo II", "Ileogbo III", "Ileogbo IV", "Kuta I", "Kuta II"],
    "Boluwaduro": ["Oke-Omi Otan", "Oke Ode Otan", "Oke-Otan", "Gbeleru Obaala I", "Gbeleru Obaala II", "Obala Iloro", "Eripa", "Oke-Irun", "Iresi I", "Iresi II"],
    "Boripe": ["Oloti Iragbiji", "College/Egbada Road", "Isale-Oyo", "Agba", "Ororuwo", "Ada I", "Ada II", "Isale Asa Iree", "Oke Esa/Oke Ogi", "Oke Aree", "Ward 11"],
    "Ede North": ["Olaba/Atapara", "Abogunde/Sagba", "Ologun/Agbaakin", "Olusokun", "Alusekere", "Sabo/Agbongbe I", "Sabo/Agbongbe II", "Isibo/Buari-Isola", "Apaso", "Asunmo", "Bara Ejemu"],
    "Ede South": ["Babanla/Agate", "Kuye", "Jagun/Jagun", "Alajue I", "Alajue II", "Olodan", "Babasanya", "Sekona", "Oloki/Akoda", "Loogun"],
    "Egbedore": ["Awo/Abudo", "Ara I", "Ara II", "Ido-Osun", "Ira Gberi I", "Ira Gberi II", "Iwoye/Idoo/Origo", "Ikotun", "Ojo/Aro", "Okin Ni/Olorunsogo/Ofatedo"],
    "Ejigbo": ["Elejigbo/Ayegbogbo", "Ola/Aye/Agurodo", "Ilawo/Isoko/Isundunrin", "Inisa I/Aato/Igbon", "Inisa II/Afaake/Ayegunle", "Ward 06", "Ward 07", "Ward 08", "Ward 09", "Ward 10", "Ward 11"],
    "Ife Central": ["Ilare I", "Ilare II", "Ilare III", "Ilare IV", "Iremo/Ajebandele", "Iremo III", "Iremo IV", "Iremo V", "Akarabata", "Moore Ojaja", "Ward 11"],
    "Ifedayo": ["Oyi", "Ayetoro", "Isinmi", "Balogun", "Obaale", "Aworo/Oke-Ila Rural", "Asaoni", "Co-Operative", "Akesin", "Temidire"],
    "Ife East": ["Moore", "Ilode I", "Ilode II", "Okerewe I", "Okerewe II", "Okerewe III", "Yekemi", "Modakeke I", "Modakeke II", "Modakeke III"],
    "Ifelodun": ["Eesa Ikirun", "Amola Ikirun", "Owode Ikirun", "Isale/Oke Afo", "Ikirun Rural", "Okeba Ikirun", "Olonde Ikirun", "Iba I", "Iba II", "Obagun", "Ekoende/Eko Ajala", "Ward 12"],
    "Ife North": ["Asipa/Akinlalu", "Edunabon I", "Edunabon II", "Famia", "Yakoyo", "Ipetumodu I", "Ipetumodu II", "Moro", "Oyere I", "Oyere II"],
    "Ife South": ["Ayesan", "Ikija I", "Ikija II", "Aare", "Mefoworade", "Oke Owena", "Olode", "Osi", "Kere", "Abiri Ogudu", "Aye"],
    "Ila": ["Ejigbo I", "Ejigbo II", "Ejigbo III", "Isedo I", "Isedo II", "Iperin", "Eyindi", "Oke Ola", "Oke Ede", "Eyindi/Iperin", "Ajaba/Edemosi/Aba Orangun"],
    "Ilesha East": ["Okesa", "Imo", "Ifosan/Oke-Eso", "Itisin/Ogudu", "Ijamo", "Iloro/Roye", "Isare", "Ilerin", "Bolorunduro", "Biladu", "Ward 11"],
    "Ilesha West": ["Itakogun/Upper Egbe-Idi", "Lower Egbe-Idi", "Upper/Lower Igbogi", "Omofe/Idasa", "Isokun", "Ikoyi / Ikoti Araromi", "Ilaje", "Isida/Adeti", "Ereja", "Ayeso"],
    "Irepodun": ["Ilobu I", "Ilobu II", "Ilobu III", "Ilobu IV", "Erin I", "Erin II", "Erin III", "Ifon I", "Ifon II", "Ifon III", "Station Road"],
    "Irewole": ["Ikire I", "Ikire II", "Ikire III", "Ikire IV", "Ikire V", "Ikire VI", "Ikire VII", "Ikire VIII", "Ikire IX", "Ikire X", "Ikire XI"],
    "Isokan": ["Asalu Ikoyi", "Oranran Ward", "Idogun Ward", "Alapomu II", "Oosa Adifa", "Awala I", "Awala II", "Ward 08", "Ward 09", "Ward 10", "Ward 11"],
    "Iwo": ["Isale Oba I", "Isale Oba II", "Isale Oba III", "Isale Oba IV", "Molete I", "Molete II", "Molete III", "Oke-Adan I", "Oke-Adan II", "Oke-Adan III", "Gidigbo I", "Gidigbo II", "Gidigbo III", "Oke-Oba I", "Oke-Oba II"],
    "Obokun": ["Ibokun", "Ipetu-Ile/Adaowode", "Ilahun/Ikinyinwa", "Ilase/Idominasi", "Eesun/Idooko", "Imesi-Ile", "Esa-Oke", "Otan-Ile", "Ilare", "Ward 10"],
    "Odo-Otin": ["Oba Ojomu", "Baale", "Igbaye", "Faji/Opete", "Ekosin/Iyeku", "Ore/Agbeye", "Ijabe/Ila Odo", "Okua/Ekusa", "Asi/Asaba", "Olunisa", "Olukotun", "Esa Otun Baale Ode", "Jagun Osi Bale Ode", "Oloyan Elemosho / Esa", "Osolo/Oparin/Ola"],
    "Ola-Oluwa": ["Telemu", "Asamu/Ilemowu", "Ogbaagba I", "Ogbaagba II", "Ikire Ile/Iwara", "Isero/Ikonifin", "Obamoro/Ile Ogo", "Bode-Osi", "Ajagba/Iwooke", "Asa Ajagunlase"],
    "Olorunda": ["Agowande", "Balogun", "Akogun", "Atelewo", "Owoope", "Owode I", "Owode II", "Ayetoro", "Oba-Ile", "Oba Oke", "Ilie"],
    "Oriade": ["Erin-Oke", "Erin-Ijesa", "Ijebu-Jesa", "Iwoye", "Ikeji-Ile", "Ira", "Ijeji Arakeji/Owena", "Apoti Dagbaja", "Ipetu Ijesa I", "Ipetu-Ijesa II", "Ijeda Iloko", "Erinmo/Iwaraja"],
    "Orolu": ["Ifon-Osun I", "Ifon-Osun II", "Ifon-Osun III", "Ifon-Osun IV", "Ifon-Osun V", "Ifon-Osun VI", "Ifon-Osun VII", "Ifon-Osun VIII", "Ifon-Osun IX", "Ifon-Osun X"],
    "Osogbo": ["Otun Hagun B", "Alagba", "Are-Ago", "Baba Kekere", "Eketa", "Ekerin", "Ward 07", "Ward 08", "Ward 09", "Ward 10", "Ward 11", "Ward 12", "Ward 13", "Ward 14", "Ward 15"],
}

OSUN_LGA_LIST = list(OSUN_LGAS.keys())

OSUN_POLLING_UNITS_JSON = Path(__file__).resolve().parent / "data" / "osun_polling_units.json"
OSUN_POLLING_UNITS_PER_WARD = 20


@lru_cache(maxsize=1)
def _load_osun_polling_units_catalog() -> dict[str, dict[str, list[dict[str, str]]]]:
    if not OSUN_POLLING_UNITS_JSON.is_file():
        return {}
    try:
        raw = json.loads(OSUN_POLLING_UNITS_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def osun_polling_units_for_ward(lga: str, ward: str) -> list[dict[str, str]]:
    lga_name = lga.strip()
    ward_name = ward.strip()
    if lga_name not in OSUN_LGAS or ward_name not in OSUN_LGAS[lga_name]:
        return []
    catalog = _load_osun_polling_units_catalog()
    official = catalog.get(lga_name, {}).get(ward_name)
    if official:
        return list(official)
    return [
        {"code": f"PU{i:03d}", "name": f"Polling unit {i:03d} — {ward_name}"}
        for i in range(1, OSUN_POLLING_UNITS_PER_WARD + 1)
    ]


def validate_osun_ward(lga: str, ward: str) -> None:
    from fastapi import HTTPException

    lga_name = lga.strip()
    ward_name = ward.strip()
    if lga_name not in OSUN_LGAS:
        raise HTTPException(status_code=400, detail="Invalid LGA for Osun State.")
    if ward_name not in OSUN_LGAS[lga_name]:
        raise HTTPException(status_code=400, detail="Invalid ward for the selected LGA.")


def validate_osun_polling_unit(lga: str, ward: str, name: str, code: str) -> dict[str, str]:
    from fastapi import HTTPException

    validate_osun_ward(lga, ward)
    units = osun_polling_units_for_ward(lga, ward)
    name_stripped = name.strip()
    code_lower = code.lower().strip()
    for unit in units:
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
