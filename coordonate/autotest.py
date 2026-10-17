"""Verificările cerute de plan pentru aria C, plus invarianții contractului.

Din planul persoanei 3: „Testează pe datele false: ev-016 trebuie să rămână
fără coordonate, iar ev-017 trebuie marcat în afara Iașiului.”

Rulează fără rețea, pe indexul OSM local, și nu scrie nimic pe disc:
    .venv\\Scripts\\python -m coordonate autotest
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import config, granita as modul_granita, parser_loc
from .aplica import MOD_TOATE, ScriereInterzisa, aplica, citeste_json, scrie_json
from .geometrie import distanta_m, punct_in_geometrie
from .index_osm import IndexLipsa, IndexOSM
from .noduri import NodCunoscut, NoduriCunoscute
from .normalizare import alias_reper, cheie_nume, normalizeaza_strada
from .rezolvare import Rezolvator

# reguli de validare copiate din api/validate_fixtures.py (persoana 1), ca
# ieșirea noastră să treacă auditul lor
PRECIZII_API = {"trecere", "intersectie", "segment", "strada", "vag"}


class Verificari:
    def __init__(self) -> None:
        self.reusite: list[str] = []
        self.esecuri: list[str] = []

    def cere(self, conditie: bool, descriere: str, detaliu: str = "") -> None:
        if conditie:
            self.reusite.append(descriere)
        else:
            self.esecuri.append(f"{descriere}{' — ' + detaliu if detaliu else ''}")

    def raporteaza(self) -> int:
        for descriere in self.reusite:
            print(f"  ok   {descriere}")
        for descriere in self.esecuri:
            print(f"  EȘEC {descriere}")
        print(f"\n{len(self.reusite)} verificări trecute, {len(self.esecuri)} eșuate.")
        return 0 if not self.esecuri else 1


# ------------------------------------------------------------------ 1. text


def verifica_text(v: Verificari) -> None:
    print("[1] Textul (fără OSM)")
    v.cere(
        normalizeaza_strada("Bd. Demo") == normalizeaza_strada("B-dul Demo")
        == normalizeaza_strada("bulevardul demo") == "Bulevardul Demo",
        "„Bd.” = „B-dul” = „bulevardul” → „Bulevardul”",
    )
    v.cere(normalizeaza_strada("Șos. Păcurari") == "Șoseaua Păcurari", "„Șos.” → „Șoseaua”")
    v.cere(cheie_nume("Str. Gării") == "strada garii", "cheia de căutare ignoră diacriticele")
    v.cere(normalizeaza_strada("Al. I. Cuza") != "Aleea I. Cuza", "„Al. I. Cuza” nu devine „Aleea”")

    i = parser_loc.analizeaza("intersecția Păcurari cu Moara de Vânt")
    v.cere(i.perechi == [("Păcurari", "Moara de Vânt")], "intersecție „X cu Y” cu nume compus",
           str(i.perechi))
    i = parser_loc.analizeaza("pe Strada Arcu a implicat doar două autoturisme")
    v.cere(i.strazi == ["Strada Arcu"], "restul frazei nu intră în numele străzii", str(i.strazi))
    i = parser_loc.analizeaza("în zona Gării")
    v.cere(i.zone == ["Gării"] and not i.poi, "„în zona Gării” e zonă, nu gară", str(i.ca_dict()))
    i = parser_loc.analizeaza("trecerea din Nicolina")
    v.cere(i.din == ["Nicolina"] and not i.pe, "„din X” = zonă întâi", str(i.ca_dict()))
    i = parser_loc.analizeaza("trecerea de pe Alexandru cel Bun")
    v.cere(i.pe == ["Alexandru cel Bun"], "„de pe X” = stradă întâi", str(i.ca_dict()))
    i = parser_loc.analizeaza("intersecția de la Podu Roș")
    v.cere(i.la == ["Podu Roș"], "„de la X” = nod cunoscut întâi", str(i.ca_dict()))
    i = parser_loc.analizeaza("în stația Târgu Cucului")
    v.cere(len(i.poi) == 1 and i.poi[0].nume == "Târgu Cucului", "reper explicit „stația X”")
    i = parser_loc.analizeaza("în Valea Lupului, la intersecția cu drumul spre Iași")
    v.cere(not i.perechi, "„drumul spre Iași” nu e luat drept stradă", str(i.perechi))
    i = parser_loc.analizeaza("pe strada Vasile Lupu nr. 45")
    v.cere(i.numar == "45" and i.strazi == ["Strada Vasile Lupu"], "stradă + număr")
    v.cere(alias_reper("Palas") == "Palas Mall", "„Palas” înseamnă Palas Mall (alias confirmat)")

    v.cere(abs(distanta_m((47.1585, 27.6014), (47.1585, 27.6114)) - 757) < 30, "haversine plauzibil")
    patrat = {"type": "Polygon",
              "coordinates": [[[27.0, 47.0], [28.0, 47.0], [28.0, 48.0], [27.0, 48.0], [27.0, 47.0]]]}
    v.cere(punct_in_geometrie(47.5, 27.5, patrat) and not punct_in_geometrie(46.5, 27.5, patrat),
           "punct în poligon")


# ------------------------------------------------------------------ 2. OSM


def verifica_osm(v: Verificari, rez: Rezolvator) -> None:
    print("[2] Indexul OSM local")
    g = rez.granita
    v.cere(g.disponibila and g.municipiu.osm == f"relation/{config.OSM_RELATIE_MUNICIPIU}",
           "granița municipiului = OSM relation/1207838")
    v.cere(g.verifica(47.1585, 27.6014).in_iasi is True, "centrul Iașiului e în municipiu")
    v.cere(g.verifica(47.1795, 27.4998).in_iasi is False, "Valea Lupului e în afara municipiului")

    def caz(text, precizie, descriere, **asteptat):
        r = rez.rezolva(text)
        ok = r.precizie_loc == precizie and all(getattr(r, k) == val for k, val in asteptat.items())
        v.cere(ok, descriere, f"{r.precizie_loc}/{r.metoda} in_iasi={r.in_iasi} ({r.lat}, {r.lon})")
        return r

    caz("trecerea din Nicolina", "vag", "„din Nicolina” rămâne zonă, nu gara Nicolina", lat=None)
    caz("intersecția din Copou", "vag", "„din Copou” rămâne zonă, nu stația Copou", lat=None)
    caz("intersecția din Tătărași", "vag", "„din Tătărași” rămâne zonă, nu restaurantul", lat=None)
    r = caz("trecerea de pe Alexandru cel Bun", "strada",
            "„de pe Alexandru cel Bun” = bulevardul (mai multe treceri → strada)")
    v.cere(any("Bulevardul Alexandru cel Bun" == c.get("nume") for c in r.candidati),
           "… și e Bulevardul, nu podul/cartierul")
    caz("pe Bulevardul Demo, în zona Podu Roș", "vag", "stradă inexistentă + zonă → vag", lat=None)
    caz("pe Bulevardul Socola", "strada", "stradă reală fără alt reper → strada", in_iasi=True)
    caz("pe Strada Arcu", "trecere" if False else "strada", "„pe Strada Arcu” → strada")
    r = caz("trecerea de pe Strada Arcu", "trecere",
            "singura trecere OSM de pe strada numită → trecere", in_iasi=True)
    caz("în comuna Tomești, pe strada principală", "vag",
        "stradă omonimă în mai multe sate → nu ghicim (vag)", in_iasi=False)
    caz("loc complet necunoscut fără nume", "vag", "fără nume → vag, in_iasi null", in_iasi=None)

    # intersecție prin nod comun, cu nume luate din index (nu din memorie)
    comps, _ = rez.index.strazi_dupa_nume("Bulevardul Independenței")
    if comps:
        perechi = [(a, b) for a in comps for b in comps]
        vecine = sorted({cid.split("#")[0] for n in comps[0].noduri
                         for cid in rez.index.nod_la_componente[n]} - {comps[0].cheie})
        gasit = False
        for cheie in vecine:
            alt = rez.index.strazi[cheie][0].nume
            if alt.startswith(("Pasajul", "Podul")):
                continue  # vrem o intersecție la nivel, nu un pasaj
            inter, _ = rez.index.intersectii(comps, rez.index.strazi[cheie])
            if len(inter) == 1:
                r = rez.rezolva(f"intersecția Bulevardului Independenței cu {alt}")
                v.cere(r.precizie_loc == "intersectie" and r.metoda == "nod_comun_osm",
                       f"intersecție reală prin nod comun ({alt})",
                       f"{r.precizie_loc}/{r.metoda} {r.avertismente}")
                gasit = True
                break
        v.cere(gasit, "există o pereche de test pentru nodul comun")
        _ = perechi

    # nod cunoscut: nevalidat → nefolosit; validat → intersecție
    nod_test = NodCunoscut(id="test", nume="Podu Roș", osm=None)
    for n in rez.noduri.noduri:
        if n.id == "podu-ros":
            nod_test = NodCunoscut(id="test", nume=n.nume, alias=n.alias, osm=n.osm)
    if nod_test.osm:
        rez_nev = Rezolvator(rez.index, rez.granita, NoduriCunoscute([nod_test]))
        r = rez_nev.rezolva("intersecția de la Podu Roș")
        v.cere(r.lat is None and "test" in r.noduri_neverificate,
               "nod cunoscut nevalidat NU e folosit, dar e semnalat")
        nod_test.verificat = True
        rez_ver = Rezolvator(rez.index, rez.granita, NoduriCunoscute([nod_test]))
        r = rez_ver.rezolva("intersecția de la Podu Roș")
        v.cere(r.precizie_loc == "intersectie" and r.metoda == "nod_cunoscut_verificat",
               "nod cunoscut validat → intersecție", f"{r.precizie_loc}/{r.metoda}")
        r = rez_ver.rezolva("în zona Podu Roș")
        v.cere(r.precizie_loc == "vag", "„în zona X” rămâne zonă chiar dacă X e nod cunoscut")


# ------------------------------------------------------------------ 3. mock


def _amprenta(director: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(director.glob("*")):
        if f.is_file():
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def verifica_mock(v: Verificari, rez: Rezolvator, cale: Path) -> None:
    print(f"[3] Datele mock ({cale})")
    inainte = _amprenta(config.DIR_PROTEJAT)
    evenimente = citeste_json(cale)
    rezultate, raport, _ = aplica(evenimente, rez, mod=MOD_TOATE, forteaza=True)
    pe_id = {e["event_id"]: e for e in rezultate}

    ev16 = pe_id.get("ev-016", {})
    v.cere(ev16.get("lat") is None and ev16.get("lon") is None and ev16.get("precizie_loc") == "vag",
           "ev-016 („în zona Gării”) rămâne fără coordonate, vag",
           f"{ev16.get('precizie_loc')} ({ev16.get('lat')}, {ev16.get('lon')})")
    ev17 = pe_id.get("ev-017", {})
    v.cere(ev17.get("in_iasi") is False, "ev-017 („Valea Lupului”) e în afara Iașiului",
           f"in_iasi={ev17.get('in_iasi')}")

    v.cere([e.get("event_id") for e in rezultate] == [e.get("event_id") for e in evenimente],
           "aceleași evenimente, în aceeași ordine")
    permise = {"lat", "lon", "precizie_loc", "in_iasi"}
    diferente = [f"{a.get('event_id')}.{k}" for a, b in zip(evenimente, rezultate)
                 for k in set(a) | set(b) if k not in permise and a.get(k) != b.get(k)]
    v.cere(not diferente, "se modifică numai lat/lon/precizie_loc/in_iasi", ", ".join(diferente[:5]))

    probleme = []
    for e in rezultate:
        p, lat, lon = e.get("precizie_loc"), e.get("lat"), e.get("lon")
        if p not in PRECIZII_API:
            probleme.append(f"{e['event_id']}: precizie {p!r}")
        if p == "vag" and (lat is not None or lon is not None):
            probleme.append(f"{e['event_id']}: vag cu coordonate")
        if p in config.PRECIZII_CU_COORDONATE and (lat is None or lon is None):
            probleme.append(f"{e['event_id']}: {p} fără coordonate")
        if (lat is None) != (lon is None):
            probleme.append(f"{e['event_id']}: coordonate pe jumătate")
        if lat is not None and not (isinstance(lat, float) and math.isfinite(lat)
                                    and 46.9 < lat < 47.4 and 27.2 < lon < 27.9):
            probleme.append(f"{e['event_id']}: coordonate în afara zonei / inversate")
        if e.get("in_iasi") is not None and type(e.get("in_iasi")) is not bool:
            probleme.append(f"{e['event_id']}: in_iasi nu e bool/null")
    v.cere(not probleme, "ieșirea trece regulile din api/validate_fixtures.py", "; ".join(probleme[:5]))

    contrazise = [e["event_id"] for e in rezultate if e.get("lat") is not None
                  and rez.granita.verifica(e["lat"], e["lon"]).in_iasi != e.get("in_iasi")]
    v.cere(not contrazise, "`in_iasi` consecvent cu granița", ", ".join(contrazise))

    try:
        scrie_json(config.DIR_PROTEJAT / "accidents.json", [])
        refuzat = False
    except ScriereInterzisa:
        refuzat = True
    v.cere(refuzat, "scrierea în false_data/ e refuzată")
    v.cere(_amprenta(config.DIR_PROTEJAT) == inainte, "fișierele mock au rămas identice")

    print(json.dumps(raport.statistici, ensure_ascii=False))


def ruleaza(cale: Path | None = None) -> int:
    v = Verificari()
    verifica_text(v)
    try:
        index = IndexOSM.incarca()
    except IndexLipsa as e:
        v.cere(False, "indexul OSM local există", str(e))
        return v.raporteaza()
    rez = Rezolvator(index, modul_granita.incarca(), NoduriCunoscute.incarca())
    verifica_osm(v, rez)
    cale = Path(cale or config.INTRARE_MOCK)
    if cale.exists():
        verifica_mock(v, rez, cale)
    else:
        v.cere(False, f"fișierul de intrare există ({cale})")
    print()
    return v.raporteaza()
