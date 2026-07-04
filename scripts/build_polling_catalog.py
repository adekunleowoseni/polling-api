"""Build ogun_polling_units.json from INEC directory + Media Nigeria updates."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.geo_data import OGUN_LGAS  # noqa: E402

INEc_PATH = ROOT / "data" / "inec_ogun_pu_directory.txt"
OUTPUT_PATH = ROOT / "app" / "data" / "ogun_polling_units.json"
MEDIA_NIGERIA_DIR = ROOT / "data" / "media_nigeria"

# INEC LGA name (upper) -> our canonical LGA key
LGA_MAP = {
    "ABEOKUTA NORTH": "Abeokuta North",
    "ABEOKUTA SOUTH": "Abeokuta South",
    "ADO ODO/OTA": "Ado-Odo/Ota",
    "ADO ODO OTA": "Ado-Odo/Ota",
    "EGBADO NORTH": "Egbado North",
    "YEWA NORTH": "Egbado North",
    "EGBADO SOUTH": "Egbado South",
    "YEWA SOUTH": "Egbado South",
    "EWEKORO": "Ewekoro",
    "IFO": "Ifo",
    "IJEBU EAST": "Ijebu East",
    "IJEBU NORTH": "Ijebu North",
    "IJEBU NORTH EAST": "Ijebu North East",
    "IJEBU ODE": "Ijebu Ode",
    "IKENNE": "Ikenne",
    "IMEKO AFON": "Imeko Afon",
    "IPOKIA": "Ipokia",
    "OBAFEMI OWODE": "Obafemi Owode",
    "ODEDA": "Odeda",
    "ODOGBOLU": "Odogbolu",
    "OGUN WATERSIDE": "Ogun Waterside",
    "REMO NORTH": "Remo North",
    "SAGAMU": "Sagamu",
    "SHAGAMU": "Sagamu",
}

# Explicit INEC/normalized ward -> canonical ward overrides per LGA
WARD_ALIASES: dict[str, dict[str, str]] = {
    "Abeokuta North": {
        "ILUGUN IBEREKODO": "Ilugun",
        "ITA OSHIN OLOMORE": "Itaoshin",
        "OLORUNDA IJALE": "Olorunda",
        "IMALA IDIEMI": "Imale",
        "ISAGA ILEWO": "Isaga",
        "IBARA ORILE ONISASA": "Ibara Orile",
        "TOTORO SOKORI": "Totoro",
    },
    "Abeokuta South": {
        "IJEMO": "Ijero",
        "ERUNBE OKE IJEUN": "Erunba",
        "AGO EGUN IJESA": "Ago Egun",
        "IGBORE AGO OBA": "Ibore",
        "IJAYE IDI ABA": "Ijaiye/Idi Apa",
        "SODEKE SALE IJEUN I": "Sodeke I",
        "SODEKE SALE IJEUN II": "Sodeke II",
    },
    "Ado-Odo/Ota": {
        "ADO ODO I": "Ado Odo I",
        "ADO ODO II": "Ado Odo II",
        "AGBARA EJILA AWORI": "Agbara II",
    },
    "Egbado North": {
        "OHUNBE": "Ehunbe",
        "IGUA": "Ibuha",
        "IJOUN": "Ijoho",
    },
    "Egbado South": {
        "OKE ODAN": "Okeodan",
    },
    "Ifo": {
        "OSOSUN": "Osunsun",
    },
    "Ijebu North East": {
        "ATAN IMUKU": "Atan/Imuku",
        "ODOSIMADEGUN ODOSEBORA": "Odosimadegun Odosebora",
        "IMEWIRO ODODEYO IMOMO": "Iwewiro",
    },
    "Ijebu Ode": {
        "ISOKU OSOSA": "Isoku/Ososa",
        "ODO EGBO OLIWORO": "Odo Ise",
    },
    "Ikenne": {
        "ILISAN I": "Ilasa I",
        "ILISAN II": "Ilasa II",
        "ILISAN IROLU": "Ilisa/Oralu",
    },
    "Ipokia": {
        "IHUNBO ILASE": "Ihumbo",
    },
    "Obafemi Owode": {
        "MOLOKO ASIPA": "Moloko-Asipa",
        "EGBEDA": "Egbada",
    },
    "Odogbolu": {
        "OGBO MORAIKA ITA EPO I": "Ogbo/Morarika",
        "OGBO MORAIKA ITA EPO II": "Ogbo/Morarika",
        "OSOSA": "Osasa",
    },
    "Remo North": {
        "MOBORODE OKE OLA": "Moborode/Oke Ola",
        "ODOFIN IMAGBO PETEKUN DAWARA": "Odofin/Imagbo",
    },
    "Sagamu": {
        "OKO EPE ITULA I": "Oko/Epe/Itula I",
        "OKO EPE ITULA II": "Oko Epe Itula II",
        "IBIDO ITUWA ALARA": "Ibido/Ituwa/Alara",
        "AYEGBAMI IJOKUN": "Aiyegbami",
    },
    "Ewekoro": {
        "ELERE ONIGBEDU": "Elere/Onigbedu",
    },
}

MEDIA_LGA_SLUGS = {
    "Abeokuta North": "abeokuta-north-l-g-a-polling-units-wards",
    "Abeokuta South": "abeokuta-south-l-g-a-polling-units-wards",
    "Ado-Odo/Ota": "ado-odo-ota-l-g-a-polling-units-wards",
    "Egbado North": "yewa-north-l-g-a-polling-units-wards",
    "Egbado South": "yewa-south-l-g-a-polling-units-wards",
    "Ewekoro": "ewekoro-l-g-a-polling-units-wards",
    "Ifo": "ifo-l-g-a-polling-units-wards",
    "Ijebu East": "ijebu-east-l-g-a-polling-units-wards",
    "Ijebu North": "ijebu-north-l-g-a-polling-units-wards",
    "Ijebu North East": "ijebu-north-east-l-g-a-polling-units-wards",
    "Ijebu Ode": "ijebu-ode-l-g-a-polling-units-wards",
    "Ikenne": "ikenne-l-g-a-polling-units-wards",
    "Imeko Afon": "imeko-afon-l-g-a-polling-units-wards",
    "Ipokia": "ipokia-l-g-a-polling-units-wards",
    "Obafemi Owode": "obafemi-owode-l-g-a-polling-units-wards",
    "Odeda": "odeda-l-g-a-polling-units-wards",
    "Odogbolu": "odogbolu-l-g-a-polling-units-wards",
    "Ogun Waterside": "ogun-waterside-l-g-a-polling-units-wards",
    "Remo North": "remo-north-l-g-a-polling-units-wards",
    "Sagamu": "shagamu-l-g-a-polling-units-wards",
}


def norm(text: str) -> str:
    text = text.upper().replace("‐", "-").replace("–", "-").replace("—", "-")
    text = text.replace("/", " ").replace("-", " ")
    text = re.sub(r"[^A-Z0-9 ]", "", text)
    return " ".join(text.split())


def resolve_lga(name: str) -> str | None:
    key = norm(name)
    for inec_name, canonical in LGA_MAP.items():
        if norm(inec_name) == key:
            return canonical
    return None


def match_canonical_ward(lga: str, inec_ward: str) -> str | None:
    aliases = WARD_ALIASES.get(lga, {})
    key = norm(inec_ward)
    if key in aliases:
        return aliases[key]

    our_wards = OGUN_LGAS.get(lga, [])
    for ward in our_wards:
        if norm(ward) == key:
            return ward

    for ward in our_wards:
        wn = norm(ward)
        if wn in key or key in wn:
            return ward

    # Token overlap fallback
    key_tokens = set(key.split())
    best: tuple[int, str] | None = None
    for ward in our_wards:
        wt = set(norm(ward).split())
        overlap = len(key_tokens & wt)
        if overlap and (best is None or overlap > best[0]):
            best = (overlap, ward)
    if best and best[0] >= 1:
        return best[1]
    return None


def parse_inec_directory(text: str) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Parse INEC PDF text into {lga: {ward: [{code, name}]}}."""
    result: dict[str, dict[str, list[dict[str, str]]]] = {}
    current_lga: str | None = None
    current_lga_code: str | None = None
    current_ward: str | None = None
    current_ward_code: str | None = None

    skip_exact = {
        "INEC Nigeria Directory of Polling Units",
        "OGUN STATE",
        "PU Name [NOTE: The old name/location of relocated PUs appear in parenthesis] CODE",
        "RA:",
        "THE LIST OF REGISTRATION AREAS IN THE LOCAL",
        "GOVERNMENT AREA",
        "NAME Code",
        "LGA:",
        "# of PUs",
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("INEC Nigeria Directory"):
            continue
        if line.startswith("TOTAL:") or line.startswith("TOTAL PUs:"):
            continue
        if line in skip_exact:
            continue

        m_lga_line = re.match(r"^LGA:\s*(.+?)\s+Code:\s*(\d{2})$", line)
        if m_lga_line:
            current_lga = resolve_lga(m_lga_line.group(1).strip())
            current_lga_code = m_lga_line.group(2)
            if current_lga:
                result.setdefault(current_lga, {})
            current_ward = None
            current_ward_code = None
            continue

        resolved = resolve_lga(line)
        if resolved:
            current_lga = resolved
            result.setdefault(current_lga, {})
            current_ward = None
            continue

        m_lga_code_only = re.match(r"^Code:\s*(\d{2})$", line)
        if m_lga_code_only and current_lga:
            current_lga_code = m_lga_code_only.group(1)
            continue

        m_ward = re.match(r"^(.+?)\s+Code:\s*(\d{2})$", line)
        if m_ward and current_lga and current_lga_code:
            ward_raw = m_ward.group(1).strip()
            if ward_raw.upper() in {"RA", "PU NAME [NOTE: THE OLD NAME/LOCATION OF RELOCATED PUS APPEAR IN PARENTHESIS]"}:
                continue
            canonical = match_canonical_ward(current_lga, ward_raw)
            if canonical:
                current_ward = canonical
                current_ward_code = m_ward.group(2)
                result[current_lga].setdefault(current_ward, [])
            else:
                current_ward = None
                current_ward_code = None
            continue

        m_pu = re.match(r"^(.+?)\s+(\d{3})$", line)
        if m_pu and current_lga and current_ward and current_lga_code and current_ward_code:
            name = m_pu.group(1).strip()
            pu_num = m_pu.group(2)
            if name.upper().startswith("TOTAL PUS"):
                continue
            code = f"27-{current_lga_code}-{current_ward_code}-{pu_num}"
            result[current_lga][current_ward].append({"code": code, "name": name})

    return result


def parse_media_nigeria_ward_block(ward_title: str, body: str) -> list[dict[str, str]]:
    """Parse '001 – NAME002 – NAME' blocks from Media Nigeria pages."""
    parts = re.split(r"(\d{3})\s*[–\-]\s*", body)
    if len(parts) < 3:
        return []
    units: list[dict[str, str]] = []
    for i in range(1, len(parts), 2):
        num, name = parts[i], parts[i + 1].strip()
        name = re.split(r"\d{3}\s*[–\-]\s*", name)[0].strip()
        name = re.sub(r"\s+", " ", name)
        if name:
            units.append({"code": num, "name": name})
    return units


def parse_media_nigeria_page(text: str) -> dict[str, list[dict[str, str]]]:
    """Extract wards and polling units from a Media Nigeria LGA page."""
    wards: dict[str, list[dict[str, str]]] = {}
    chunks = re.split(r"\n(?=[A-Za-z].*Ward\s*\n)", text, flags=re.IGNORECASE)
    for chunk in chunks:
        m = re.match(r"^(.+?)\s+Ward\s*\n+\(\s*\d+\s*Polling", chunk, re.IGNORECASE | re.DOTALL)
        if not m:
            continue
        ward_title = m.group(1).strip()
        body_match = re.search(r"\(\s*\d+\s*Polling[^\n]*\n+(.*)", chunk, re.IGNORECASE | re.DOTALL)
        if not body_match:
            continue
        body = body_match.group(1)
        body = re.split(r"\n#{1,3}\s|\nList Of |\n#### ", body)[0]
        units = parse_media_nigeria_ward_block(ward_title, body)
        if units:
            wards[ward_title] = units
    return wards


def apply_media_nigeria_overrides(
    catalog: dict[str, dict[str, list[dict[str, str]]]],
    lga: str,
    media_wards: dict[str, list[dict[str, str]]],
    lga_code: str,
) -> None:
    """Replace ward lists with Media Nigeria 2023 data when available."""
    ward_code_map: dict[str, str] = {}
    # Build ward code map from existing INEC entries
    for ward, units in catalog.get(lga, {}).items():
        if units:
            m = re.match(r"27-(\d{2})-(\d{2})-\d{3}", units[0]["code"])
            if m:
                ward_code_map[ward] = m.group(2)

    for media_ward, units in media_wards.items():
        canonical = match_canonical_ward(lga, media_ward.replace(" Ward", ""))
        if not canonical:
            continue
        wcode = ward_code_map.get(canonical, "00")
        catalog.setdefault(lga, {})[canonical] = [
            {
                "code": f"27-{lga_code}-{wcode}-{u['code']}",
                "name": u["name"],
            }
            for u in units
        ]


def load_media_nigeria_pages() -> None:
    """Fetch and cache Media Nigeria pages (optional — uses cache if present)."""
    try:
        import httpx
    except ImportError:
        return

    MEDIA_NIGERIA_DIR.mkdir(parents=True, exist_ok=True)
    for lga, slug in MEDIA_LGA_SLUGS.items():
        cache = MEDIA_NIGERIA_DIR / f"{slug}.txt"
        if cache.exists():
            continue
        url = f"https://www.medianigeria.com/{slug}/"
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            cache.write_text(resp.text, encoding="utf-8")
            print(f"Fetched {lga}")
        except Exception as exc:
            print(f"Skip fetch {lga}: {exc}")


def merge_media_nigeria(catalog: dict[str, dict[str, list[dict[str, str]]]]) -> None:
    if not MEDIA_NIGERIA_DIR.exists():
        return
    lga_codes = {}
    for lga, wards in catalog.items():
        for units in wards.values():
            if units:
                m = re.match(r"27-(\d{2})-", units[0]["code"])
                if m:
                    lga_codes[lga] = m.group(1)
                    break

    for lga, slug in MEDIA_LGA_SLUGS.items():
        cache = MEDIA_NIGERIA_DIR / f"{slug}.txt"
        if not cache.exists():
            continue
        text = cache.read_text(encoding="utf-8", errors="ignore")
        # Strip HTML tags crudely for parsing
        text = re.sub(r"<[^>]+>", "\n", text)
        text = re.sub(r"\n+", "\n", text)
        media_wards = parse_media_nigeria_page(text)
        if media_wards and lga in lga_codes:
            apply_media_nigeria_overrides(catalog, lga, media_wards, lga_codes[lga])
            print(f"Media Nigeria override: {lga} ({len(media_wards)} wards)")


def apply_manual_overrides(catalog: dict[str, dict[str, list[dict[str, str]]]]) -> None:
    """Keep user-provided Odeda/Odeda extended list."""
    odeda_ward = [
        {"code": "27-16-01-001", "name": "ODEDA MARKET I"},
        {"code": "27-16-01-002", "name": "ODEDA MARKET II"},
        {"code": "27-16-01-003", "name": "IKA AINA TITUN VILLAGE"},
        {"code": "27-16-01-004", "name": "ROGUN PRY. SCHOOL"},
        {"code": "27-16-01-005", "name": "OGIJAN VILLAGE"},
        {"code": "27-16-01-006", "name": "OGBOYE PRY. SCHOOL"},
        {"code": "27-16-01-007", "name": "ARALAMO VILLAGE"},
        {"code": "27-16-01-008", "name": "OLUGBO MARKET"},
        {"code": "27-16-01-009", "name": "ILE-OLU, PRY. SCHOOL"},
        {"code": "27-16-01-010", "name": "BAALE OGUNBAYO"},
        {"code": "27-16-01-011", "name": "OLUGA PRY. SCHOOL"},
        {"code": "27-16-01-012", "name": "AREGE PRY. SCHOOL"},
        {"code": "27-16-01-013", "name": "SANYAOLU OLOBE"},
        {"code": "27-16-01-014", "name": "ILAGBE VILLAGE"},
        {"code": "27-16-01-015", "name": "OGBOYE PRY. SCHOOL II"},
        {"code": "27-16-01-016", "name": "OPEN SPACE BESIDE OLU ODEDA PALACE"},
        {"code": "27-16-01-017", "name": "INFRONT OF MINISTRY OF YOUTH AND AGRO SERVICE"},
        {"code": "27-16-01-018", "name": "ST PAUL ANG SCHOOL SOKAN, ODEDA"},
        {"code": "27-16-01-019", "name": "ST SAVIOURS ANGLICAN PRY SCHOOL OLUGBO"},
        {"code": "27-16-01-020", "name": "OPEN SPACE AT APATA VILLAGE VIA OLUGA"},
        {"code": "27-16-01-021", "name": "ST PETERS ANGLICAN PRY SCHOOL, ILE OLU"},
        {"code": "27-16-01-022", "name": "OPEN SPACE AT OGELEJE VILAGE"},
        {"code": "27-16-01-023", "name": "OPEN SPACE AT THE BACK OF POLICE BARRACK ODEDA"},
        {"code": "27-16-01-024", "name": "OPEN SPACE AT IWAYE ODEDA"},
        {"code": "27-16-01-025", "name": "OPEN SPACE OPPOSITE MINISTRY OF AGRIC EWEJE"},
    ]
    catalog.setdefault("Odeda", {})["Odeda"] = odeda_ward


def main() -> None:
    if not INEc_PATH.exists():
        print(f"Missing {INEc_PATH}")
        sys.exit(1)

    print("Loading INEC directory…")
    text = INEc_PATH.read_text(encoding="utf-8", errors="ignore")
    catalog = parse_inec_directory(text)

    print("Fetching Media Nigeria pages (cached)…")
    load_media_nigeria_pages()
    merge_media_nigeria(catalog)
    apply_manual_overrides(catalog)

    # Stats
    total_pus = sum(len(units) for lga in catalog.values() for units in lga.values())
    wards_covered = sum(len(lga) for lga in catalog.values())
    missing: list[str] = []
    for lga, wards in OGUN_LGAS.items():
        for ward in wards:
            if not catalog.get(lga, {}).get(ward):
                missing.append(f"{lga} / {ward}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH}")
    print(f"LGAs: {len(catalog)}, wards: {wards_covered}, polling units: {total_pus}")
    if missing:
        print(f"Wards still missing official data ({len(missing)}):")
        for item in missing[:20]:
            print(f"  - {item}")
        if len(missing) > 20:
            print(f"  … and {len(missing) - 20} more")


if __name__ == "__main__":
    main()
