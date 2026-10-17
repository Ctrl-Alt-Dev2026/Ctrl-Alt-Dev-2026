"""Configurația ariei C — coordonate (persoana 3).

Aici stau doar setări și căi. Nicio coordonată de accident nu se scrie în acest
fișier: tot ce ajunge în `accidents.json` vine din indexul OSM local, construit
o singură dată cu osmnx (`python -m coordonate descarca`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------- căi

DIR_MODUL = Path(__file__).resolve().parent
RADACINA_REPO = DIR_MODUL.parent

DIR_CACHE = Path(os.environ.get("SAFEIASI_CACHE", DIR_MODUL / "cache"))
DIR_REFERINTA = DIR_MODUL / "date_referinta"
DIR_OSM = DIR_REFERINTA / "osm"
DIR_OUT = Path(os.environ.get("SAFEIASI_OUT", DIR_MODUL / "out"))

# Indexul local (străzi, noduri, treceri, repere, cartiere, adrese).
FISIER_INDEX = DIR_OSM / "index_osm.json.gz"
# Granițele administrative (municipiul Iași + comunele din jur).
FISIER_UNITATI = DIR_OSM / "unitati_admin.geojson"
# Alias-uri de nume (doar text -> text, fără coordonate).
FISIER_ALIAS = DIR_REFERINTA / "alias_nume.json"
# Noduri cunoscute (Podu Roș, Piața Unirii...), legate de obiecte OSM și
# verificate de un om înainte de a fi folosite.
FISIER_NODURI = DIR_REFERINTA / "noduri_cunoscute.json"

DIR_PROTEJAT = RADACINA_REPO / "false_data"  # fișierele mock nu se scriu niciodată
INTRARE_MOCK = DIR_PROTEJAT / "accidents.json"
# Ce propunem la promptul de rulare, în ordine (primul care există).
INTRARI_SUGERATE = (
    RADACINA_REPO / "ai" / "work" / "results" / "hybrid" / "accidents.json",
    INTRARE_MOCK,
)

# ---------------------------------------------------------------- identificare

APP_NAME = "SafeIasi-HartaPietonului"
APP_VERSION = "0.2.0"
USER_AGENT = f"{APP_NAME}/{APP_VERSION} (Hackathon AI Iasi 2026)"

# Overpass e folosit doar de osmnx, doar la `descarca`. Rezolvarea e locală.
OVERPASS_URL = os.environ.get("SAFEIASI_OVERPASS", "https://overpass-api.de/api")
TIMEOUT_DESCARCARE_SEC = 600

# ---------------------------------------------------------------- geografie


@dataclass(frozen=True)
class Bbox:
    sud: float
    vest: float
    nord: float
    est: float

    def pentru_osmnx(self) -> tuple[float, float, float, float]:
        # osmnx 2.x: (left, bottom, right, top)
        return (self.vest, self.sud, self.est, self.nord)

    def contine(self, lat: float, lon: float) -> bool:
        return self.sud <= lat <= self.nord and self.vest <= lon <= self.est


# Municipiul Iași + localitățile conexe (Valea Lupului, Tomești, Miroslava,
# Ciurea, Bârnova, Holboca, Rediu, Lețcani...). Evenimentele de acolo primesc
# coordonate, dar `in_iasi: false`, deci nu intră în clasament.
BBOX_DATE = Bbox(sud=47.00, vest=27.30, nord=47.35, est=27.85)

ORAS = "Iași"
OSM_RELATIE_MUNICIPIU = 1207838  # relation/1207838, admin_level=8

# ---------------------------------------------------------------- raze (metri)

# Două noduri de intersecție mai apropiate de atât sunt tratate ca una singură.
RAZA_GRUPARE_NODURI = 40.0
# Bucăți ale aceleiași străzi mai apropiate de atât sunt aceeași stradă.
RAZA_UNIRE_COMPONENTE = 120.0
# Trecere căutată în jurul unui reper punctual (mall, gară, stație, școală).
RAZA_TRECERE_LANGA_REPER = 90.0
# Cât de departe poate fi strada de reper ca „pe X, în dreptul Y” să fie coerent.
RAZA_STRADA_LANGA_REPER = 250.0
# Componente de stradă cu același nume, mai departe de atât: străzi diferite.
RAZA_AMBIGUITATE_STRADA = 1500.0

# ---------------------------------------------------------------- precizie

# Ordinea crescătoare a preciziei. `vag` nu primește niciodată lat/lon.
PRECIZII = ("vag", "strada", "segment", "intersectie", "trecere")
PRECIZII_CU_COORDONATE = ("strada", "segment", "intersectie", "trecere")
PRECIZII_IN_CLASAMENT = ("trecere", "intersectie", "segment")  # secțiunea 5 din plan
