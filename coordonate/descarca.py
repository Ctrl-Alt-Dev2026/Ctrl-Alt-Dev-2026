"""Descărcarea datelor OSM cu osmnx și construirea indexului local.

Rulează o singură dată (sau când vreți date OSM mai noi):

    .venv\\Scripts\\python -m coordonate descarca

Rezultă două fișiere în `date_referinta/osm/`:
- `index_osm.json.gz` — străzi (cu nodurile OSM reale, ca intersecțiile să se
  poată verifica prin **nod comun**), treceri de pietoni, repere (POI),
  cartiere/localități și adrese cu număr;
- `unitati_admin.geojson` — granițele municipiului Iași și ale comunelor din
  jur, pentru `in_iasi`.

După asta, rezolvarea locațiilor nu mai face nicio cerere în rețea.
Date © OpenStreetMap contributors, ODbL 1.0.
"""

from __future__ import annotations

import gzip
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import config
from .geometrie import distanta_m
from .normalizare import cheie_nume

# Străzile cu nume pe care pot circula vehicule (aici se lovesc pietonii).
# Fără footway/path/cycleway: nu au intersecții „X cu Y” relatate în presă.
FILTRU_STRAZI = (
    '["highway"]["name"]["area"!~"yes"]'
    '["highway"!~"footway|path|cycleway|steps|track|bridleway|corridor|proposed|'
    'construction|abandoned|platform|raceway|bus_guideway|elevator|via_ferrata"]'
)

ETICHETE_NUME = ("name", "name:ro", "alt_name", "old_name", "short_name", "official_name", "loc_name")

ETICHETE_POI: dict[str, Any] = {
    "amenity": True,
    "shop": True,
    "tourism": True,
    "leisure": True,
    "healthcare": True,
    "historic": True,
    "office": True,
    "public_transport": ["station", "platform", "stop_position"],
    "railway": ["station", "halt", "tram_stop"],
    "highway": ["bus_stop"],
}
CLASE_POI = tuple(ETICHETE_POI)

TIPURI_LOC = [
    "city", "town", "village", "hamlet", "suburb", "quarter", "neighbourhood",
    "locality", "isolated_dwelling", "square", "city_block",
]


def _jurnal(mesaj: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {mesaj}", flush=True)


def _configureaza_osmnx():
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.cache_folder = str(config.DIR_CACHE / "osmnx")
    ox.settings.log_console = False
    ox.settings.http_user_agent = config.USER_AGENT
    ox.settings.overpass_url = config.OVERPASS_URL
    ox.settings.requests_timeout = config.TIMEOUT_DESCARCARE_SEC
    ox.settings.useful_tags_node = ["highway", "crossing", "crossing_ref", "junction", "name"]
    ox.settings.useful_tags_way = [
        "highway", "name", "name:ro", "alt_name", "old_name", "official_name",
        "junction", "ref", "lanes", "bridge", "tunnel",
    ]
    return ox


def _valoare(rand: Any, coloana: str) -> Any:
    try:
        v = rand[coloana]
    except (KeyError, IndexError):
        return None
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _nume_din(rand: Any) -> list[str]:
    nume: list[str] = []
    for eticheta in ETICHETE_NUME:
        v = _valoare(rand, eticheta)
        if not v:
            continue
        for bucata in str(v).split(";"):
            bucata = bucata.strip()
            if bucata and bucata not in nume:
                nume.append(bucata)
    return nume


def _ref_osm(index_rand: Any) -> str:
    # osmnx 2.x: MultiIndex (element, id)
    if isinstance(index_rand, tuple) and len(index_rand) == 2:
        return f"{index_rand[0]}/{index_rand[1]}"
    return str(index_rand)


def _punct_reprezentativ(geom) -> tuple[float, float] | None:
    if geom is None or geom.is_empty:
        return None
    p = geom if geom.geom_type == "Point" else geom.representative_point()
    return (round(p.y, 7), round(p.x, 7))


# ------------------------------------------------------------------ străzi


def _strazi(ox) -> tuple[dict, dict, dict]:
    """Străzile pe componente conexe + coordonatele nodurilor + treceri pe străzi."""
    _jurnal("descarc rețeaua de străzi cu nume (osmnx.graph_from_bbox)...")
    G = _cu_reincercari(
        lambda: ox.graph_from_bbox(
            bbox=config.BBOX_DATE.pentru_osmnx(),
            simplify=False,
            retain_all=True,
            truncate_by_edge=True,
            custom_filter=FILTRU_STRAZI,
        ),
        "rețeaua de străzi",
    )
    _jurnal(f"  {G.number_of_nodes()} noduri, {G.number_of_edges()} muchii")

    noduri = {n: (round(d["y"], 7), round(d["x"], 7)) for n, d in G.nodes(data=True)}

    # nume -> segmente neorientate (+ way id și tip pe segment) + variante de nume
    pe_nume: dict[str, dict] = defaultdict(
        lambda: {"variante": set(), "principale": Counter(), "segmente": set(), "info": {}}
    )
    for u, v, d in G.edges(data=True):
        nume_principal = d.get("name")
        if isinstance(nume_principal, list):
            nume_principal = nume_principal[0]
        if not nume_principal:
            continue
        toate = [nume_principal]
        for eticheta in ("name:ro", "alt_name", "old_name", "official_name"):
            v_alt = d.get(eticheta)
            if isinstance(v_alt, list):
                toate.extend(v_alt)
            elif v_alt:
                toate.extend(s.strip() for s in str(v_alt).split(";"))
        cheie = cheie_nume(nume_principal)
        intrare = pe_nume[cheie]
        intrare["variante"].update(x for x in toate if x)
        intrare["principale"][nume_principal] += 1
        segment = (min(u, v), max(u, v))
        intrare["segmente"].add(segment)
        osmid = d.get("osmid")
        hw = d.get("highway")
        intrare["info"][segment] = (
            [int(w) for w in (osmid if isinstance(osmid, list) else [osmid]) if w is not None],
            [h for h in (hw if isinstance(hw, list) else [hw]) if h],
        )

    strazi: dict[str, list[dict]] = {}
    for cheie, date in pe_nume.items():
        strazi[cheie] = _componente(cheie, date, noduri)

    noduri_folosite = {n for comps in strazi.values() for c in comps for s in c["segmente"] for n in s}
    noduri_out = {str(n): list(noduri[n]) for n in noduri_folosite}

    treceri_pe_strazi: dict[int, set[str]] = defaultdict(set)
    nod_la_strazi: dict[int, set[str]] = defaultdict(set)
    for cheie, comps in strazi.items():
        for i, c in enumerate(comps):
            for s in c["segmente"]:
                for n in s:
                    nod_la_strazi[n].add(f"{cheie}#{i}")
    for n, d in G.nodes(data=True):
        if d.get("highway") == "crossing" or d.get("crossing"):
            treceri_pe_strazi[n] = nod_la_strazi.get(n, set())

    return strazi, noduri_out, {"treceri": treceri_pe_strazi, "G": G}


def _componente(cheie: str, date: dict, noduri: dict) -> list[dict]:
    """Împarte o stradă în bucăți conexe; unește bucățile foarte apropiate."""
    parinte: dict[int, int] = {}

    def gaseste(x: int) -> int:
        while parinte.setdefault(x, x) != x:
            parinte[x] = parinte[parinte[x]]
            x = parinte[x]
        return x

    def uneste(a: int, b: int) -> None:
        ra, rb = gaseste(a), gaseste(b)
        if ra != rb:
            parinte[ra] = rb

    for u, v in date["segmente"]:
        uneste(u, v)

    grupuri: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for u, v in date["segmente"]:
        grupuri[gaseste(u)].append((u, v))
    bucati = list(grupuri.values())

    # unește bucățile despărțite de o piață / un sens giratoriu / o lipsă în OSM
    schimbat = True
    while schimbat and len(bucati) > 1:
        schimbat = False
        for i in range(len(bucati)):
            for j in range(i + 1, len(bucati)):
                if _aproape(bucati[i], bucati[j], noduri, config.RAZA_UNIRE_COMPONENTE):
                    bucati[i].extend(bucati[j])
                    del bucati[j]
                    schimbat = True
                    break
            if schimbat:
                break

    # numele afișat = tag-ul `name` cel mai frecvent (nu un old_name / alt_name)
    nume_afisat = date["principale"].most_common(1)[0][0] if date["principale"] else cheie
    rezultat = []
    for segmente in bucati:
        puncte = [noduri[n] for s in segmente for n in s]
        lats = [p[0] for p in puncte]
        lons = [p[1] for p in puncte]
        way_ids = sorted({w for s in segmente for w in date["info"][s][0]})
        highway = sorted({h for s in segmente for h in date["info"][s][1]})
        rezultat.append(
            {
                "nume": nume_afisat,
                "variante": sorted(date["variante"]),
                "highway": highway,
                "way_ids": way_ids,
                "segmente": [list(s) for s in segmente],
                "bbox": [min(lats), min(lons), max(lats), max(lons)],
                "punct": list(_punct_strada(segmente, noduri)),
            }
        )
    return rezultat


def _aproape(a, b, noduri, raza: float) -> bool:
    na = {n for s in a for n in s}
    nb = {n for s in b for n in s}
    if len(na) * len(nb) > 250_000:
        na = set(list(na)[::5])
        nb = set(list(nb)[::5])
    for x in na:
        px = noduri[x]
        for y in nb:
            if distanta_m(px, noduri[y]) <= raza:
                return True
    return False


def _punct_strada(segmente, noduri) -> tuple[float, float]:
    """Nodul străzii cel mai apropiat de centrul ponderat cu lungimea."""
    total = sx = sy = 0.0
    for u, v in segmente:
        a, b = noduri[u], noduri[v]
        lung = distanta_m(a, b) or 0.01
        total += lung
        sx += lung * (a[0] + b[0]) / 2
        sy += lung * (a[1] + b[1]) / 2
    centru = (sx / total, sy / total)
    cel_mai_bun = min(
        {n for s in segmente for n in s}, key=lambda n: distanta_m(noduri[n], centru)
    )
    return noduri[cel_mai_bun]


# ------------------------------------------------------------------ restul


def _cu_reincercari(apel, descriere: str, incercari: int = 6, pauza_sec: float = 30.0):
    """Overpass public refuză uneori cereri când e plin (502/504/429).

    Reîncercăm cu pauză dublată de fiecare dată. Răspunsurile reușite rămân în
    cache-ul osmnx, deci o reluare nu mai descarcă ce avem deja.
    """
    for incercare in range(1, incercari + 1):
        try:
            return apel()
        except Exception as e:
            nume = type(e).__name__
            if nume == "InsufficientResponseError":
                raise
            temporar = nume in ("ResponseStatusCodeError", "ConnectionError", "ReadTimeout",
                                "ConnectTimeout", "ChunkedEncodingError", "JSONDecodeError")
            if not temporar or incercare == incercari:
                raise
            _jurnal(f"  {descriere}: {nume} ({str(e).splitlines()[0][:90]}); "
                    f"reîncerc în {pauza_sec:.0f} s ({incercare}/{incercari - 1})")
            time.sleep(pauza_sec)
            pauza_sec *= 2


def _features(ox, etichete: dict, descriere: str):
    _jurnal(f"descarc {descriere} (osmnx.features_from_bbox)...")
    try:
        gdf = _cu_reincercari(
            lambda: ox.features_from_bbox(bbox=config.BBOX_DATE.pentru_osmnx(), tags=etichete),
            descriere,
        )
    except Exception as e:  # InsufficientResponseError = niciun rezultat
        if type(e).__name__ == "InsufficientResponseError":
            _jurnal("  niciun rezultat")
            return None
        raise
    _jurnal(f"  {len(gdf)} obiecte")
    return gdf


def _treceri(ox, pe_strazi: dict[int, set[str]], noduri_graf) -> list[dict]:
    gdf = _features(ox, {"highway": "crossing"}, "trecerile de pietoni")
    treceri: dict[str, dict] = {}
    if gdf is not None:
        for idx, rand in gdf.iterrows():
            punct = _punct_reprezentativ(rand.geometry)
            if not punct:
                continue
            ref = _ref_osm(idx)
            treceri[ref] = {
                "osm": ref,
                "lat": punct[0],
                "lon": punct[1],
                "crossing": _valoare(rand, "crossing"),
                "strazi": [],
            }
    for nod, strazi in pe_strazi.items():
        ref = f"node/{nod}"
        d = noduri_graf.nodes[nod]
        intrare = treceri.setdefault(
            ref,
            {"osm": ref, "lat": round(d["y"], 7), "lon": round(d["x"], 7),
             "crossing": d.get("crossing"), "strazi": []},
        )
        intrare["strazi"] = sorted(strazi)
    return list(treceri.values())


def _poi(ox) -> list[dict]:
    gdf = _features(ox, ETICHETE_POI, "reperele (POI)")
    if gdf is None:
        return []
    rezultat = []
    for idx, rand in gdf.iterrows():
        nume = _nume_din(rand)
        if not nume:
            continue
        punct = _punct_reprezentativ(rand.geometry)
        if not punct:
            continue
        clasa = next((c for c in CLASE_POI if _valoare(rand, c)), None)
        rezultat.append(
            {
                "osm": _ref_osm(idx),
                "nume": nume[0],
                "variante": nume,
                "clasa": clasa,
                "tip": str(_valoare(rand, clasa)) if clasa else None,
                "lat": punct[0],
                "lon": punct[1],
            }
        )
    return rezultat


def _locuri(ox) -> list[dict]:
    gdf = _features(ox, {"place": TIPURI_LOC}, "cartierele și localitățile")
    if gdf is None:
        return []
    rezultat = []
    for idx, rand in gdf.iterrows():
        nume = _nume_din(rand)
        punct = _punct_reprezentativ(rand.geometry)
        if not nume or not punct:
            continue
        rezultat.append(
            {
                "osm": _ref_osm(idx),
                "nume": nume[0],
                "variante": nume,
                "tip": _valoare(rand, "place"),
                "lat": punct[0],
                "lon": punct[1],
            }
        )
    return rezultat


def _adrese(ox) -> dict[str, dict[str, list]]:
    gdf = _features(ox, {"addr:housenumber": True}, "adresele cu număr")
    if gdf is None:
        return {}
    rezultat: dict[str, dict[str, list]] = defaultdict(dict)
    for idx, rand in gdf.iterrows():
        strada = _valoare(rand, "addr:street")
        numar = _valoare(rand, "addr:housenumber")
        punct = _punct_reprezentativ(rand.geometry)
        if not strada or not numar or not punct:
            continue
        for n in str(numar).replace(",", ";").split(";"):
            n = n.strip().upper()
            if n:
                rezultat[cheie_nume(str(strada))].setdefault(n, [punct[0], punct[1], _ref_osm(idx)])
    return dict(rezultat)


def _unitati_admin(ox) -> dict:
    gdf = _features(ox, {"admin_level": "8"}, "granițele administrative (admin_level=8)")
    features = []
    if gdf is not None:
        for idx, rand in gdf.iterrows():
            geom = rand.geometry
            if geom is None or geom.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            if _valoare(rand, "boundary") != "administrative":
                continue
            nume = _nume_din(rand)
            features.append(
                {
                    "type": "Feature",
                    "geometry": json.loads(
                        __import__("shapely").to_geojson(geom.simplify(0.00005, preserve_topology=True))
                    ),
                    "properties": {
                        "osm": _ref_osm(idx),
                        "nume": nume[0] if nume else None,
                        "admin_level": "8",
                    },
                }
            )
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "sursa": "OpenStreetMap contributors, ODbL 1.0 (osmnx / Overpass)",
            "descarcat_la": time.strftime("%Y-%m-%d"),
        },
    }


def _atribuie_unitati(strazi: dict, unitati: dict) -> None:
    """Pentru fiecare bucată de stradă: în ce unitate administrativă e."""
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree

    geometrii = [shape(f["geometry"]) for f in unitati["features"]]
    nume = [f["properties"]["nume"] for f in unitati["features"]]
    if not geometrii:
        return
    arbore = STRtree(geometrii)
    for comps in strazi.values():
        for c in comps:
            p = Point(c["punct"][1], c["punct"][0])
            c["unitate"] = next(
                (nume[i] for i in arbore.query(p) if geometrii[i].contains(p)), None
            )


def ruleaza(fortat: bool = False) -> dict:
    if config.FISIER_INDEX.exists() and not fortat:
        _jurnal(f"indexul există deja: {config.FISIER_INDEX} (folosește --forteaza)")
        return {"index": str(config.FISIER_INDEX), "sarit": True}

    ox = _configureaza_osmnx()
    inceput = time.time()

    unitati = _unitati_admin(ox)
    strazi, noduri, extra = _strazi(ox)
    treceri = _treceri(ox, extra["treceri"], extra["G"])
    poi = _poi(ox)
    locuri = _locuri(ox)
    adrese = _adrese(ox)
    _atribuie_unitati(strazi, unitati)

    index = {
        "meta": {
            "versiune_index": 1,
            "descarcat_la": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "bbox": {
                "sud": config.BBOX_DATE.sud, "vest": config.BBOX_DATE.vest,
                "nord": config.BBOX_DATE.nord, "est": config.BBOX_DATE.est,
            },
            "osmnx": ox.__version__,
            "overpass": config.OVERPASS_URL,
            "filtru_strazi": FILTRU_STRAZI,
            "sursa": "OpenStreetMap contributors, ODbL 1.0",
            "numere": {
                "nume_strazi": len(strazi),
                "componente_strazi": sum(len(c) for c in strazi.values()),
                "noduri": len(noduri),
                "treceri": len(treceri),
                "poi": len(poi),
                "locuri": len(locuri),
                "strazi_cu_adrese": len(adrese),
                "unitati_admin": len(unitati["features"]),
            },
        },
        "noduri": noduri,
        "strazi": strazi,
        "treceri": treceri,
        "poi": poi,
        "locuri": locuri,
        "adrese": adrese,
    }

    config.DIR_OSM.mkdir(parents=True, exist_ok=True)
    _scrie_gz(config.FISIER_INDEX, index)
    with config.FISIER_UNITATI.open("w", encoding="utf-8") as f:
        json.dump(unitati, f, ensure_ascii=False)
    _jurnal(
        f"gata în {time.time() - inceput:.0f} s: {config.FISIER_INDEX} "
        f"({config.FISIER_INDEX.stat().st_size / 1e6:.1f} MB), "
        f"{config.FISIER_UNITATI} ({config.FISIER_UNITATI.stat().st_size / 1e6:.1f} MB)"
    )
    _jurnal(json.dumps(index["meta"]["numere"], ensure_ascii=False))
    return {"index": str(config.FISIER_INDEX), "numere": index["meta"]["numere"]}


def _scrie_gz(cale: Path, date: Any) -> None:
    temp = cale.with_suffix(cale.suffix + ".tmp")
    with gzip.open(temp, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(date, f, ensure_ascii=False, separators=(",", ":"))
    temp.replace(cale)
