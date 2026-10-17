"""Indexul OSM local: încărcare și căutări, fără rețea.

Toate răspunsurile trimit la obiecte OSM reale (`node/…`, `way/…`), ca să se
poată verifica pe openstreetmap.org. Nimic nu e calculat din coordonate scrise
de mână.
"""

from __future__ import annotations

import gzip
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from . import config
from .geometrie import Punct, centru_grup, distanta_m, grupeaza_puncte, intersectie_segmente
from .normalizare import cheie_baza, cheie_nume, prefix_canonic, variante_nominativ

# potrivirea unui nume (cât de sigur e că e același obiect)
POTRIVIRE_EXACTA = 3      # aceeași cheie, inclusiv prefixul („bulevardul socola”)
POTRIVIRE_BAZA = 2        # același nume fără prefix („socola”)
POTRIVIRE_CUVINTE = 1     # toate cuvintele cerute apar în numele OSM („palas” ⊂ „palas mall”)

CLASE_STATIE = {("highway", "bus_stop"), ("railway", "tram_stop"), ("public_transport", "platform"),
                ("public_transport", "stop_position"), ("railway", "halt")}


class IndexLipsa(Exception):
    """Indexul OSM nu a fost descărcat încă."""


# ------------------------------------------------------------------ obiecte


@dataclass
class Componenta:
    """O bucată conexă dintr-o stradă cu nume."""

    cheie: str
    pozitie: int
    nume: str
    variante: list[str]
    highway: list[str]
    way_ids: list[int]
    segmente: list[tuple[int, int]]
    bbox: tuple[float, float, float, float]
    punct: Punct
    unitate: str | None = None
    noduri: set[int] = field(default_factory=set)

    @property
    def id(self) -> str:
        return f"{self.cheie}#{self.pozitie}"

    @property
    def referinta_osm(self) -> str:
        return f"way/{self.way_ids[0]}" if self.way_ids else self.id


@dataclass
class Obiect:
    """Un obiect punctual din OSM: trecere, reper sau loc."""

    osm: str
    nume: str | None
    lat: float
    lon: float
    fel: str
    clasa: str | None = None
    tip: str | None = None
    variante: list[str] = field(default_factory=list)
    strazi: list[str] = field(default_factory=list)

    @property
    def punct(self) -> Punct:
        return (self.lat, self.lon)

    @property
    def este_statie(self) -> bool:
        return (self.clasa, self.tip) in CLASE_STATIE

    def ca_dict(self) -> dict:
        return {
            "osm": self.osm, "nume": self.nume, "fel": self.fel, "clasa": self.clasa,
            "tip": self.tip, "lat": self.lat, "lon": self.lon,
        }


@dataclass
class Intersectie:
    punct: Punct
    noduri: list[int]
    componente: list[str]

    @property
    def referinta_osm(self) -> str:
        return f"node/{self.noduri[0]}"


# ------------------------------------------------------------------ index


class IndexOSM:
    def __init__(self, date: dict) -> None:
        self.meta = date.get("meta", {})
        self.noduri: dict[int, Punct] = {int(k): (v[0], v[1]) for k, v in date["noduri"].items()}

        self.strazi: dict[str, list[Componenta]] = {}
        self.componente: dict[str, Componenta] = {}
        self.pe_baza: dict[str, set[str]] = defaultdict(set)
        self.pe_varianta: dict[str, set[str]] = defaultdict(set)
        self.pe_cuvant_strada: dict[str, set[str]] = defaultdict(set)
        self.nod_la_componente: dict[int, set[str]] = defaultdict(set)
        for cheie, comps in date["strazi"].items():
            lista = []
            for i, c in enumerate(comps):
                segmente = [(int(u), int(v)) for u, v in c["segmente"]]
                comp = Componenta(
                    cheie=cheie, pozitie=i, nume=c["nume"], variante=c.get("variante") or [c["nume"]],
                    highway=c.get("highway") or [], way_ids=c.get("way_ids") or [],
                    segmente=segmente, bbox=tuple(c["bbox"]), punct=tuple(c["punct"]),
                    unitate=c.get("unitate"),
                    noduri={n for s in segmente for n in s},
                )
                lista.append(comp)
                self.componente[comp.id] = comp
                for n in comp.noduri:
                    self.nod_la_componente[n].add(comp.id)
            self.strazi[cheie] = lista
            for varianta in {v for c in comps for v in (c.get("variante") or [c["nume"]])}:
                self.pe_varianta[cheie_nume(varianta)].add(cheie)
                self.pe_baza[cheie_baza(varianta)].add(cheie)
                for cuv in cheie_baza(varianta).split():
                    self.pe_cuvant_strada[cuv].add(cheie)

        self.treceri = [
            Obiect(osm=t["osm"], nume=None, lat=t["lat"], lon=t["lon"], fel="trecere",
                   tip=t.get("crossing"), strazi=t.get("strazi") or [])
            for t in date.get("treceri", [])
        ]
        self.treceri_pe_componenta: dict[str, list[Obiect]] = defaultdict(list)
        for t in self.treceri:
            for comp_id in t.strazi:
                self.treceri_pe_componenta[comp_id].append(t)
        self._grila_treceri = _Grila(self.treceri)

        self.poi = [
            Obiect(osm=p["osm"], nume=p["nume"], lat=p["lat"], lon=p["lon"], fel="poi",
                   clasa=p.get("clasa"), tip=p.get("tip"), variante=p.get("variante") or [p["nume"]])
            for p in date.get("poi", [])
        ]
        self.locuri = [
            Obiect(osm=p["osm"], nume=p["nume"], lat=p["lat"], lon=p["lon"], fel="loc",
                   tip=p.get("tip"), variante=p.get("variante") or [p["nume"]])
            for p in date.get("locuri", [])
        ]
        self._poi_pe_cuvant = _index_cuvinte(self.poi)
        self._locuri_pe_cuvant = _index_cuvinte(self.locuri)
        self.adrese: dict[str, dict[str, list]] = date.get("adrese", {})

    # ------------------------------------------------------------ încărcare

    @classmethod
    def incarca(cls, cale: Path | None = None) -> "IndexOSM":
        return _incarca_cache(str(Path(cale or config.FISIER_INDEX)))

    # ------------------------------------------------------------ străzi

    def strazi_dupa_nume(self, nume: str) -> tuple[list[Componenta], int]:
        """Componentele unei străzi după nume, cu nivelul de potrivire."""
        cheie = cheie_nume(nume)
        if not cheie:
            return [], 0
        are_prefix = prefix_canonic(nume) is not None
        if are_prefix and cheie in self.pe_varianta:
            return self._comps(self.pe_varianta[cheie]), POTRIVIRE_EXACTA
        baza = cheie_baza(nume)
        if baza in self.pe_baza:
            return self._comps(self.pe_baza[baza]), POTRIVIRE_BAZA
        cuv = baza.split()
        if len(cuv) >= 2:
            candidati = set.intersection(*(self.pe_cuvant_strada.get(c, set()) for c in cuv))
            if candidati:
                return self._comps(candidati), POTRIVIRE_CUVINTE
        return [], 0

    def _comps(self, chei: Iterable[str]) -> list[Componenta]:
        return [c for k in sorted(chei) for c in self.strazi.get(k, [])]

    def treceri_pe(self, comp: Componenta) -> list[Obiect]:
        return _comaseaza(self.treceri_pe_componenta.get(comp.id, []), config.RAZA_GRUPARE_NODURI)

    def adresa(self, comp: Componenta, numar: str) -> tuple[Punct, str] | None:
        for varianta in comp.variante:
            gasit = self.adrese.get(cheie_nume(varianta), {}).get(numar.upper())
            if gasit:
                return (gasit[0], gasit[1]), gasit[2]
        return None

    def punct_pe_strada(self, comp: Componenta, punct: Punct) -> tuple[Punct, float]:
        """Proiecția punctului pe cea mai apropiată porțiune a străzii."""
        cel_mai_bun: tuple[Punct, float] | None = None
        for u, v in comp.segmente:
            p = _proiectie(punct, self.noduri[u], self.noduri[v])
            d = distanta_m(p, punct)
            if cel_mai_bun is None or d < cel_mai_bun[1]:
                cel_mai_bun = (p, d)
        assert cel_mai_bun is not None
        return cel_mai_bun

    # ------------------------------------------------------------ intersecții

    def intersectii(
        self, comps_a: list[Componenta], comps_b: list[Componenta]
    ) -> tuple[list[Intersectie], list[Punct]]:
        """Noduri comune (intersecții reale) și suprapuneri doar în plan (pasaje)."""
        ids_a = {c.id for c in comps_a}
        ids_b = {c.id for c in comps_b}
        noduri_a = set().union(*(c.noduri for c in comps_a)) if comps_a else set()
        noduri_b = set().union(*(c.noduri for c in comps_b)) if comps_b else set()
        comune = sorted(noduri_a & noduri_b)

        grupuri = grupeaza_puncte([self.noduri[n] for n in comune], config.RAZA_GRUPARE_NODURI)
        rezultat: list[Intersectie] = []
        for grup in grupuri:
            centru = centru_grup(grup)
            noduri_grup = sorted(
                (n for n in comune if self.noduri[n] in grup),
                key=lambda n: distanta_m(self.noduri[n], centru),
            )
            comps = sorted({cid for n in noduri_grup for cid in self.nod_la_componente[n]
                            if cid in ids_a or cid in ids_b})
            rezultat.append(Intersectie(punct=self.noduri[noduri_grup[0]], noduri=noduri_grup,
                                        componente=comps))

        suprapuneri: list[Punct] = []
        if not rezultat:
            for ca in comps_a:
                for cb in comps_b:
                    if not _bbox_se_ating(ca.bbox, cb.bbox):
                        continue
                    for u1, v1 in ca.segmente:
                        for u2, v2 in cb.segmente:
                            p = intersectie_segmente(self.noduri[u1], self.noduri[v1],
                                                     self.noduri[u2], self.noduri[v2])
                            if p is not None:
                                suprapuneri.append(p)
        return rezultat, suprapuneri

    # ------------------------------------------------------------ treceri

    def treceri_in_jur(self, punct: Punct, raza_m: float) -> list[Obiect]:
        aproape = [t for t in self._grila_treceri.in_jur(punct, raza_m)
                   if distanta_m(t.punct, punct) <= raza_m]
        return _comaseaza(aproape, config.RAZA_GRUPARE_NODURI)

    # ------------------------------------------------------------ repere și locuri

    def poi_dupa_nume(self, nume: str, *, cu_genitiv: bool = True) -> list[tuple[Obiect, int]]:
        return _cauta_nume(self.poi, self._poi_pe_cuvant, nume, cu_genitiv)

    def locuri_dupa_nume(self, nume: str, *, cu_genitiv: bool = True) -> list[tuple[Obiect, int]]:
        return _cauta_nume(self.locuri, self._locuri_pe_cuvant, nume, cu_genitiv)

    # ------------------------------------------------------------ obiecte după id

    def punct_osm(self, referinta: str) -> Punct | None:
        """Punctul unui obiect OSM din index.

        `node/…`: nodul de stradă, trecerea, reperul sau locul cu acel id.
        `way/…` / `relation/…`: doar dacă e un reper sau un loc (punctul
        reprezentativ calculat la descărcare). Nu inventăm centre de străzi.
        """
        tip, _, ident = referinta.partition("/")
        if not ident.isdigit():
            return None
        if tip == "node" and int(ident) in self.noduri:
            return self.noduri[int(ident)]
        for obiect in (*self.treceri, *self.poi, *self.locuri):
            if obiect.osm == referinta:
                return obiect.punct
        return None


# ------------------------------------------------------------------ ajutoare


@lru_cache(maxsize=2)
def _incarca_cache(cale: str) -> IndexOSM:
    p = Path(cale)
    if not p.exists():
        raise IndexLipsa(
            f"Lipsește indexul OSM ({p}). Rulează o dată: "
            ".venv\\Scripts\\python -m coordonate descarca"
        )
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return IndexOSM(json.load(f))


def _index_cuvinte(obiecte: list[Obiect]) -> dict[str, list[int]]:
    rezultat: dict[str, list[int]] = defaultdict(list)
    for i, o in enumerate(obiecte):
        for cuv in {c for v in o.variante for c in cheie_nume(v).split()}:
            rezultat[cuv].append(i)
    return rezultat


def _scor(obiect: Obiect, cheie: str) -> int:
    cuv_cerute = set(cheie.split())
    cel_mai_bun = 0
    for v in obiect.variante:
        k = cheie_nume(v)
        if k == cheie or cheie_baza(v) == cheie:
            return POTRIVIRE_EXACTA
        if cuv_cerute and cuv_cerute <= set(k.split()):
            cel_mai_bun = max(cel_mai_bun, POTRIVIRE_CUVINTE)
    return cel_mai_bun


def _cauta_nume(obiecte, pe_cuvant, nume: str, cu_genitiv: bool) -> list[tuple[Obiect, int]]:
    chei = [cheie_nume(nume)]
    if cu_genitiv:
        chei.extend(variante_nominativ(nume))
    for cheie in chei:
        cuv = cheie.split()
        if not cuv:
            continue
        candidati = set(pe_cuvant.get(cuv[0], []))
        for c in cuv[1:]:
            candidati &= set(pe_cuvant.get(c, []))
        rezultat = [(obiecte[i], _scor(obiecte[i], cheie)) for i in candidati]
        rezultat = [(o, s) for o, s in rezultat if s > 0]
        if rezultat:
            rezultat.sort(key=lambda x: (-x[1], x[0].osm))
            return rezultat
    return []


def _comaseaza(obiecte: list[Obiect], raza_m: float) -> list[Obiect]:
    """Mai multe noduri ale aceleiași treceri (câte unul pe sens) = o trecere."""
    rezultat: list[Obiect] = []
    for o in obiecte:
        if any(distanta_m(o.punct, r.punct) <= raza_m for r in rezultat):
            continue
        rezultat.append(o)
    return rezultat


def _proiectie(p: Punct, a: Punct, b: Punct) -> Punct:
    """Proiecția lui p pe segmentul ab (aproximare plană locală)."""
    k = math.cos(math.radians(p[0]))
    ax, ay = a[1] * k, a[0]
    bx, by = b[1] * k, b[0]
    px, py = p[1] * k, p[0]
    dx, dy = bx - ax, by - ay
    lung2 = dx * dx + dy * dy
    if lung2 == 0:
        return a
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / lung2))
    return (ay + t * dy, (ax + t * dx) / k)


def _bbox_se_ating(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


class _Grila:
    """Grilă simplă pentru căutări „în jurul punctului”."""

    PAS = 0.005  # ~550 m pe latitudine

    def __init__(self, obiecte: list[Obiect]) -> None:
        self.celule: dict[tuple[int, int], list[Obiect]] = defaultdict(list)
        for o in obiecte:
            self.celule[self._celula(o.punct)].append(o)

    def _celula(self, p: Punct) -> tuple[int, int]:
        return (int(math.floor(p[0] / self.PAS)), int(math.floor(p[1] / self.PAS)))

    def in_jur(self, p: Punct, raza_m: float) -> list[Obiect]:
        pasi = max(1, int(math.ceil(raza_m / 400)))
        ci, cj = self._celula(p)
        rezultat: list[Obiect] = []
        for di in range(-pasi, pasi + 1):
            for dj in range(-pasi, pasi + 1):
                rezultat.extend(self.celule.get((ci + di, cj + dj), []))
        return rezultat
