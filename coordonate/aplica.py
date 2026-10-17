"""Aplicarea rezultatelor pe `accidents.json` + raportul de rulare.

Scriem exact patru câmpuri din contract: `lat`, `lon`, `precizie_loc`,
`in_iasi`. Restul rămâne neatins — conținutul e al persoanei 2.
Tot ce e explicație (metodă, avertismente, ce e de verificat) merge în raportul
separat `raport_coordonate.json`, ca să nu umflăm fișierul de contract.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import config
from .rezolvare import Rezolvator, Rezultat

ORDINE_CAMPURI = (
    "event_id", "article_ids", "urls", "data_eveniment", "ora", "loc_text",
    "precizie_loc", "lat", "lon", "in_iasi", "participanti", "cauza_raportata",
    "gravitate", "noapte", "dovezi", "verificat",
)

MOD_LIPSA = "lipsa"
MOD_TOATE = "toate"


# ------------------------------------------------------------------ fișiere


class ScriereInterzisa(Exception):
    """Încercare de a scrie în `false_data/` (fișierele mock nu se modifică)."""


def este_protejat(cale: Path) -> bool:
    return Path(cale).resolve().is_relative_to(config.DIR_PROTEJAT.resolve())


def citeste_json(cale: Path) -> Any:
    with Path(cale).open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def scrie_json(cale: Path, date: Any) -> None:
    cale = Path(cale)
    if este_protejat(cale):
        raise ScriereInterzisa(f"nu scriu în {config.DIR_PROTEJAT} (fișiere mock): {cale}")
    cale.parent.mkdir(parents=True, exist_ok=True)
    temp = cale.with_suffix(cale.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(date, f, ensure_ascii=False, indent=1)
        f.write("\n")
    temp.replace(cale)


def citeste_manifest(cale_accidente: Path) -> dict | None:
    cale = Path(cale_accidente).parent / "manifest.json"
    if not cale.exists():
        return None
    try:
        return citeste_json(cale)
    except (OSError, json.JSONDecodeError):
        return None


def reordoneaza(eveniment: dict) -> dict:
    ordonat = {c: eveniment[c] for c in ORDINE_CAMPURI if c in eveniment}
    for cheie, valoare in eveniment.items():
        if cheie not in ordonat:
            ordonat[cheie] = valoare
    return ordonat


# ------------------------------------------------------------------ raport


@dataclass
class Raport:
    mod_date: str | None = None
    intrare: str | None = None
    iesire: str | None = None
    generat_la: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    granita: dict = field(default_factory=dict)
    statistici: dict = field(default_factory=dict)
    retea: dict = field(default_factory=dict)
    evenimente: list[dict] = field(default_factory=list)

    def ca_dict(self) -> dict:
        return {
            "generat_la": self.generat_la,
            "data_mode": self.mod_date,
            "intrare": self.intrare,
            "iesire": self.iesire,
            "granita": self.granita,
            "statistici": self.statistici,
            "retea": self.retea,
            "sursa_date": "OpenStreetMap contributors, ODbL 1.0 (index local construit cu osmnx)",
            "evenimente": self.evenimente,
        }


def _numara(valori: Iterable[str]) -> dict[str, int]:
    rezultat: dict[str, int] = {}
    for v in valori:
        rezultat[v] = rezultat.get(v, 0) + 1
    return dict(sorted(rezultat.items(), key=lambda kv: (-kv[1], kv[0])))


def statistici(evenimente: list[dict], rezultate: dict[str, Rezultat]) -> dict:
    precizii = [e.get("precizie_loc") or "vag" for e in evenimente]
    in_iasi = [e.get("in_iasi") for e in evenimente]
    precis = [
        e
        for e in evenimente
        if (e.get("precizie_loc") in config.PRECIZII_IN_CLASAMENT)
        and e.get("lat") is not None
        and e.get("in_iasi") is True
    ]
    return {
        "nr_evenimente": len(evenimente),
        # definiția folosită pentru manifest: precizie de clasament + în municipiu
        "nr_localizate_precis": len(precis),
        "nr_cu_coordonate": sum(1 for e in evenimente if e.get("lat") is not None),
        "nr_fara_coordonate": sum(1 for e in evenimente if e.get("lat") is None),
        "nr_in_iasi": sum(1 for v in in_iasi if v is True),
        "nr_in_afara_iasi": sum(1 for v in in_iasi if v is False),
        "nr_in_iasi_necunoscut": sum(1 for v in in_iasi if v is None),
        "pe_precizie": _numara(precizii),
        "pe_metoda": _numara(r.metoda for r in rezultate.values()),
        "pe_incredere": _numara(r.incredere for r in rezultate.values()),
        "nr_procesate_acum": len(rezultate),
        "nr_de_verificat_manual": sum(1 for r in rezultate.values() if r.de_verificat),
        # evenimente care ar fi folosit un nod cunoscut încă nevalidat
        "noduri_neverificate_potrivite": _numara(
            n for r in rezultate.values() for n in r.noduri_neverificate
        ),
    }


# ------------------------------------------------------------------ aplicare


def aplica(
    evenimente: list[dict],
    rezolvator: Rezolvator,
    *,
    mod: str = MOD_TOATE,
    forteaza: bool = False,
    limita: int | None = None,
    verbos: bool = False,
) -> tuple[list[dict], Raport, dict[str, Rezultat]]:
    """Completează câmpurile de localizare. Întoarce (evenimente, raport, rezultate)."""
    raport = Raport()
    rezultate: dict[str, Rezultat] = {}
    iesire: list[dict] = []
    procesate = 0

    for brut in evenimente:
        eveniment = dict(brut)
        id_ev = eveniment.get("event_id") or f"(fără event_id, poziția {len(iesire)})"
        motiv_sarit: str | None = None

        are_coordonate = eveniment.get("lat") is not None and eveniment.get("lon") is not None
        if eveniment.get("verificat") is True and not forteaza:
            motiv_sarit = "verificat_manual"
        elif mod == MOD_LIPSA and are_coordonate:
            motiv_sarit = "are_deja_coordonate"
        elif limita is not None and procesate >= limita:
            motiv_sarit = "limita_atinsa"

        if motiv_sarit:
            raport.evenimente.append(
                {"event_id": id_ev, "sarit": motiv_sarit, "loc_text": eveniment.get("loc_text")}
            )
            iesire.append(reordoneaza(eveniment))
            continue

        if verbos:
            print(f"[{id_ev}] {eveniment.get('loc_text')!r}")
        rezultat = rezolvator.rezolva(eveniment.get("loc_text"))
        procesate += 1
        rezultate[id_ev] = rezultat

        eveniment["lat"] = rezultat.lat
        eveniment["lon"] = rezultat.lon
        eveniment["precizie_loc"] = rezultat.precizie_loc
        eveniment["in_iasi"] = rezultat.in_iasi

        inregistrare = {"event_id": id_ev, **rezultat.ca_dict()}
        raport.evenimente.append(inregistrare)
        if verbos:
            print(
                f"    → {rezultat.precizie_loc} / {rezultat.metoda} / "
                f"in_iasi={rezultat.in_iasi} ({rezultat.lat}, {rezultat.lon})"
            )
        iesire.append(reordoneaza(eveniment))

    raport.statistici = statistici(iesire, rezultate)
    raport.granita = rezolvator.granita.descriere()
    raport.retea = rezolvator.statistici()
    return iesire, raport, rezultate


def actualizeaza_manifest(manifest: dict, stat: dict) -> dict:
    """Valorile pe care persoana 1 le poate copia în `manifest.json`.

    Nu scriem noi în manifest: are un singur proprietar (persoana 1).
    """
    propus = dict(manifest or {})
    propus["nr_localizate_precis"] = stat["nr_localizate_precis"]
    return {
        "nr_localizate_precis": stat["nr_localizate_precis"],
        "nr_evenimente": stat["nr_evenimente"],
        "observatii": {
            "nr_in_afara_iasi": stat["nr_in_afara_iasi"],
            "nr_fara_coordonate": stat["nr_fara_coordonate"],
            "nr_in_iasi_necunoscut": stat["nr_in_iasi_necunoscut"],
        },
        "manifest_propus": propus,
    }
