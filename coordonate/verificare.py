"""Fișa de verificare manuală a localizărilor (duminică, 09:30–12:00).

Taskurile C5 / V1–V2 cer deschiderea articolelor și confirmarea pinului pe
hartă. Modulul generează o fișă cu tot ce trebuie deschis (articole, OSM,
Street View, Mapillary) și cu ce a semnalat geocodarea ca nesigur, plus un
registru în care se notează **corecturile**, nu doar „OK”.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .aplica import ScriereInterzisa, citeste_json, este_protejat, scrie_json


def link_osm(lat: float, lon: float, zoom: int = 19) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map={zoom}/{lat}/{lon}"


def link_street_view(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps?q&layer=c&cbll={lat},{lon}"


def link_mapillary(lat: float, lon: float) -> str:
    return f"https://www.mapillary.com/app/?lat={lat}&lng={lon}&z=18"


def _event_ids_din_hotspots(cale: Path, limita: int = 10) -> list[str]:
    hotspots = citeste_json(cale)
    hotspots = sorted(hotspots, key=lambda h: -(h.get("scor") or 0))[:limita]
    ids: list[str] = []
    for h in hotspots:
        for ev in h.get("event_ids") or []:
            if ev not in ids:
                ids.append(ev)
    return ids


def construieste(
    accidente: list[dict],
    raport: dict | None = None,
    *,
    event_ids: list[str] | None = None,
) -> list[dict]:
    pe_id: dict[str, dict] = {}
    for inregistrare in (raport or {}).get("evenimente", []):
        pe_id[inregistrare.get("event_id")] = inregistrare

    rezultat: list[dict] = []
    for eveniment in accidente:
        id_ev = eveniment.get("event_id")
        if event_ids is not None and id_ev not in event_ids:
            continue
        lat, lon = eveniment.get("lat"), eveniment.get("lon")
        detalii = pe_id.get(id_ev, {})
        punct_orientativ = detalii.get("punct_orientativ")
        linkuri = {}
        if lat is not None and lon is not None:
            linkuri = {
                "osm": link_osm(lat, lon),
                "street_view": link_street_view(lat, lon),
                "mapillary": link_mapillary(lat, lon),
                "orientativ": False,
            }
        elif punct_orientativ:
            p_lat, p_lon = punct_orientativ["lat"], punct_orientativ["lon"]
            linkuri = {
                "osm": link_osm(p_lat, p_lon, zoom=16),
                "street_view": link_street_view(p_lat, p_lon),
                "mapillary": link_mapillary(p_lat, p_lon),
                "orientativ": True,
            }

        rezultat.append(
            {
                "event_id": id_ev,
                "data_eveniment": eveniment.get("data_eveniment"),
                "ora": eveniment.get("ora"),
                "gravitate": eveniment.get("gravitate"),
                "loc_text": eveniment.get("loc_text"),
                "precizie_loc": eveniment.get("precizie_loc"),
                "in_iasi": eveniment.get("in_iasi"),
                "lat": lat,
                "lon": lon,
                "punct_orientativ": punct_orientativ,
                "metoda": detalii.get("metoda"),
                "incredere": detalii.get("incredere"),
                "referinte_osm": detalii.get("referinte_osm") or [],
                "avertismente": detalii.get("avertismente") or [],
                "de_verificat": detalii.get("de_verificat") or [],
                "urls": eveniment.get("urls") or [],
                "linkuri_harta": linkuri,
                "corectura": {
                    "lat_corect": None,
                    "lon_corect": None,
                    "precizie_corecta": None,
                    "in_iasi_corect": None,
                    "nota": None,
                    "verificat_de": None,
                },
            }
        )
    return rezultat


def ca_markdown(fise: list[dict], titlu: str = "Fișă de verificare a localizărilor") -> str:
    linii = [
        f"# {titlu}",
        "",
        "Pentru fiecare eveniment: deschide **toate** articolele, confirmă data, locul și",
        "gravitatea, apoi confirmă pinul pe OSM / Street View / Mapillary. Notează ce ai",
        "**corectat**, nu doar „OK”. Corecturile se trec și în `fisa_verificare.json`.",
        "",
        f"Evenimente în fișă: **{len(fise)}**",
        "",
    ]
    for fisa in fise:
        linii.append(f"## {fisa['event_id']} — {fisa.get('loc_text') or '(fără loc_text)'}")
        linii.append("")
        linii.append(
            f"- data: `{fisa.get('data_eveniment')}` · ora: `{fisa.get('ora')}` · "
            f"gravitate: `{fisa.get('gravitate')}`"
        )
        linii.append(
            f"- localizare: `{fisa.get('precizie_loc')}` · in_iasi: `{fisa.get('in_iasi')}` · "
            f"metodă: `{fisa.get('metoda')}` · încredere: `{fisa.get('incredere')}`"
        )
        if fisa.get("lat") is not None:
            linii.append(f"- coordonate: `{fisa['lat']}, {fisa['lon']}`")
            linkuri = fisa["linkuri_harta"]
            linii.append(
                f"- hartă: [OSM]({linkuri['osm']}) · "
                f"[Street View]({linkuri['street_view']}) · "
                f"[Mapillary]({linkuri['mapillary']})"
            )
        elif pt := fisa.get("punct_orientativ"):
            linii.append("- coordonate: **lipsă** (localizare vagă)")
            linii.append(f"- punct orientativ zonă/stradă: `{pt['lat']}, {pt['lon']}`")
            linkuri = fisa.get("linkuri_harta") or {}
            if "osm" in linkuri:
                linii.append(
                    f"- hartă orientativă: [OSM zonă]({linkuri['osm']}) · "
                    f"[Street View]({linkuri['street_view']}) · "
                    f"[Mapillary]({linkuri['mapillary']})"
                )
        else:
            linii.append("- coordonate: **lipsă** (localizare vagă)")
        if fisa.get("referinte_osm"):
            referinte = ", ".join(
                f"[{r}](https://www.openstreetmap.org/{r})" for r in fisa["referinte_osm"]
            )
            linii.append(f"- obiecte OSM folosite: {referinte}")
        for url in fisa.get("urls") or []:
            linii.append(f"- articol: {url}")
        for nota in fisa.get("avertismente") or []:
            linii.append(f"- ⚠ {nota}")
        for nota in fisa.get("de_verificat") or []:
            linii.append(f"- de verificat: {nota}")
        linii.extend(
            [
                "",
                "- [ ] data confirmată din articol",
                "- [ ] locul confirmat din articol",
                "- [ ] gravitatea confirmată din articol",
                "- [ ] nu e dublură a altui eveniment",
                "- [ ] pin confirmat pe hartă / Street View / Mapillary",
                "",
                "Corectură: ____________________________________________",
                "",
            ]
        )
    return "\n".join(linii)


def genereaza(
    cale_accidente: Path,
    cale_raport: Path | None,
    director_iesire: Path,
    *,
    cale_hotspots: Path | None = None,
    limita_hotspots: int = 10,
) -> dict[str, Any]:
    accidente = citeste_json(cale_accidente)
    raport = None
    if cale_raport and Path(cale_raport).exists():
        try:
            raport = citeste_json(cale_raport)
        except json.JSONDecodeError:
            raport = None
    event_ids = None
    if cale_hotspots and Path(cale_hotspots).exists():
        event_ids = _event_ids_din_hotspots(Path(cale_hotspots), limita_hotspots)

    fise = construieste(accidente, raport, event_ids=event_ids)
    director_iesire = Path(director_iesire)
    cale_json = director_iesire / "fisa_verificare.json"
    cale_md = director_iesire / "fisa_verificare.md"
    if este_protejat(cale_md):
        raise ScriereInterzisa(f"nu scriu fișa în fișierele mock: {cale_md}")
    scrie_json(cale_json, fise)
    cale_md.write_text(ca_markdown(fise), encoding="utf-8")
    return {"json": cale_json.as_posix(), "markdown": cale_md.as_posix(), "nr_fise": len(fise)}
