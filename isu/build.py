"""Parsed ISU releases -> deduplicated events -> geocoded contract files in isu/out/.

Two sources only, never summed:
- ISU Iași releases: individual events (accidents.json, articles.json).
- PMUD Iași 2022, Table 2.11 (IPJ counts per artery, 2020 and 2021): street totals in streets.geojson.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config
from .collect import collect
from .parse import parse
from .presa import AI_REPLAY, RULES, from_articles, from_contract, from_gemini

SCHEMA = "2.0"
PRECISE = {"trecere", "intersectie", "segment"}


# ------------------------------------------------------------------ night (sun below the horizon)

def _utc_offset(day: date) -> int:
    """Romania: UTC+3 from the last Sunday of March to the last Sunday of October, else UTC+2."""
    def last_sunday(month: int) -> date:
        d = date(day.year, month, 31)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    return 3 if last_sunday(3) <= day < last_sunday(10) else 2


def _sun_hours(day: date, lat: float = 47.16, lon: float = 27.59) -> tuple[float, float]:
    """Sunrise and sunset in local decimal hours (NOAA approximation, ±2 min)."""
    n = day.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                   - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(math.radians(lat)) * math.cos(decl))
                                - math.tan(math.radians(lat)) * math.tan(decl)))
    noon = 720 - 4 * lon - eq
    offset = _utc_offset(day) * 60
    return (noon - 4 * ha + offset) / 60, (noon + 4 * ha + offset) / 60


def is_night(day: str | None, hour: str | None) -> bool | None:
    if not day or not hour:
        return None
    h, m = map(int, hour.split(":"))
    rise, sett = _sun_hours(date.fromisoformat(day))
    t = h + m / 60
    return t < rise or t >= sett


# ------------------------------------------------------------------ dedup

def _minutes(hour: str | None) -> int | None:
    if not hour:
        return None
    h, m = map(int, hour.split(":"))
    return h * 60 + m


def _place_key(ev: dict) -> str:
    return (ev["strada"] or ev["drum"] or ev["localitate"] or "").lower()


def same_event(a: dict, b: dict) -> bool:
    """Two releases describe one crash: same day, same place, times within 90 min (or one unknown)."""
    if not a["data_eveniment"] or a["data_eveniment"] != b["data_eveniment"]:
        return False
    ka, kb = _place_key(a), _place_key(b)
    if not ka or not kb or not (ka in kb or kb in ka):
        return False
    ma, mb = _minutes(a["ora"]), _minutes(b["ora"])
    return ma is None or mb is None or abs(ma - mb) <= 90


# ------------------------------------------------------------------ street geometry (PMUD layer)

def _lines(index, components) -> list[list[list[float]]]:
    """Chains a street's OSM segments into polylines ([lon, lat] for GeoJSON)."""
    adjacency = defaultdict(list)
    for comp in components:
        for u, v in comp.segmente:
            adjacency[u].append(v)
            adjacency[v].append(u)
    seen = set()
    lines = []
    for start in sorted(adjacency, key=lambda n: len(adjacency[n]) != 1):
        for nxt in adjacency[start]:
            if (start, nxt) in seen:
                continue
            path = [start]
            prev, cur = start, nxt
            seen.update({(prev, cur), (cur, prev)})
            path.append(cur)
            while len(adjacency[cur]) == 2:
                cand = adjacency[cur][0] if adjacency[cur][1] == prev else adjacency[cur][1]
                if (cur, cand) in seen:
                    break
                seen.update({(cur, cand), (cand, cur)})
                prev, cur = cur, cand
                path.append(cur)
            lines.append([[round(index.noduri[n][1], 6), round(index.noduri[n][0], 6)] for n in path if n in index.noduri])
    return [l for l in lines if len(l) >= 2]


def _street_components(index, osm_name: str):
    comps, level = index.strazi_dupa_nume(osm_name)
    return [c for c in comps if c.unitate == "Iași" and c.nume == osm_name] if level else []


def _osm_street(index, geo, strada: str | None, in_iasi: bool | None) -> str | None:
    """The OSM street an event lies on, even when the geocoder gives no point."""
    name = next((c["nume"] for c in geo.candidati if c.get("fel") == "strada"), None) \
        if geo.precizie_loc != "vag" else None
    if not name and strada and in_iasi:
        # The geocoder places no point when a name has several disconnected OSM pieces (Șoseaua
        # Nicolina); the street itself is still certain, so the event counts on the street layer.
        comps, level = index.strazi_dupa_nume(strada)
        names = {c.nume for c in comps if c.unitate == "Iași"}
        if level >= 2 and len(names) == 1:
            name = names.pop()
    return name


def _days(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def press_events(resolver, index, today: datetime, presa_path: Path | None,
                 presa_csvs: list[Path]) -> tuple[list, list, dict]:
    """Press reports as events with sursa_tip "presa"; never merged with ISU events."""
    if presa_path:
        events = from_contract(presa_path)
        for a in events:
            a.setdefault("sursa", "presă")
            a["sursa_tip"] = "presa"
            a["extractie"] = "pipeline echipă"
            a.setdefault("strada_osm", None)
        return events, [], {"extractie": "pipeline echipă", "fisier": str(presa_path)}

    ai_rows, judged, ai_info = from_gemini(presa_csvs)
    # The rules only read what Gemini has not judged, and keep its scope: pedestrians hit.
    rule_rows = [e for e in from_articles(presa_csvs) if e["url"] not in judged and "pieton" in e["participanti"]]
    raw = sorted(ai_rows + rule_rows, key=lambda e: e["publicat_la"] or "")
    groups: list[list[dict]] = []
    for ev in raw:
        for g in groups:
            o = g[0]
            near = _days(ev["publicat_la"], o["publicat_la"])
            if ev["strada"] and o["strada"] and ev["strada"].lower() == o["strada"].lower() \
                    and near is not None and abs(near) <= 1:
                g.append(ev)
                break
        else:
            groups.append([ev])
    articles, events = [], []
    rank = {"deces": 3, "grav": 2, "usor": 1, "necunoscut": 0}
    for g in groups:
        for ev in g:
            articles.append({k: ev[k] for k in ("article_id", "sursa", "url", "titlu", "text", "publicat_la")}
                            | {"colectat_la": today.date().isoformat()})
        main = max(g, key=lambda e: (e["loc_text"] is not None, len(e["dovezi"])))
        geo = resolver.rezolva(main.get("geo_text") or main["loc_text"])
        in_iasi = geo.in_iasi
        if in_iasi is None and main["municipiu"] and main["loc_text"]:
            in_iasi = True
        published = [e["publicat_la"] for e in g if e["publicat_la"]]
        events.append({
            # Stable across runs: new articles must not renumber the events a viewer has open.
            "event_id": "ev-presa-" + hashlib.sha1(g[0]["article_id"].encode()).hexdigest()[:10],
            "article_ids": [e["article_id"] for e in g],
            "urls": [e["url"] for e in g],
            "data_eveniment": main["data_eveniment"],
            "ora": main["ora"],
            "loc_text": main["loc_text"] or "loc nemenționat în articol",
            "precizie_loc": geo.precizie_loc,
            "lat": geo.lat,
            "lon": geo.lon,
            "in_iasi": in_iasi,
            "participanti": sorted({p for e in g for p in e["participanti"]}),
            "cauza_raportata": next((e["cauza_raportata"] for e in g if e["cauza_raportata"]), None),
            "gravitate": max((e["gravitate"] for e in g), key=rank.get),
            # Gemini reports night only from the article's words; the rules derive it from the hour.
            "noapte": main["noapte"] if main.get("noapte") is not None else is_night(main["data_eveniment"], main["ora"]),
            "dovezi": main["dovezi"],
            "verificat": False,
            "review_status": "pending",
            "sursa": " + ".join(sorted({e["sursa"] for e in g})),
            "sursa_tip": "presa",
            "extractie": main.get("extractie", RULES),
            "publicat_la": min(published) if published else None,
            "strada_osm": _osm_street(index, geo, main["strada"], in_iasi),
        })
    methods = sorted({e["extractie"] for e in events})
    return events, articles, {"extractie": " + ".join(methods) if methods else AI_REPLAY,
                              "articole_citite": len(judged) + len(rule_rows), "ai": ai_info,
                              "reguli_evenimente": sum(e["extractie"] == RULES for e in events),
                              "fisiere": [str(p.relative_to(config.REPO)) if p.is_relative_to(config.REPO) else str(p)
                                          for p in presa_csvs if p.exists()]}


def link_sources(isu: list[dict], press: list[dict]) -> None:
    """Marks a press report and an ISU event as possibly the same crash: same street, and the ISU event
    happened at most 3 days before the article (or on the article's event date). Shown, never merged."""
    for p in press:
        if not p["strada_osm"]:
            continue
        ref = p["data_eveniment"] or p.get("publicat_la")
        for a in isu:
            if a["strada_osm"] != p["strada_osm"]:
                continue
            gap = _days(ref, a["data_eveniment"])
            if gap is not None and 0 <= gap <= (0 if p["data_eveniment"] else 3):
                p.setdefault("posibil_acelasi_cu", []).append(a["event_id"])
                a.setdefault("posibil_acelasi_cu", []).append(p["event_id"])


def _ro(n: int, one: str, many: str) -> str:
    """Romanian count agreement: 1 eveniment, 2 evenimente, 20 de evenimente."""
    return f"{n} {one}" if n == 1 else f"{n} {many}" if n % 100 < 20 else f"{n} de {many}"


def attention(features: list[dict]) -> None:
    """Streets to look at first, by a fixed rule (README): one signal per independent fact,
    order = number of signals, then ISU count, then PMUD 2021. A reading order for a field check, not a risk score."""
    def top(key, n=5):
        ranked = sorted((f for f in features if f["properties"][key]), key=lambda f: -f["properties"][key])
        return {f["properties"]["id"]: (i + 1, len(ranked)) for i, f in enumerate(ranked[:n])}
    isu_top, pmud_top = top("isu_evenimente"), top("pmud_2021")
    for f in features:
        p = f["properties"]
        signals, checks = [], []
        if p["id"] in isu_top:
            r, n = isu_top[p["id"]]
            signals.append({"tip": "isu", "text": f"{_ro(p['isu_evenimente'], 'intervenție', 'intervenții')} ISU în oct. 2024 – oct. 2026, locul {r} din {n} străzi"})
        if p["id"] in pmud_top:
            r, n = pmud_top[p["id"]]
            signals.append({"tip": "pmud", "text": f"{_ro(p['pmud_2021'], 'accident', 'accidente')} IPJ în 2021 (PMUD), locul {r} din {n} artere din tabel"})
        deaths, serious = p["isu_deces"] + p["presa_deces"], p["isu_grav"] + p["presa_grav"]
        if deaths or serious:
            parts = [f"{_ro(v, 'eveniment', 'evenimente')} {t}" for v, t in ((deaths, "cu decese"), (serious, "cu răniți grav")) if v]
            signals.append({"tip": "gravitate", "text": " și ".join(parts) + " (ISU și presă, pot fi aceleași)"})
        if p["presa_evenimente"] >= 2:
            signals.append({"tip": "presa", "text": f"{_ro(p['presa_evenimente'], 'relatare', 'relatări')} distincte în presă în 2026"})
        walkers = p["isu_pietoni"] + p["presa_pietoni"]
        if walkers >= 2:  # one event alone would count twice with the severity signal
            signals.append({"tip": "pietoni", "text": f"{_ro(walkers, 'eveniment', 'evenimente')} cu pietoni (ISU și presă, pot fi aceleași)"})
        night = p["isu_noapte"] + p["presa_noapte"]
        # Planificare §7 rules, read at street level (the exact crossing is unknown).
        if night >= 2:
            checks.append(f"{_ro(night, 'eveniment', 'evenimente')} noaptea: iluminatul existent, poziția stâlpilor, vizibilitatea la treceri")
        if p["presa_neacordare"] >= 2:
            checks.append("Neacordare de prioritate relatată repetat: vizibilitatea și organizarea intersecțiilor")
        checks.append("Observație în teren: comunicatele și articolele numesc strada, nu trecerea sau intersecția")
        p["semnale"], p["de_verificat"] = signals, checks
    order = sorted((f for f in features if len(f["properties"]["semnale"]) >= 2),
                   key=lambda f: (-len(f["properties"]["semnale"]), -f["properties"]["isu_evenimente"],
                                  -(f["properties"]["pmud_2021"] or 0)))
    for f in features:
        f["properties"]["prioritate"] = None
    for i, f in enumerate(order[:10], 1):
        f["properties"]["prioritate"] = i


# ------------------------------------------------------------------ main

_RESOLVER = None


def _resolver():
    # Loading the OSM street index takes a few seconds; the scheduler reuses it between runs.
    global _RESOLVER
    if _RESOLVER is None:
        from coordonate.cli import _incarca_rezolvator
        _RESOLVER = _incarca_rezolvator()
    return _RESOLVER


def build(db, presa_csvs: list[Path], presa_path: Path | None = None) -> tuple[dict, dict, dict]:
    """Collects new ISU releases into `db` and builds the dataset from everything stored.
    Returns (dataset served to the map, extras kept in the database, what this run fetched)."""
    from coordonate.normalizare import cheie_baza

    releases, fetched = collect(db)
    parsed = []
    skipped = 0
    for rel in releases:
        if not rel["text"]:
            continue
        ev = parse(rel["titlu"], rel["text"])
        if ev is None:
            skipped += 1
            continue
        ev["release"] = rel
        parsed.append(ev)
    parsed.sort(key=lambda e: (e["publicat_la"] or "", int(e["nr_comunicat"] or 0)))

    groups: list[list[dict]] = []
    for ev in parsed:
        for g in groups:
            if any(same_event(ev, other) for other in g):
                g.append(ev)
                break
        else:
            groups.append([ev])

    resolver = _resolver()
    index = resolver.index
    today = datetime.now(timezone(timedelta(hours=_utc_offset(date.today())))).replace(microsecond=0)
    articles, accidents, report = [], [], []
    for g in groups:
        ids = []
        for ev in g:
            rel = ev["release"]
            year = (ev["publicat_la"] or "0000")[:4]
            aid = f"isu-{year}-{ev['nr_comunicat']}" if ev["nr_comunicat"] else f"isu-{rel['fisier'][:8]}"
            ids.append(aid)
            articles.append({
                "article_id": aid, "sursa": config.SOURCE, "url": rel["url"], "titlu": rel["titlu"],
                "text": ev["text"], "publicat_la": ev["publicat_la"], "colectat_la": today.date().isoformat(),
            })
        main = max(g, key=lambda e: (e["strada"] is not None, e["ora"] is not None, len(e["dovezi"])))
        rank = {"deces": 3, "grav": 2, "usor": 1, "necunoscut": 0}
        gravity = max((e["gravitate"] for e in g), key=rank.get)
        geo = resolver.rezolva(main["loc_text"])
        in_iasi = geo.in_iasi
        if in_iasi is None and main["municipiu"]:
            in_iasi = True  # the release says "municipiul Iași" although the street is not in the OSM index
        osm_street = _osm_street(index, geo, main["strada"], in_iasi)
        accidents.append({
            "event_id": ids[0].replace("isu-", "ev-isu-", 1),
            "article_ids": ids,
            "urls": [e["release"]["url"] for e in g],
            "data_eveniment": main["data_eveniment"],
            "ora": main["ora"],
            "loc_text": main["loc_text"] or "loc nemenționat în comunicat",
            "precizie_loc": geo.precizie_loc,
            "lat": geo.lat,
            "lon": geo.lon,
            "in_iasi": in_iasi,
            "participanti": sorted({p for e in g for p in e["participanti"]}),
            "cauza_raportata": None,  # ISU does not state causes; the police investigation does
            "gravitate": gravity,
            "noapte": is_night(main["data_eveniment"], main["ora"]),
            "dovezi": main["dovezi"],
            "verificat": False,
            "sursa": config.SOURCE,
            "sursa_tip": "isu",
            "strada_osm": osm_street,
        })
        report.append({"event_id": accidents[-1]["event_id"], "metoda": geo.metoda,
                       "de_verificat": geo.de_verificat, "referinte_osm": geo.referinte_osm})

    isu_events = list(accidents)
    press, press_articles, press_info = press_events(resolver, index, today, presa_path, presa_csvs)
    link_sources(isu_events, press)
    accidents += press
    articles += press_articles

    city = [a for a in accidents if a["in_iasi"]]
    precise = [a for a in city if a["precizie_loc"] in PRECISE and a["lat"] is not None]

    # Hotspots: Planificare §5 on precisely located city events only; context points are unknown here.
    by_place = defaultdict(list)
    for a in precise:
        by_place[(round(a["lat"], 4), round(a["lon"], 4))].append(a)
    hotspots = []
    for (lat, lon), evs in by_place.items():
        if len(evs) < 2:
            continue
        deces = sum(a["gravitate"] == "deces" for a in evs)
        grav = sum(a["gravitate"] == "grav" for a in evs)
        hours = [0] * 24
        for a in evs:
            if a["ora"]:
                hours[int(a["ora"][:2])] += 1
        hotspots.append({
            "id": f"loc-isu-{len(hotspots) + 1:02d}", "crossing_id": None, "nume": evs[0]["loc_text"],
            "lat": lat, "lon": lon, "h3": None, "scor": len(evs) + 4 * deces + 2 * grav,
            "componente_scor": {"evenimente": len(evs), "deces": 4 * deces, "grav": 2 * grav, "context": 0},
            "event_ids": [a["event_id"] for a in evs], "nr_evenimente": len(evs), "pe_ore": hours,
            "explicatie": f"{len(evs)} evenimente la același loc" + (f", {deces} cu decese" if deces else ""),
            "date_lipsa": ["semafor", "benzi", "iluminat", "scoala_150m", "statie_100m"],
            "masuri": [], "verificat": False,
        })

    # Street layer: events per street and per source (by base name, any prefix) next to the PMUD counts.
    pmud = []
    with open(config.PMUD_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pmud.append(row)
    # PMUD writes "Str." for every artery, so ISU events join a PMUD street by base name ("Bucium");
    # other streets are keyed by their full OSM name (Aleea ≠ Șoseaua Tudor Neculai).
    streets: dict[str, dict] = {}
    for row in pmud:
        key = cheie_baza(row["strada_osm"])
        streets[key] = {"nume": row["strada_osm"], "pmud": row, "events": []}
    for a in city:
        if not a["strada_osm"]:
            continue
        key = cheie_baza(a["strada_osm"])
        if key not in streets or streets[key]["pmud"] is None:
            key = a["strada_osm"].lower()
        streets.setdefault(key, {"nume": a["strada_osm"], "pmud": None, "events": []})["events"].append(a)
    features = []
    for key, s in sorted(streets.items()):
        names = {s["nume"]} | {a["strada_osm"] for a in s["events"]}
        comps = [c for n in sorted(names) for c in _street_components(index, n)]
        lines = _lines(index, comps)
        if not lines:
            continue
        evs = sorted(s["events"], key=lambda a: a["data_eveniment"] or "")
        counts = {}
        for t in ("isu", "presa"):
            lst = [a for a in evs if a["sursa_tip"] == t]
            counts |= {
                f"{t}_evenimente": len(lst),
                f"{t}_deces": sum(a["gravitate"] == "deces" for a in lst),
                f"{t}_grav": sum(a["gravitate"] == "grav" for a in lst),
                f"{t}_noapte": sum(a["noapte"] is True for a in lst),
                f"{t}_pietoni": sum("pieton" in a["participanti"] for a in lst),
                f"{t}_event_ids": [a["event_id"] for a in lst],
            }
        counts["presa_neacordare"] = sum(a["cauza_raportata"] == "neacordare_prioritate"
                                         for a in evs if a["sursa_tip"] == "presa")
        p = s["pmud"]
        features.append({
            "type": "Feature",
            "geometry": {"type": "MultiLineString", "coordinates": lines},
            "properties": {
                "id": "str-" + key.replace(" ", "-"),
                "nume": s["nume"],
                "nume_osm": sorted(names),
                **counts,
                "pmud_strada": p["strada_pmud"] if p else None,
                "pmud_2020": int(p["accidente_2020"]) if p else None,
                "pmud_2021": int(p["accidente_2021"]) if p else None,
                "pmud_nota": p["nota_mapare"] or None if p else None,
            },
        })

    attention(features)

    dates = sorted(a["data_eveniment"] for a in accidents if a["data_eveniment"])
    manifest = {
        "schema_version": SCHEMA,
        "data_mode": "observed",
        "perioada": [dates[0], dates[-1]] if dates else [None, None],
        "generat_la": today.isoformat(),
        "nr_articole": len(articles),
        "nr_evenimente": len(accidents),
        "nr_localizate_precis": len(precise),
        "nr_verificate": 0,
        "avertisment": (
            "Date reale din comunicatele ISU Iași (intervenții ale pompierilor la accidente rutiere), extrase automat "
            "cu reguli fixe, neverificate manual. Nu sunt toate accidentele: poliția înregistrează cam 650 pe an în "
            "municipiu, ISU comunică doar intervențiile sale. Stratul pe străzi arată separat totalurile IPJ din "
            "PMUD Iași 2022 (2020–2021). Relatările din presă (BZI, Ziarul de Iași) sunt o sursă separată: "
            "pietoni loviți, selectați și extrași de Gemini (răspunsuri salvate, reluare), neverificați manual; "
            "articolele noi, fără răspuns Gemini, trec prin reguli provizorii și sunt marcate așa. "
            "Sursele nu se adună și pot descrie același accident."
        ),
        "surse": [
            {"id": "isu", "nume": config.SOURCE, "url": f"{config.BASE}/comunicate-de-presa",
             "listari": config.LISTINGS},
            {"id": "pmud", "nume": "PMUD Iași 2022, Tabel 2.11 (date IPJ Iași)",
             "url": "https://zmi.ro/wp-content/uploads/2026/06/PMUD-Iasi-Reactualizare-2022.pdf", "pagina": 73},
            {"id": "presa", "nume": "Presa locală (BZI, Ziarul de Iași)", "url": "https://www.bzi.ro/",
             "extractie": press_info["extractie"], "ai": press_info.get("ai")},
        ],
        "statistici": {
            "comunicate_descarcate": len(releases), "comunicate_respinse_nerutier": skipped,
            "evenimente_judet": len(isu_events),
            "evenimente_municipiu": sum(1 for a in city if a["sursa_tip"] == "isu"),
            "municipiu_pe_strada": sum(a["precizie_loc"] == "strada" for a in city if a["sursa_tip"] == "isu"),
            "municipiu_fara_loc": sum(a["precizie_loc"] == "vag" for a in city if a["sursa_tip"] == "isu"),
            "presa_articole": press_info.get("articole_citite", 0),
            "presa_evenimente": len(press),
            "presa_ai_neclare": (press_info.get("ai") or {}).get("neclare", 0),
            "presa_reguli": press_info.get("reguli_evenimente", 0),
            "presa_municipiu": sum(1 for a in city if a["sursa_tip"] == "presa"),
            "surse_posibil_acelasi": sum(1 for a in press if a.get("posibil_acelasi_cu")),
            "fara_data": sum(a["data_eveniment"] is None for a in accidents),
            "fara_ora": sum(a["ora"] is None for a in accidents),
        },
    }

    dataset = {
        "manifest": manifest,
        "accidents": accidents,
        "hotspots": hotspots,
        "crossings": {"type": "FeatureCollection", "features": []},
        "measures": [],
        "streets": {"type": "FeatureCollection", "features": features},
    }
    return dataset, {"articles": articles, "raport_geocodare": report}, fetched


def export(dataset: dict, extras: dict, out: Path) -> None:
    """Writes the contract files (manifest.json, accidents.json, …) for teammates who work on files."""
    out.mkdir(parents=True, exist_ok=True)
    files = {"manifest.json": dataset["manifest"], "accidents.json": dataset["accidents"],
             "articles.json": extras["articles"], "hotspots.json": dataset["hotspots"],
             "crossings.geojson": dataset["crossings"], "measures.json": dataset["measures"],
             "streets.geojson": dataset["streets"], "raport_geocodare.json": extras["raport_geocodare"]}
    for name, value in files.items():
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
