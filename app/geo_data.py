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


def validate_ogun_ward(lga: str, ward: str) -> None:
    from fastapi import HTTPException

    lga_name = lga.strip()
    ward_name = ward.strip()
    if lga_name not in OGUN_LGAS:
        raise HTTPException(status_code=400, detail="Invalid LGA for Ogun State.")
    if ward_name not in OGUN_LGAS[lga_name]:
        raise HTTPException(status_code=400, detail="Invalid ward for the selected LGA.")
