"""Linia de comandă a ariei C (rulați cu Python-ul din .venv).

    python -m coordonate descarca            # o singură dată: indexul OSM local (osmnx)
    python -m coordonate ruleaza             # cere calea către accidents.json
    python -m coordonate ruleaza --intrare ai/work/results/hybrid/accidents.json
    python -m coordonate noduri [--propune]  # nodurile cunoscute de verificat
    python -m coordonate fisa                # fișa de verificare manuală (duminică)
    python -m coordonate autotest            # verificările din plan, pe datele mock
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from .aplica import (
    MOD_LIPSA, MOD_TOATE, ScriereInterzisa, actualizeaza_manifest, aplica, citeste_json,
    citeste_manifest, este_protejat, scrie_json,
)


# ------------------------------------------------------------------ intrare


def _rezolva_cale(text: str) -> Path:
    cale = Path(text.strip().strip('"').strip("'")).expanduser()
    if not cale.is_absolute():
        cale = (Path.cwd() / cale).resolve()
    if cale.is_dir():
        cale = cale / "accidents.json"
    return cale


def cere_intrarea() -> Path | None:
    """Întreabă utilizatorul unde e `accidents.json`."""
    sugestii = [c for c in config.INTRARI_SUGERATE if c.exists()]
    if not sys.stdin.isatty():
        print(
            "Lipsește --intrare și nu pot întreba (rulare neinteractivă). "
            "Exemplu: --intrare ai/work/results/hybrid/accidents.json",
            file=sys.stderr,
        )
        return None
    print("Calea către accidents.json (fișier sau folder).")
    for i, s in enumerate(sugestii, 1):
        eticheta = " (date mock)" if este_protejat(s) else ""
        print(f"  {i}. {_relativ(s)}{eticheta}")
    implicit = sugestii[0] if sugestii else None
    indiciu = f" [Enter = {_relativ(implicit)}]" if implicit else ""
    raspuns = input(f"Cale sau număr{indiciu}: ").strip()
    if not raspuns:
        return implicit
    if raspuns.isdigit() and 1 <= int(raspuns) <= len(sugestii):
        return sugestii[int(raspuns) - 1]
    return _rezolva_cale(raspuns)


def _relativ(cale: Path | None) -> str:
    """Cale relativă la repo, cu „/” (fișierele de ieșire merg pe Git)."""
    if cale is None:
        return ""
    try:
        return cale.resolve().relative_to(config.RADACINA_REPO).as_posix()
    except ValueError:
        return Path(cale).as_posix()


def _mod_date(cale: Path, evenimente: list[dict]) -> tuple[str | None, str | None]:
    """data_mode din manifestul de lângă fișier și din evenimente. (mod, eroare)."""
    moduri = {e.get("data_mode") for e in evenimente if e.get("data_mode")}
    manifest = citeste_manifest(cale) or {}
    if manifest.get("data_mode"):
        moduri.add(manifest["data_mode"])
    if len(moduri) > 1:
        return None, f"date amestecate ({', '.join(sorted(moduri))}); nu se amestecă niciodată"
    if moduri:
        return moduri.pop(), None
    if este_protejat(cale):
        return "synthetic", None
    return None, None


# ------------------------------------------------------------------ comenzi


def comanda_descarca(argumente: argparse.Namespace) -> int:
    from . import descarca

    try:
        descarca.ruleaza(fortat=argumente.forteaza)
    except ImportError as e:
        print(f"Lipsește osmnx ({e}). Folosiți Python-ul din .venv sau instalați: "
              ".venv\\Scripts\\python -m pip install -r coordonate/requirements.txt",
              file=sys.stderr)
        return 2
    return 0


def _incarca_rezolvator():
    from . import granita as modul_granita
    from .index_osm import IndexLipsa, IndexOSM
    from .noduri import NoduriCunoscute
    from .rezolvare import Rezolvator

    try:
        index = IndexOSM.incarca()
    except IndexLipsa as e:
        print(str(e), file=sys.stderr)
        return None
    granita = modul_granita.incarca()
    if not granita.disponibila:
        print("Atenție: lipsește granița municipiului; in_iasi va rămâne null. "
              "Rulează `python -m coordonate descarca --forteaza`.", file=sys.stderr)
    return Rezolvator(index, granita, NoduriCunoscute.incarca())


def comanda_ruleaza(argumente: argparse.Namespace) -> int:
    cale_intrare = _rezolva_cale(str(argumente.intrare)) if argumente.intrare else cere_intrarea()
    if cale_intrare is None:
        return 2
    if not cale_intrare.exists():
        print(f"Nu găsesc {cale_intrare}", file=sys.stderr)
        return 2
    evenimente = citeste_json(cale_intrare)
    if not isinstance(evenimente, list):
        print(f"{cale_intrare} nu conține o listă de evenimente", file=sys.stderr)
        return 2

    mod_date, eroare = _mod_date(cale_intrare, evenimente)
    if eroare:
        print(f"Opresc: {eroare}.", file=sys.stderr)
        return 3
    if argumente.mod_date and mod_date and argumente.mod_date != mod_date:
        print(f"Opresc: --mod-date {argumente.mod_date} contrazice datele ({mod_date}).",
              file=sys.stderr)
        return 3
    mod_date = mod_date or argumente.mod_date
    if mod_date is None:
        print("Opresc: nu știu dacă datele sunt `synthetic` sau `observed` (lipsește "
              "manifest.json lângă fișier și câmpul data_mode). Adaugă --mod-date.",
              file=sys.stderr)
        return 3

    cale_iesire = Path(argumente.iesire) if argumente.iesire else config.DIR_OUT / mod_date / "accidents.json"
    if este_protejat(cale_iesire):
        print(f"Opresc: nu scriu în {config.DIR_PROTEJAT} (fișiere mock).", file=sys.stderr)
        return 3

    rezolvator = _incarca_rezolvator()
    if rezolvator is None:
        return 2

    print(f"Intrare: {_relativ(cale_intrare)} ({len(evenimente)} evenimente, {mod_date})")
    rezultate_evenimente, raport, _ = aplica(
        evenimente, rezolvator, mod=argumente.mod, forteaza=argumente.forteaza,
        limita=argumente.limita, verbos=argumente.verbos,
    )
    raport.mod_date = mod_date
    raport.intrare = _relativ(cale_intrare)
    raport.iesire = _relativ(cale_iesire)

    try:
        scrie_json(cale_iesire, rezultate_evenimente)
        cale_raport = cale_iesire.parent / "raport_coordonate.json"
        scrie_json(cale_raport, raport.ca_dict())
    except ScriereInterzisa as e:
        print(f"Opresc: {e}", file=sys.stderr)
        return 3

    stat = raport.statistici
    print(f"\nScris: {_relativ(cale_iesire)}")
    print(f"Raport: {_relativ(cale_raport)}")
    print(json.dumps(stat, ensure_ascii=False, indent=1))
    manifest = citeste_manifest(cale_intrare) or {}
    print("\nPentru manifest (le preia persoana 1):")
    print(json.dumps(actualizeaza_manifest(manifest, stat), ensure_ascii=False, indent=1))

    neverificate = stat.get("noduri_neverificate_potrivite") or {}
    if neverificate:
        total = sum(neverificate.values())
        print(
            f"\n>>> VERIFICARE NECESARĂ: {total} evenimente ar folosi noduri cunoscute "
            f"încă nevalidate ({', '.join(neverificate)}).\n"
            ">>> Rulează `python -m coordonate noduri`, verifică link-urile și pune "
            "verificat=true în coordonate/date_referinta/noduri_cunoscute.json."
        )
    if mod_date == "synthetic":
        print("\nDATE SINTETICE: nu se folosesc în demo sau în pitch.")
    return 0


def comanda_noduri(argumente: argparse.Namespace) -> int:
    from . import noduri as modul_noduri
    from .index_osm import IndexLipsa, IndexOSM

    try:
        index = IndexOSM.incarca()
    except IndexLipsa as e:
        print(str(e), file=sys.stderr)
        return 2
    existente = modul_noduri.NoduriCunoscute.incarca()
    if argumente.propune:
        propuse, negasite = modul_noduri.propune(index, existente)
        cale = modul_noduri.scrie(propuse)
        print(f"Scris: {_relativ(cale)} ({len(propuse)} noduri)")
        if negasite:
            print(f"Negăsite în OSM (nu am propus nimic): {', '.join(negasite)}")
        existente = modul_noduri.NoduriCunoscute.incarca()
    print(modul_noduri.raport(existente, index))
    rest = len(existente.neverificate())
    if rest:
        print(f"\n>>> {rest} noduri așteaptă verificarea: deschide link-urile, apoi editează "
              f"{_relativ(config.FISIER_NODURI)} (verificat, verificat_de, verificat_la).")
    return 0


def comanda_fisa(argumente: argparse.Namespace) -> int:
    from . import verificare

    cale_intrare = _rezolva_cale(str(argumente.intrare))
    if not cale_intrare.exists():
        print(f"Nu găsesc {cale_intrare}", file=sys.stderr)
        return 2
    try:
        rezultat = verificare.genereaza(
            cale_intrare,
            Path(argumente.raport) if argumente.raport else cale_intrare.parent / "raport_coordonate.json",
            Path(argumente.iesire) if argumente.iesire else cale_intrare.parent,
            cale_hotspots=Path(argumente.hotspots) if argumente.hotspots else None,
            limita_hotspots=argumente.top,
        )
    except ScriereInterzisa as e:
        print(f"Opresc: {e}", file=sys.stderr)
        return 3
    rezultat["json"] = _relativ(Path(rezultat["json"]))
    rezultat["markdown"] = _relativ(Path(rezultat["markdown"]))
    print(json.dumps(rezultat, ensure_ascii=False, indent=1))
    return 0


def comanda_autotest(argumente: argparse.Namespace) -> int:
    from . import autotest

    return autotest.ruleaza(Path(argumente.intrare))


# ------------------------------------------------------------------ parser


def construieste_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coordonate",
        description="Aria C: coordonatele accidentelor (Harta pietonului, Iași)",
    )
    sub = parser.add_subparsers(dest="comanda", required=True)

    p = sub.add_parser("descarca", help="descarcă datele OSM cu osmnx și construiește indexul local")
    p.add_argument("--forteaza", action="store_true", help="descarcă din nou chiar dacă indexul există")

    p = sub.add_parser("ruleaza", help="completează lat/lon/precizie_loc/in_iasi")
    p.add_argument("--intrare", type=str, default=None,
                   help="accidents.json (fișier sau folder); dacă lipsește, se cere la pornire")
    p.add_argument("--iesire", type=Path, default=None,
                   help="implicit coordonate/out/<data_mode>/accidents.json")
    p.add_argument("--mod", choices=(MOD_LIPSA, MOD_TOATE), default=MOD_TOATE,
                   help="toate = recalculează (implicit); lipsa = doar fără coordonate")
    p.add_argument("--mod-date", dest="mod_date", choices=("synthetic", "observed"), default=None,
                   help="doar dacă intrarea nu are manifest.json / data_mode")
    p.add_argument("--forteaza", action="store_true", help="rescrie și evenimentele cu verificat: true")
    p.add_argument("--limita", type=int, default=None, help="procesează cel mult N evenimente")
    p.add_argument("--verbos", action="store_true", help="afișează fiecare eveniment")

    p = sub.add_parser("noduri", help="nodurile cunoscute (Podu Roș...) și starea verificării")
    p.add_argument("--propune", action="store_true", help="(re)generează propunerile din OSM")

    p = sub.add_parser("fisa", help="fișa de verificare manuală (duminică)")
    p.add_argument("--intrare", type=Path, default=config.DIR_OUT / "observed" / "accidents.json")
    p.add_argument("--raport", type=Path, default=None)
    p.add_argument("--hotspots", type=Path, default=None, help="limitează la top N locații")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--iesire", type=Path, default=None)

    p = sub.add_parser("autotest", help="verificările din plan, pe datele mock")
    p.add_argument("--intrare", type=Path, default=config.INTRARE_MOCK)
    return parser


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    argumente = construieste_parser().parse_args(argv)
    comenzi = {
        "descarca": comanda_descarca, "ruleaza": comanda_ruleaza, "noduri": comanda_noduri,
        "fisa": comanda_fisa, "autotest": comanda_autotest,
    }
    return comenzi[argumente.comanda](argumente)
