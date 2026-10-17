"""`in_iasi`: punctul e în municipiul Iași?

Răspunsul vine din poligonul administrativ real (OSM relation/1207838,
admin_level=8), descărcat cu osmnx în `date_referinta/osm/unitati_admin.geojson`
împreună cu comunele din jur. Pentru punctele din afara municipiului spunem și
în ce comună cad (Valea Lupului, Tomești...), ca informație pentru verificare.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import config
from .geometrie import bbox_geometrie, punct_in_geometrie
from .normalizare import cheie_nume


@dataclass
class VerdictGranita:
    in_iasi: bool | None
    metoda: str
    unitate: str | None = None


@dataclass
class _Unitate:
    nume: str | None
    osm: str | None
    geometrie: dict
    bbox: tuple[float, float, float, float] | None

    def contine(self, lat: float, lon: float) -> bool:
        if self.bbox:
            sud, vest, nord, est = self.bbox
            if not (sud <= lat <= nord and vest <= lon <= est):
                return False
        return punct_in_geometrie(lat, lon, self.geometrie)


class Granita:
    def __init__(self, unitati: list[_Unitate], municipiu: _Unitate | None) -> None:
        self.unitati = unitati
        self.municipiu = municipiu

    @property
    def disponibila(self) -> bool:
        return self.municipiu is not None

    def descriere(self) -> dict:
        return {
            "metoda": "poligon_osm" if self.municipiu else "lipsa",
            "sursa": self.municipiu.osm if self.municipiu else None,
            "nume": self.municipiu.nume if self.municipiu else None,
            "nr_unitati_vecine": max(0, len(self.unitati) - 1),
        }

    def unitate(self, lat: float, lon: float) -> str | None:
        for u in self.unitati:
            if u.contine(lat, lon):
                return u.nume
        return None

    def verifica(self, lat: float | None, lon: float | None) -> VerdictGranita:
        if lat is None or lon is None:
            return VerdictGranita(None, "fara_punct")
        if self.municipiu is None:
            # fără graniță nu ghicim: necunoscut rămâne necunoscut
            return VerdictGranita(None, "granita_lipsa")
        in_iasi = self.municipiu.contine(lat, lon)
        return VerdictGranita(
            in_iasi, "poligon_osm", self.municipiu.nume if in_iasi else self.unitate(lat, lon)
        )


def incarca(cale: Path | None = None) -> Granita:
    cale = Path(cale or config.FISIER_UNITATI)
    if not cale.exists():
        return Granita([], None)
    with cale.open("r", encoding="utf-8") as f:
        colectie = json.load(f)

    unitati: list[_Unitate] = []
    municipiu: _Unitate | None = None
    tinta_osm = f"relation/{config.OSM_RELATIE_MUNICIPIU}"
    for feature in colectie.get("features", []):
        geom = feature.get("geometry")
        if not geom:
            continue
        prop = feature.get("properties") or {}
        u = _Unitate(prop.get("nume"), prop.get("osm"), geom, bbox_geometrie(geom))
        unitati.append(u)
        if prop.get("osm") == tinta_osm:
            municipiu = u
    if municipiu is None:
        municipiu = next(
            (u for u in unitati if u.nume and cheie_nume(u.nume) in ("iasi", "municipiul iasi")),
            None,
        )
    # municipiul primul, ca `unitate()` să-l găsească repede
    if municipiu is not None:
        unitati.sort(key=lambda u: u is not municipiu)
    return Granita(unitati, municipiu)
