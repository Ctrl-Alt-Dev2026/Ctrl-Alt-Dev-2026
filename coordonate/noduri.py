"""Noduri cunoscute: locuri pe care presa le numește ca intersecții.

„Podu Roș”, „Târgu Cucului” sau „Piața Unirii” nu apar în OSM ca intersecții
cu nume. Lista din `date_referinta/noduri_cunoscute.json` leagă fiecare nume de
un **nod OSM real** (fără coordonate scrise de mână). Nodul e propus automat
din indexul local, iar un om îl confirmă pe openstreetmap.org.

Regula: un nod cu `"verificat": false` NU e folosit pentru localizare. Rularea
semnalează doar că ar fi fost potrivit, ca să știi ce să verifici.

    python -m coordonate noduri              # starea listei + link-uri
    python -m coordonate noduri --propune    # (re)generează propunerile din OSM
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .geometrie import distanta_m
from .index_osm import POTRIVIRE_BAZA, POTRIVIRE_EXACTA, IndexOSM
from .normalizare import cheie_baza, cheie_nume, prefix_canonic

# Nume des întâlnite în presa din Iași ca „intersecția de la X” / „la X”.
# Lista se poate completa; propunerile se fac doar dacă OSM are obiectul.
NUME_PROPUSE: dict[str, list[str]] = {
    "Podu Roș": ["Podul Roș"],
    "Târgu Cucului": ["Tg. Cucului", "Targu Cucului"],
    "Piața Unirii": ["Unirii"],
    "Piața Mihai Eminescu": [],
    "Piața Voievozilor": [],
    "Podu de Fier": ["Podul de Fier"],
    "Agronomie": ["Rond Agronomie", "Rondul Agronomie"],
    "Piața Gării": ["Gării"],
    "Piața Independenței": [],
    "Piața Nicolina": [],
}

RAZA_NOD_LANGA_LOC = 150.0


@dataclass
class NodCunoscut:
    id: str
    nume: str
    alias: list[str] = field(default_factory=list)
    osm: str | None = None
    strazi_osm: list[str] = field(default_factory=list)
    sursa_propunere: str | None = None
    verificat: bool = False
    verificat_de: str | None = None
    verificat_la: str | None = None
    nota: str | None = None

    @property
    def link(self) -> str | None:
        return f"https://www.openstreetmap.org/{self.osm}" if self.osm else None

    def chei(self) -> set[str]:
        return {k for n in [self.nume, *self.alias] for k in (cheie_nume(n), cheie_baza(n)) if k}

    def ca_dict(self) -> dict:
        return {
            "id": self.id, "nume": self.nume, "alias": self.alias, "osm": self.osm,
            "link": self.link, "strazi_osm": self.strazi_osm,
            "sursa_propunere": self.sursa_propunere, "verificat": self.verificat,
            "verificat_de": self.verificat_de, "verificat_la": self.verificat_la,
            "nota": self.nota,
        }


class NoduriCunoscute:
    def __init__(self, noduri: list[NodCunoscut]) -> None:
        self.noduri = noduri
        self._pe_cheie: dict[str, NodCunoscut] = {}
        for nod in noduri:
            for k in nod.chei():
                self._pe_cheie.setdefault(k, nod)

    @classmethod
    def incarca(cls, cale: Path | None = None) -> "NoduriCunoscute":
        cale = Path(cale or config.FISIER_NODURI)
        if not cale.exists():
            return cls([])
        with cale.open("r", encoding="utf-8") as f:
            date = json.load(f)
        campuri = NodCunoscut.__dataclass_fields__
        return cls([
            NodCunoscut(**{k: v for k, v in n.items() if k in campuri})
            for n in date.get("noduri", [])
        ])

    def gaseste(self, nume: str) -> NodCunoscut | None:
        return self._pe_cheie.get(cheie_nume(nume)) or self._pe_cheie.get(cheie_baza(nume))

    def neverificate(self) -> list[NodCunoscut]:
        return [n for n in self.noduri if not n.verificat]


# ------------------------------------------------------------------ propuneri


def _noduri_de_intersectie(index: IndexOSM) -> dict[int, set[str]]:
    """Nod -> numele distincte ale străzilor care se întâlnesc acolo (≥ 2)."""
    rezultat: dict[int, set[str]] = {}
    for nod, comps in index.nod_la_componente.items():
        chei = {cid.split("#")[0] for cid in comps}
        if len(chei) >= 2:
            rezultat[nod] = chei
    return rezultat


def _cel_mai_bun_nod(candidati: dict[int, set[str]], index: IndexOSM, centru) -> int | None:
    if not candidati:
        return None
    return min(
        candidati,
        key=lambda n: (-len(candidati[n]), distanta_m(index.noduri[n], centru)),
    )


def _propune_unul(index: IndexOSM, nume: str, alias: list[str], intersectii,
                  municipiu: str | None) -> NodCunoscut | None:
    ident = cheie_nume(nume).replace(" ", "-")
    for varianta in [nume, *alias]:
        comps, potrivire = index.strazi_dupa_nume(varianta)
        # Doar nume identic („Piața Gării” ≠ „Strada Gării”) și doar în municipiu.
        are_prefix = prefix_canonic(varianta) is not None
        exact = potrivire == POTRIVIRE_EXACTA or (not are_prefix and potrivire == POTRIVIRE_BAZA
                                                   and all(cheie_nume(c.nume) == cheie_nume(varianta)
                                                           for c in comps))
        comps = [c for c in comps if municipiu is None or c.unitate == municipiu]
        if comps and exact:
            candidati: dict[int, set[str]] = {}
            for comp in comps:
                for n in comp.noduri:
                    if n in intersectii:
                        candidati[n] = intersectii[n]
            nod = _cel_mai_bun_nod(candidati, index, comps[0].punct)
            if nod is not None:
                return NodCunoscut(
                    id=ident, nume=nume, alias=alias, osm=f"node/{nod}",
                    strazi_osm=_nume_strazi(index, candidati[nod]),
                    sursa_propunere=(
                        f"strada OSM „{comps[0].nume}” ({comps[0].referinta_osm}); "
                        "nodul ei cu cele mai multe străzi"
                    ),
                )
        obiecte = (index.locuri_dupa_nume(varianta, cu_genitiv=False)
                   + index.poi_dupa_nume(varianta, cu_genitiv=False))
        for obiect, scor in obiecte:
            if scor < POTRIVIRE_EXACTA or cheie_nume(obiect.nume or "") != cheie_nume(varianta):
                continue
            aproape = {
                n: s for n, s in intersectii.items()
                if distanta_m(index.noduri[n], obiect.punct) <= RAZA_NOD_LANGA_LOC
            }
            nod = _cel_mai_bun_nod(aproape, index, obiect.punct)
            if nod is not None:
                return NodCunoscut(
                    id=ident, nume=nume, alias=alias, osm=f"node/{nod}",
                    strazi_osm=_nume_strazi(index, aproape[nod]),
                    sursa_propunere=(
                        f"{obiect.fel} OSM „{obiect.nume}” ({obiect.osm}, {obiect.tip}); "
                        f"intersecția cu cele mai multe străzi în {RAZA_NOD_LANGA_LOC:.0f} m"
                    ),
                )
    return None


def _nume_strazi(index: IndexOSM, chei: set[str]) -> list[str]:
    return sorted(index.strazi[k][0].nume for k in chei if k in index.strazi)


def propune(index: IndexOSM, existente: NoduriCunoscute | None = None,
            municipiu: str | None = config.ORAS) -> tuple[list[NodCunoscut], list[str]]:
    """Propuneri noi din OSM. Intrările deja verificate nu se ating."""
    intersectii = _noduri_de_intersectie(index)
    pastrate = {n.id: n for n in (existente.noduri if existente else []) if n.verificat}
    rezultat: list[NodCunoscut] = list(pastrate.values())
    negasite: list[str] = []
    for nume, alias in NUME_PROPUSE.items():
        ident = cheie_nume(nume).replace(" ", "-")
        if ident in pastrate:
            continue
        nod = _propune_unul(index, nume, alias, intersectii, municipiu)
        if nod is None:
            negasite.append(nume)
            continue
        rezultat.append(nod)
    return rezultat, negasite


def scrie(noduri: list[NodCunoscut], cale: Path | None = None) -> Path:
    cale = Path(cale or config.FISIER_NODURI)
    cale.parent.mkdir(parents=True, exist_ok=True)
    date = {
        "_citeste_ma": [
            "Noduri pe care presa le numește ca intersecții (ex. „intersecția de la Podu Roș”).",
            "Fiecare intrare trimite la un nod OSM real; nu se scriu coordonate de mână.",
            "CUM VERIFICI: deschide `link`, confirmă că nodul e intersecția pe care o știți",
            "sub acel nume. Dacă e corect: verificat=true, verificat_de, verificat_la.",
            "Dacă e greșit: înlocuiește `osm` cu nodul corect (node/<id> de pe openstreetmap.org)",
            "sau șterge intrarea. Intrările cu verificat=false NU sunt folosite la localizare.",
        ],
        "generat_la": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "noduri": [n.ca_dict() for n in noduri],
    }
    temp = cale.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(date, f, ensure_ascii=False, indent=1)
        f.write("\n")
    temp.replace(cale)
    return cale


def raport(noduri: NoduriCunoscute, index: IndexOSM | None = None) -> str:
    linii = []
    for n in noduri.noduri:
        stare = "verificat" if n.verificat else "DE VERIFICAT"
        exista = ""
        if index is not None and n.osm and index.punct_osm(n.osm) is None:
            exista = "  (!) nodul nu e în indexul OSM"
        linii.append(f"[{stare:12}] {n.nume:22} {n.osm or '-':18} {n.link or ''}{exista}")
        if n.strazi_osm:
            linii.append(f"               străzi: {', '.join(n.strazi_osm)}")
    if not linii:
        linii.append("Lista e goală. Rulează: python -m coordonate noduri --propune")
    return "\n".join(linii)
