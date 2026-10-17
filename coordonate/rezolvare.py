"""Din `loc_text` în `lat`, `lon`, `precizie_loc`, `in_iasi` — doar din indexul OSM local.

Reguli, în ordine (prima care reușește câștigă):

1. `intersectie` — nod cunoscut **verificat** („intersecția de la Podu Roș”).
2. `intersectie` — cele două străzi numite au exact un **nod comun** în OSM.
3. `segment`     — stradă + număr confirmat de o adresă OSM.
4. `trecere`     — o trecere OSM identificabilă fără ambiguitate: singura de pe
                   strada numită, singura de pe stradă lângă reper, sau singura
                   în jurul unui reper.
5. `segment`     — stradă + reper („pe Bd. Socola, în dreptul Palas”): punctul
                   străzii cel mai apropiat de reper.
6. `segment`     — stație de transport numită („stația Târgu Cucului”): stația
                   e pe marginea drumului, deci punctul e precis.
7. `strada`      — reper întins (mall, școală, spital) fără stradă: punct
                   aproximativ, pe hartă, dar în afara clasamentului.
8. `strada`      — știm strada, nu și locul pe ea.
9. `vag`         — doar cartier/zonă/localitate: `lat`/`lon` rămân `null`, dar
                   `in_iasi` se stabilește din punctul zonei.
10. `vag`        — nimic găsit: `in_iasi` rămâne `null`.

Un nume care e cartier în OSM („din Nicolina”, „din Copou”) rămâne zonă, chiar
dacă există și o gară sau o stație cu același nume, cu excepția cazului în care
textul spune explicit „gara”, „stația” etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config, parser_loc
from .geometrie import Punct, distanta_m
from .granita import Granita
from .index_osm import (
    POTRIVIRE_BAZA, POTRIVIRE_CUVINTE, POTRIVIRE_EXACTA, Componenta, IndexOSM, Obiect,
)
from .noduri import NoduriCunoscute
from .normalizare import alias_reper

INCREDERE_RIDICATA = "ridicata"
INCREDERE_MEDIE = "medie"
INCREDERE_SCAZUTA = "scazuta"

TIPURI_LOCALITATE = {"city", "town", "village", "hamlet", "isolated_dwelling", "municipality"}
TIPURI_ZONA = {"suburb", "quarter", "neighbourhood", "locality", "city_block", "square"}
RAZA_LOCALITATE_M = 3000.0
RAZA_GRUP_REPERE_M = 400.0


@dataclass
class Rezultat:
    """Ce scriem în `accidents.json` plus ce păstrăm pentru verificare."""

    loc_text: str
    lat: float | None = None
    lon: float | None = None
    precizie_loc: str = "vag"
    in_iasi: bool | None = None
    metoda: str = "nerezolvat"
    incredere: str = INCREDERE_SCAZUTA
    punct_orientativ: Punct | None = None
    unitate_admin: str | None = None
    referinte_osm: list[str] = field(default_factory=list)
    avertismente: list[str] = field(default_factory=list)
    de_verificat: list[str] = field(default_factory=list)
    noduri_neverificate: list[str] = field(default_factory=list)
    intentie: dict = field(default_factory=dict)
    candidati: list[dict] = field(default_factory=list)

    def ca_dict(self) -> dict:
        return {
            "loc_text": self.loc_text,
            "lat": self.lat,
            "lon": self.lon,
            "precizie_loc": self.precizie_loc,
            "in_iasi": self.in_iasi,
            "metoda": self.metoda,
            "incredere": self.incredere,
            "punct_orientativ": (
                {"lat": self.punct_orientativ[0], "lon": self.punct_orientativ[1]}
                if self.punct_orientativ else None
            ),
            "unitate_admin": self.unitate_admin,
            "referinte_osm": self.referinte_osm,
            "avertismente": self.avertismente,
            "de_verificat": self.de_verificat,
            "noduri_neverificate": self.noduri_neverificate,
            "intentie": self.intentie,
            "candidati_osm": self.candidati,
        }


class Rezolvator:
    def __init__(self, index: IndexOSM, granita: Granita, noduri: NoduriCunoscute | None = None) -> None:
        self.index = index
        self.granita = granita
        self.noduri = noduri or NoduriCunoscute([])
        nume_mun = granita.municipiu.nume if granita.municipiu else config.ORAS
        self.nume_municipiu = nume_mun

    def statistici(self) -> dict:
        return {
            "sursa": "index OSM local (osmnx)",
            "index_descarcat_la": self.index.meta.get("descarcat_la"),
            "numere_index": self.index.meta.get("numere"),
            "cereri_retea": 0,
        }

    # ================================================================ flux

    def rezolva(self, loc_text: str | None) -> Rezultat:
        intentie = parser_loc.analizeaza(loc_text)
        rez = Rezultat(loc_text=intentie.text, intentie=intentie.ca_dict())
        if not intentie.text:
            rez.avertismente.append("loc_text gol (null de la extracție)")
            rez.de_verificat.append("fără text de localizare: de completat manual")
            return rez

        localitate = self._localitate_externa(intentie, rez)

        # 1. nod cunoscut („intersecția de la Podu Roș”, „trecerea de la ...”)
        if intentie.este_intersectie or intentie.este_trecere:
            for nume in intentie.la:
                gasit = self._nod_cunoscut(nume, rez)
                if gasit is not None:
                    return self._final(rez, gasit[0], "intersectie", "nod_cunoscut_verificat",
                                       INCREDERE_RIDICATA, gasit[1])

        # 2. intersecție prin nod comun
        for a, b in intentie.perechi:
            comps_a = self._strazi(a, localitate, rez, raporteaza=True)
            comps_b = self._strazi(b, localitate, rez, raporteaza=True)
            if not comps_a or not comps_b:
                continue
            intersectii, suprapuneri = self.index.intersectii(comps_a, comps_b)
            if len(intersectii) == 1:
                inter = intersectii[0]
                return self._final(rez, inter.punct, "intersectie", "nod_comun_osm",
                                   INCREDERE_RIDICATA, inter.referinta_osm)
            if len(intersectii) > 1:
                rez.de_verificat.append(
                    f"„{a}” și „{b}” se întâlnesc în {len(intersectii)} locuri: care anume?"
                )
            elif suprapuneri:
                rez.de_verificat.append(
                    f"„{a}” și „{b}” se suprapun doar în plan, fără nod comun: "
                    "posibil pasaj/pod, nu intersecție"
                )
            else:
                rez.avertismente.append(f"„{a}” și „{b}” nu se intersectează în OSM")

        # străzi, repere, zone
        strada = self._prima_strada(intentie, localitate, rez)
        reper = self._reper(intentie, localitate, rez)
        zona = self._zona(intentie, localitate, rez)

        # 3. stradă + număr
        if strada and intentie.numar:
            adresa = self.index.adresa(strada, intentie.numar)
            if adresa:
                return self._final(rez, adresa[0], "segment", "strada_si_numar_osm",
                                   INCREDERE_RIDICATA, adresa[1])
            rez.avertismente.append(f"numărul {intentie.numar} nu apare în adresele OSM")

        # 4. trecere fără ambiguitate
        if intentie.este_trecere:
            trecere = self._trecere(strada, reper, rez)
            if trecere is not None:
                obiect, metoda, incredere = trecere
                return self._final(rez, obiect.punct, "trecere", metoda, incredere, obiect.osm)

        # 5. stradă + reper
        if strada and reper:
            punct, dist = self.index.punct_pe_strada(strada, reper.punct)
            if dist <= config.RAZA_STRADA_LANGA_REPER:
                rez.de_verificat.append(
                    f"punctul de pe „{strada.nume}” cel mai apropiat de „{reper.nume}”"
                )
                return self._final(rez, punct, "segment", "strada_langa_reper",
                                   INCREDERE_MEDIE, strada.referinta_osm)
            rez.avertismente.append(
                f"„{reper.nume}” e la {dist:.0f} m de „{strada.nume}”: nu le combin"
            )

        # 6–7. doar reper
        if reper and not strada:
            if reper.este_statie:
                rez.de_verificat.append("punctul e stația din OSM; confirmați partea străzii")
                return self._final(rez, reper.punct, "segment", "statie_osm",
                                   INCREDERE_MEDIE, reper.osm)
            rez.de_verificat.append(
                f"reper întins („{reper.nume}”, {reper.clasa}={reper.tip}): punct aproximativ, "
                "nu intră în clasament"
            )
            return self._final(rez, reper.punct, "strada", "reper_osm", INCREDERE_MEDIE, reper.osm)

        # 8. doar stradă
        if strada:
            rez.de_verificat.append("se știe doar strada; locul pe stradă e neconfirmat")
            return self._final(rez, strada.punct, "strada", "strada_osm", INCREDERE_MEDIE,
                               strada.referinta_osm)

        # 9. zonă / localitate: fără coordonate
        zona_finala = zona or localitate
        if zona_finala is not None:
            rez.precizie_loc = "vag"
            rez.metoda = "zona_osm" if zona else "localitate_osm"
            rez.incredere = INCREDERE_SCAZUTA
            rez.punct_orientativ = zona_finala.punct
            verdict = self.granita.verifica(*zona_finala.punct)
            rez.in_iasi = verdict.in_iasi
            rez.unitate_admin = verdict.unitate
            rez.de_verificat.append(
                f"localizare doar la nivel de zonă („{zona_finala.nume}”): fără coordonate"
            )
            return rez

        # 10. nimic
        rez.de_verificat.append("localizare negăsită în indexul OSM: de completat manual")
        return rez

    # ================================================================ localitate

    def _localitate_externa(self, intentie, rez: Rezultat) -> Obiect | None:
        """O localitate numită în text, din afara municipiului („în Valea Lupului”)."""
        for nume in [*intentie.localitati, *intentie.din, *intentie.la]:
            for obiect, scor in self.index.locuri_dupa_nume(nume):
                if scor < POTRIVIRE_EXACTA or obiect.tip not in TIPURI_LOCALITATE:
                    continue
                verdict = self.granita.verifica(*obiect.punct)
                if verdict.in_iasi is False:
                    rez.avertismente.append(f"textul indică altă localitate: {obiect.nume}")
                    self._noteaza(rez, obiect)
                    return obiect
        return None

    # ================================================================ noduri cunoscute

    def _nod_cunoscut(self, nume: str, rez: Rezultat) -> tuple[Punct, str] | None:
        nod = self.noduri.gaseste(nume)
        if nod is None or not nod.osm:
            return None
        if not nod.verificat:
            rez.noduri_neverificate.append(nod.id)
            rez.de_verificat.append(
                f"„{nume}” e în lista de noduri cunoscute, dar nevalidat încă "
                "(python -m coordonate noduri)"
            )
            return None
        punct = self.index.punct_osm(nod.osm)
        if punct is None:
            rez.avertismente.append(f"nodul cunoscut {nod.osm} lipsește din indexul OSM")
            return None
        rez.candidati.append({"nod_cunoscut": nod.id, "osm": nod.osm, "strazi": nod.strazi_osm})
        return punct, nod.osm

    # ================================================================ străzi

    def _prima_strada(self, intentie, localitate, rez: Rezultat) -> Componenta | None:
        # „Strada X” și „pe X” se caută ca străzi. „din X”/„la X” doar dacă X nu e zonă.
        nume_zone = [n for n in [*intentie.din, *intentie.la] if not self._e_zona(n)]
        for nume in [*intentie.strazi, *intentie.pe, *nume_zone]:
            comps = self._strazi(nume, localitate, rez, raporteaza=nume in intentie.strazi)
            comp = self._alege_componenta(nume, comps, rez)
            if comp is not None:
                self._noteaza_strada(rez, comp)
                return comp
        return None

    def _strazi(self, nume: str, localitate, rez: Rezultat, *, raporteaza: bool) -> list[Componenta]:
        comps, potrivire = self.index.strazi_dupa_nume(nume)
        if not comps:
            if raporteaza:
                rez.avertismente.append(f"strada negăsită în OSM: „{nume}”")
            return []
        if potrivire == POTRIVIRE_CUVINTE:
            rez.avertismente.append(
                f"„{nume}” potrivit doar pe cuvinte cu „{comps[0].nume}”"
            )
        elif potrivire == POTRIVIRE_BAZA and comps[0].nume.split()[0] != nume.split()[0]:
            rez.avertismente.append(f"„{nume}” potrivit fără prefix cu „{comps[0].nume}”")

        if localitate is not None:
            aproape = [c for c in comps
                       if distanta_m(c.punct, localitate.punct) <= RAZA_LOCALITATE_M]
            return aproape
        in_municipiu = [c for c in comps if c.unitate == self.nume_municipiu]
        if in_municipiu:
            return in_municipiu
        if comps:
            rez.avertismente.append(
                f"„{nume}” există doar în afara municipiului ({comps[0].unitate})"
            )
        return comps

    def _alege_componenta(self, nume: str, comps: list[Componenta], rez: Rezultat) -> Componenta | None:
        if not comps:
            return None
        if len(comps) == 1:
            return comps[0]
        # bucăți ale aceleiași străzi (despărțite de o piață) sau străzi omonime?
        departe = max(distanta_m(a.punct, b.punct) for a in comps for b in comps)
        if departe <= config.RAZA_AMBIGUITATE_STRADA:
            return max(comps, key=lambda c: len(c.segmente))
        rez.de_verificat.append(
            f"„{nume}” corespunde mai multor străzi OSM: "
            + "; ".join(f"{c.nume} ({c.unitate or '?'})" for c in comps[:4])
        )
        return None

    def _e_zona(self, nume: str) -> bool:
        return any(
            scor >= POTRIVIRE_EXACTA and obiect.tip in TIPURI_ZONA | TIPURI_LOCALITATE
            for obiect, scor in self.index.locuri_dupa_nume(nume)
        )

    # ================================================================ repere

    def _reper(self, intentie, localitate, rez: Rezultat) -> Obiect | None:
        cereri: list[tuple[str, tuple]] = [(p.nume, p.clase) for p in intentie.poi if p.nume]
        cereri += [(n, ()) for n in intentie.repere]
        for nume, clase in cereri:
            cautat = alias_reper(nume)
            candidati = [
                (o, s) for o, s in self.index.poi_dupa_nume(cautat)
                if not clase or any(o.clasa == c and (t is None or o.tip == t) for c, t in clase)
            ]
            if not clase:
                # fără cuvânt-cheie: doar potriviri pe nume întreg sau pe toate cuvintele
                candidati = [(o, s) for o, s in candidati if s >= POTRIVIRE_CUVINTE]
            candidati = self._in_zona_de_interes(candidati, localitate)
            if not candidati:
                rez.avertismente.append(f"reper negăsit în OSM: „{nume}”")
                continue
            scor_max = candidati[0][1]
            cei_mai_buni = [o for o, s in candidati if s == scor_max]
            departe = max(distanta_m(a.punct, b.punct) for a in cei_mai_buni for b in cei_mai_buni)
            if departe > RAZA_GRUP_REPERE_M:
                rez.de_verificat.append(
                    f"„{nume}” corespunde mai multor repere OSM, la {departe:.0f} m distanță: "
                    + "; ".join(f"{o.nume} ({o.clasa}={o.tip})" for o in cei_mai_buni[:4])
                )
                continue
            ales = cei_mai_buni[0]
            if cautat != nume:
                rez.avertismente.append(f"„{nume}” interpretat ca „{cautat}” (alias confirmat)")
            self._noteaza(rez, ales)
            return ales
        return None

    def _in_zona_de_interes(self, candidati, localitate):
        if localitate is not None:
            return [(o, s) for o, s in candidati
                    if distanta_m(o.punct, localitate.punct) <= RAZA_LOCALITATE_M]
        in_mun = [(o, s) for o, s in candidati if self.granita.verifica(*o.punct).in_iasi]
        return in_mun or candidati

    # ================================================================ zone

    def _zona(self, intentie, localitate, rez: Rezultat) -> Obiect | None:
        for nume in [*intentie.zone, *intentie.din, *intentie.la, *intentie.pe]:
            candidati = [
                (o, s) for o, s in self.index.locuri_dupa_nume(nume)
                if s >= POTRIVIRE_EXACTA or (s >= POTRIVIRE_CUVINTE and nume in intentie.zone)
            ]
            candidati = self._in_zona_de_interes(candidati, localitate)
            if candidati:
                # zonele înaintea localităților („Păcurari” cartier, nu sat)
                candidati.sort(key=lambda x: (x[0].tip not in TIPURI_ZONA, -x[1]))
                ales = candidati[0][0]
                self._noteaza(rez, ales)
                return ales
        return None

    # ================================================================ treceri

    def _trecere(self, strada, reper, rez: Rezultat):
        if strada is not None:
            pe_strada = self.index.treceri_pe(strada)
            if len(pe_strada) == 1:
                return pe_strada[0], "trecere_unica_pe_strada", INCREDERE_RIDICATA
            if reper is not None and pe_strada:
                aproape = [t for t in pe_strada
                           if distanta_m(t.punct, reper.punct) <= config.RAZA_STRADA_LANGA_REPER]
                if len(aproape) == 1:
                    rez.de_verificat.append(
                        f"singura trecere de pe „{strada.nume}” în "
                        f"{config.RAZA_STRADA_LANGA_REPER:.0f} m de „{reper.nume}”"
                    )
                    return aproape[0], "trecere_pe_strada_langa_reper", INCREDERE_MEDIE
                if len(aproape) > 1:
                    rez.de_verificat.append(
                        f"{len(aproape)} treceri pe „{strada.nume}” lângă „{reper.nume}”: care anume?"
                    )
                    return None
            if len(pe_strada) > 1:
                rez.de_verificat.append(f"{len(pe_strada)} treceri pe „{strada.nume}”: care anume?")
            elif not pe_strada:
                rez.de_verificat.append(f"nicio trecere OSM pe „{strada.nume}”")
            return None
        if reper is not None:
            in_jur = self.index.treceri_in_jur(reper.punct, config.RAZA_TRECERE_LANGA_REPER)
            if len(in_jur) == 1:
                rez.de_verificat.append(
                    f"singura trecere OSM în {config.RAZA_TRECERE_LANGA_REPER:.0f} m de „{reper.nume}”"
                )
                return in_jur[0], "trecere_unica_langa_reper", INCREDERE_MEDIE
            if len(in_jur) > 1:
                rez.de_verificat.append(f"{len(in_jur)} treceri în jurul „{reper.nume}”: care anume?")
        return None

    # ================================================================ final

    def _noteaza(self, rez: Rezultat, obiect: Obiect) -> None:
        if obiect.osm not in rez.referinte_osm:
            rez.referinte_osm.append(obiect.osm)
        rez.candidati.append(obiect.ca_dict())

    def _noteaza_strada(self, rez: Rezultat, comp: Componenta) -> None:
        if comp.referinta_osm not in rez.referinte_osm:
            rez.referinte_osm.append(comp.referinta_osm)
        rez.candidati.append({
            "osm": comp.referinta_osm, "nume": comp.nume, "fel": "strada",
            "highway": comp.highway, "unitate": comp.unitate,
            "lat": comp.punct[0], "lon": comp.punct[1],
        })

    def _final(self, rez: Rezultat, punct: Punct, precizie: str, metoda: str,
               incredere: str, referinta: str | None) -> Rezultat:
        rez.lat = round(punct[0], 6)
        rez.lon = round(punct[1], 6)
        rez.precizie_loc = precizie
        rez.metoda = metoda
        rez.incredere = incredere
        rez.punct_orientativ = punct
        if referinta and referinta not in rez.referinte_osm:
            rez.referinte_osm.insert(0, referinta)
        verdict = self.granita.verifica(rez.lat, rez.lon)
        rez.in_iasi = verdict.in_iasi
        rez.unitate_admin = verdict.unitate
        if verdict.in_iasi is False:
            rez.de_verificat.append(
                f"punct în afara municipiului ({verdict.unitate or 'necunoscut'}): "
                "nu intră în clasament"
            )
        if verdict.in_iasi is None:
            rez.avertismente.append("granița municipiului lipsește: in_iasi necunoscut")
        return rez
