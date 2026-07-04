"""Ogun State administrative divisions (INEC electoral wards)."""

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

# Official INEC polling units by LGA -> ward -> [{code, name}].
# Wards without an entry fall back to generated PU 001–020 placeholders.
OGUN_POLLING_UNITS: dict[str, dict[str, list[dict[str, str]]]] = {
    "Odeda": {
        "Odeda": [
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
        ],
    },
    "Abeokuta South": {
        "Ibara I": [
            {"code": "27-02-14-001", "name": "OPEN SPACE NEAR MERCY HOSPITAL"},
            {"code": "27-02-14-002", "name": "O.L.L. PRIMARY SCHOOL ONIKOKO"},
            {"code": "27-02-14-003", "name": "OPEN SPACE 'SARAKI ILUPEJU ADIGBE I"},
            {"code": "27-02-14-004", "name": "OPEN SPACE SARAKI ILUPEJU ADIGBE II"},
            {"code": "27-02-14-005", "name": "OPEN SPACE NEAR SAFARI JUNCTION"},
            {"code": "27-02-14-006", "name": "HOUSING ESTATE PRY. SCH. ONIKOLOBO I"},
            {"code": "27-02-14-007", "name": "HOUSING ESTATE PRY. SCH. ONIKOLOBO II"},
            {"code": "27-02-14-008", "name": "OPEN SPACE NEAR BAYEWUNMI HOUSE I"},
            {"code": "27-02-14-009", "name": "ST. PAULS DEMONSTRATION SCHOOL SODUBI I"},
            {"code": "27-02-14-010", "name": "ST. PAULS DEMONSTRATION SCHOOL SODUBI II"},
            {"code": "27-02-14-011", "name": "IJEMO TITUN HIGH SCHOOL"},
            {"code": "27-02-14-012", "name": "OPEN SPACE AT OLOKEMEJI I"},
            {"code": "27-02-14-013", "name": "ANGLICAN HIGH SCHOOL IBARA I"},
            {"code": "27-02-14-014", "name": "ANGLICAN HIGH SCHOOL IBARA II"},
            {"code": "27-02-14-015", "name": "OPEN SPACE NEAR CHIEF OMOLOLU'S HOUSE"},
            {"code": "27-02-14-016", "name": "OPEN SPACE NEAR SARAKI BUS-STOP ADIGBE"},
            {"code": "27-02-14-017", "name": "OPEN SPACE NEAR MERCY HOSPITAL"},
            {"code": "27-02-14-018", "name": "OPEN SPACE NEAR BAALE'S HOUSE OLOKEMEJI"},
            {"code": "27-02-14-019", "name": "OPEN SPACE OPP. OF KAT STAR GUEST IYANA OLOKE"},
            {"code": "27-02-14-020", "name": "OPEN SPACE ADJCENT WAEC OFFICE ONIKOLOBO"},
            {"code": "27-02-14-021", "name": "OPEN SPACE, ENIOLA JUNCTION, MERCY HOSP. ROAD"},
            {"code": "27-02-14-022", "name": "T. JUNCTION LEMOMU AYENI CLOSE OLUWO"},
            {"code": "27-02-14-023", "name": "PARAMOUNT VILLA JUNCTION IREPODUN C.D.A OLUWO"},
            {"code": "27-02-14-024", "name": "T-JUNCTION BESIDE TRANSFORMER ATOBATELE ONIKOKO"},
            {"code": "27-02-14-025", "name": "ODEMO JUNCTION NEAR C.A.C CHURCH SARAKI"},
            {"code": "27-02-14-026", "name": "OPEN SPACE OMOWE PHASE II SARAKI"},
            {"code": "27-02-14-027", "name": "OPEN SPACE NEAR CELE IRAPADA SURULERE SARAKI"},
            {"code": "27-02-14-028", "name": "OPEN SPACE BEIND CHRIST LEGACY SCHOOL, ALAWAYE SARAKI"},
            {"code": "27-02-14-029", "name": "TOTAL CHILD ONIKOLOBO"},
            {"code": "27-02-14-030", "name": "OPEN SPACE AT FAN MILK PANSEKE, ONIKOKO"},
            {"code": "27-02-14-031", "name": "OPEN SPACE, FIRST GATE LIPEDE ESTATE, ONIKOKO"},
            {"code": "27-02-14-032", "name": "OPEN SPACE BEHIND NEW SPRING ROSE SCHOOL, QUARRY"},
            {"code": "27-02-14-033", "name": "OPEN SPACE, OLD SAVANNAH BANK QUARRY"},
            {"code": "27-02-14-034", "name": "OPP. ABDUL-AZEEZ MOSQUE KUFORIJI JUNCTION, ADIGBE"},
            {"code": "27-02-14-035", "name": "IYANA VULCANIZER NEAR AJEGUNLE CENTRAL MOSQUE ADIGBE"},
            {"code": "27-02-14-036", "name": "ARAROMI JUNCTION BESIDE NAVY SCH."},
            {"code": "27-02-14-037", "name": "OPEN SPACE IFAMODUPE STREET SARAKI"},
            {"code": "27-02-14-038", "name": "OPEN SPACE NEAR BABA ASIKO STREET SARAKI"},
            {"code": "27-02-14-039", "name": "OPEN SPACE GREEN LAND'S ACADEMY SCHOOL"},
        ],
    },
}

# Placeholder count for wards without official INEC data yet.
POLLING_UNITS_PER_WARD = 20


def polling_units_for_ward(lga: str, ward: str) -> list[dict[str, str]]:
    """Return selectable polling units for an LGA/ward."""
    lga_name = lga.strip()
    ward_name = ward.strip()
    if lga_name not in OGUN_LGAS or ward_name not in OGUN_LGAS[lga_name]:
        return []

    official = OGUN_POLLING_UNITS.get(lga_name, {}).get(ward_name)
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
        if unit_code == name_stripped or unit_code_lower == name_stripped.lower():
            return unit
        if code_lower.endswith(unit_code_lower) or f"-{unit_code_lower}" in code_lower:
            return unit

    raise HTTPException(
        status_code=400,
        detail="Select a valid polling unit from the list for this ward.",
    )
