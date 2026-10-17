"""Citirea intenției din `loc_text` (primit de la persoana 2, nemodificat).

Nu decidem aici coordonate și nici precizia finală. Extragem doar ce *spune*
textul și cu ce rol, după prepoziție:

- „pe X”, „de pe X”          -> `pe`: se caută întâi ca stradă;
- „din X”, „de la X”, „în X” -> `din`: se caută întâi ca zonă/localitate;
- „zona X”, „cartierul X”    -> `zone`: rămâne zonă (precizie `vag`);
- „stația X”, „Spitalul X”   -> `poi`: reper explicit, căutat ca punct de interes;
- „în dreptul X”, „lângă X”  -> `repere`;
- „Strada X”, „Bd. X”        -> `strazi`: stradă cu prefix explicit;
- „comuna X”, „satul X”      -> `localitati`.

Rezolvarea și precizia vin din ce confirmă indexul OSM (`rezolvare.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalizare import curata, fara_diacritice, normalizeaza_strada

# ------------------------------------------------------------------ vocabular

_MAJ = "A-ZĂÂÎȘȚŞŢ"
_CUV_MARE = rf"(?:\d+\s+)?[{_MAJ}][\w’'\.\-]*"
_LEGATURA = r"(?:de|cel|cea|lui|din|și|si|al|a|la)"
# Nume propriu: începe cu majusculă; legăturile mici sunt acceptate doar dacă
# urmează din nou o majusculă („Alexandru cel Bun”, „Moara de Vânt”), ca să nu
# înghițim restul frazei („Arcu a implicat doar...”).
NUME = rf"{_CUV_MARE}(?:\s+{_LEGATURA}\s+{_CUV_MARE}|\s+{_CUV_MARE}|\s+\d+){{0,5}}"
# După un prefix explicit de stradă acceptăm și primul cuvânt cu literă mică
# („pe strada principală”).
NUME_DUPA_PREFIX = rf"(?:{NUME}|(?!(?:spre|către|catre|de|din|la|pe|cu|și|si)\b)[a-zăâîșț][\w’'\-]+(?:\s+{_CUV_MARE})*)"

# Formele lungi înaintea celor scurte („bulevardului” înainte de „bulevardul”),
# iar după prefix nu poate urma o literă (altfel „Bulevardului” = „Bulevardul”+„ui”).
PREFIX_STRADA = (
    r"(?i:(?:str[ăa]zilor|str[ăa]zii|stradela|strada|str\.|str|"
    r"bulevardului|bulevardul|b-dul|bdul\.?|bd\.|bd|blvd\.?|"
    r"[șşs]oselei|[șşs]oseaua|[șşs]os\.|c[ăa]ii|calea|aleii|aleea|pie[țţt]ei|pia[țţt]a|p-[țţt]a|"
    r"splaiul|intrarea|drumul|pasajul|podul|fundacul)(?![a-zăâîșțşţ]))"
)

# cuvânt-cheie de reper -> clase OSM acceptate (clasa, tip) ; tip None = orice
CUVINTE_POI: dict[str, tuple[tuple[str, str | None], ...]] = {
    "gara": (("railway", "station"), ("railway", "halt"), ("amenity", "bus_station"), ("public_transport", "station")),
    "garii": (("railway", "station"), ("railway", "halt"), ("amenity", "bus_station"), ("public_transport", "station")),
    "autogara": (("amenity", "bus_station"),),
    "statia": (("highway", "bus_stop"), ("railway", "tram_stop"), ("public_transport", None), ("railway", "halt")),
    "statiei": (("highway", "bus_stop"), ("railway", "tram_stop"), ("public_transport", None), ("railway", "halt")),
    "scoala": (("amenity", "school"),),
    "scolii": (("amenity", "school"),),
    "liceul": (("amenity", "school"), ("amenity", "college")),
    "liceului": (("amenity", "school"), ("amenity", "college")),
    "colegiul": (("amenity", "school"), ("amenity", "college")),
    "colegiului": (("amenity", "school"), ("amenity", "college")),
    "gradinita": (("amenity", "kindergarten"),),
    "gradinitei": (("amenity", "kindergarten"),),
    "spitalul": (("amenity", "hospital"), ("amenity", "clinic"), ("healthcare", None)),
    "spitalului": (("amenity", "hospital"), ("amenity", "clinic"), ("healthcare", None)),
    "universitatea": (("amenity", "university"), ("amenity", "college")),
    "universitatii": (("amenity", "university"), ("amenity", "college")),
    "mall": (("shop", "mall"), ("shop", None)),
    "mall-ul": (("shop", "mall"), ("shop", None)),
    "mallul": (("shop", "mall"), ("shop", None)),
    "magazinul": (("shop", None),),
    "supermarketul": (("shop", None),),
    "hipermarketul": (("shop", None),),
    "biserica": (("amenity", "place_of_worship"),),
    "bisericii": (("amenity", "place_of_worship"),),
    "catedrala": (("amenity", "place_of_worship"),),
    "catedralei": (("amenity", "place_of_worship"),),
    "parcul": (("leisure", "park"), ("leisure", None)),
    "parcului": (("leisure", "park"), ("leisure", None)),
    "teatrul": (("amenity", "theatre"),),
    "teatrului": (("amenity", "theatre"),),
    "hotelul": (("tourism", "hotel"), ("tourism", None)),
    "hotelului": (("tourism", "hotel"), ("tourism", None)),
    "benzinaria": (("amenity", "fuel"),),
    "benzinariei": (("amenity", "fuel"),),
    "primaria": (("amenity", "townhall"), ("office", None)),
    "primariei": (("amenity", "townhall"), ("office", None)),
    "stadionul": (("leisure", "stadium"), ("leisure", None)),
    "stadionului": (("leisure", "stadium"), ("leisure", None)),
}
_RE_CUV_POI = (
    r"(?i:gara|g[ăa]rii|autogara|sta[țţt]ia|sta[țţt]iei|[șşs]coala|[șşs]colii|liceul|liceului|"
    r"colegiul|colegiului|gr[ăa]dini[țţt]a|gr[ăa]dini[țţt]ei|spitalul|spitalului|"
    r"universitatea|universit[ăa][țţt]ii|mall-ul|mallul|mall|magazinul|supermarketul|"
    r"hipermarketul|biserica|bisericii|catedrala|catedralei|parcul|parcului|teatrul|"
    r"teatrului|hotelul|hotelului|benzin[ăa]ria|benzin[ăa]riei|prim[ăa]ria|prim[ăa]riei|"
    r"stadionul|stadionului)"
)

RE_STRADA = re.compile(rf"\b(?P<prefix>{PREFIX_STRADA})\s*(?P<nume>{NUME_DUPA_PREFIX})")
RE_POI = re.compile(rf"\b(?P<cuv>{_RE_CUV_POI})\s+(?P<nume>{NUME})")
RE_POI_GENERIC = re.compile(rf"\b(?P<cuv>{_RE_CUV_POI})\b")
RE_ZONA = re.compile(
    rf"(?i:\b(?:[îi]n\s+)?(?:zona|cartierul|cartier|perimetrul))\s+(?P<nume>{NUME})"
)
RE_REPER = re.compile(
    rf"(?i:\b(?:[îi]n\s+dreptul|[îi]n\s+fa[țţt]a|[îi]n\s+apropierea|l[âa]ng[ăa]|vizavi\s+de|"
    rf"peste\s+drum\s+de|[îi]n\s+spatele|la\s+intrarea\s+[îi]n))\s+(?!{_RE_CUV_POI}\b)(?P<nume>{NUME})"
)
RE_LOCALITATE = re.compile(
    rf"(?i:\b(?:comuna|satul|ora[șşs]ul|localitatea|municipiul))\s+(?P<nume>{NUME})"
)
RE_PE = re.compile(rf"(?i:\b(?:de\s+pe|pe))\s+(?P<nume>{NUME})")
RE_LA = re.compile(rf"(?i:\b(?:de\s+la|la))\s+(?P<nume>{NUME})")
RE_DIN = re.compile(
    rf"(?i:\b(?:din\s+zona|din|[îi]n|spre|dinspre|c[ăa]tre))\s+(?P<nume>{NUME})"
)

RE_TRECERE = re.compile(
    r"(?i:\btrecer(?:e|ea|ii|i|ile)\b|\bzebr[ăa]\b)",
)
RE_INTERSECTIE = re.compile(
    r"(?i:\bintersec[țţt]i(?:a|e|ei|ile)\b|\bcol[țţt]ul\b|\bgiratori|\brond(?:ul)?\b)",
)

_LEGATURI_PERECHE = r"(?:\s+cu\s+|\s+[șşs]i\s+|\s*[×]\s*|\s+x\s+|\s*[–—]\s*|\s*/\s*)"
RE_PERECHE = [
    re.compile(
        rf"(?i:intersec[țţt]i\w*)\s+(?:(?i:de\s+la|dintre|din)\s+)?(?P<a>[^,;.]{{3,70}}?)"
        rf"{_LEGATURI_PERECHE}(?P<b>[^,;]{{3,70}}?)(?=[,;]|$)",
    ),
    re.compile(
        rf"(?i:col[țţt]ul)\s+(?P<a>[^,;.]{{3,70}}?){_LEGATURI_PERECHE}(?P<b>[^,;]{{3,70}}?)(?=[,;]|$)",
    ),
    re.compile(
        rf"(?P<a>[^,;]{{3,70}}?)\s*,?\s*(?i:la\s+intersec[țţt]ia\s+cu)\s+(?P<b>[^,;]{{3,70}}?)(?=[,;]|$)",
    ),
]
# Doar începutul membrului: „Moara de Vânt, lângă...” -> „Moara de Vânt”.
# Cuvânt cu literă mică doar după un prefix explicit („strada principală”),
# altfel „drumul spre Iași” ar deveni strada „Drumul”.
RE_MEMBRU = re.compile(
    rf"^(?:(?P<prefix>{PREFIX_STRADA})\s*(?P<nume_p>{NUME_DUPA_PREFIX})|(?P<nume>{NUME}))"
)

RE_NUMAR = re.compile(r"(?i:\bnr\.?\s*(?P<numar>\d+[A-Za-z]?)\b|\bnum[ăa]rul\s+(?P<numar2>\d+[A-Za-z]?)\b)")

# Cuvinte care arată că un „nume” prins de regex nu e un toponim.
STOP_NUME = {
    "politia", "spitalul", "victima", "victimei", "serviciul", "ambulanta", "smurd", "ipj",
    "municipiul", "judetul", "romania", "sensul", "sens", "directia", "locul", "fata", "data",
    "ora", "ieri", "azi", "aseara", "noaptea", "dimineata", "seara", "luni", "marti", "miercuri",
    "joi", "vineri", "sambata", "duminica", "un", "o", "acesta", "aceasta", "evenimentul",
    "accidentul", "soferul", "pietonul", "pietona", "barbatul", "femeia", "copilul",
}
# Nume de oraș care nu localizează nimic în plus („în Iași”).
NUME_ORAS = {"iasi", "municipiul iasi", "orasul iasi"}


def _nume_valid(nume: str) -> bool:
    nume = curata(nume)
    if len(nume) < 3:
        return False
    prim = fara_diacritice(nume.split()[0]).lower().strip(".")
    return prim not in STOP_NUME and fara_diacritice(nume).lower() not in NUME_ORAS


def cheie_cuvant_poi(cuv: str) -> str:
    return fara_diacritice(cuv).lower()


# ------------------------------------------------------------------ rezultat


@dataclass
class ReperExplicit:
    cuvant: str            # „statia”, „spitalul” (fără diacritice)
    nume: str | None       # „Târgu Cucului” sau None („lângă stație”)

    @property
    def clase(self) -> tuple[tuple[str, str | None], ...]:
        return CUVINTE_POI.get(self.cuvant, ())


@dataclass
class Intentie:
    """Ce am înțeles din text, înainte de orice căutare în OSM."""

    text: str
    este_trecere: bool = False
    este_intersectie: bool = False
    strazi: list[str] = field(default_factory=list)
    pe: list[str] = field(default_factory=list)
    la: list[str] = field(default_factory=list)
    din: list[str] = field(default_factory=list)
    zone: list[str] = field(default_factory=list)
    repere: list[str] = field(default_factory=list)
    poi: list[ReperExplicit] = field(default_factory=list)
    poi_generic: list[str] = field(default_factory=list)
    localitati: list[str] = field(default_factory=list)
    perechi: list[tuple[str, str]] = field(default_factory=list)
    numar: str | None = None
    semnale: list[str] = field(default_factory=list)

    def ca_dict(self) -> dict:
        return {
            "este_trecere": self.este_trecere,
            "este_intersectie": self.este_intersectie,
            "strazi": self.strazi,
            "pe": self.pe,
            "la": self.la,
            "din": self.din,
            "zone": self.zone,
            "repere": self.repere,
            "poi": [{"cuvant": p.cuvant, "nume": p.nume} for p in self.poi],
            "poi_generic": self.poi_generic,
            "localitati": self.localitati,
            "perechi": [list(p) for p in self.perechi],
            "numar": self.numar,
            "semnale": self.semnale,
        }


def _adauga(lista: list[str], valoare: str) -> None:
    valoare = curata(valoare)
    if not valoare:
        return
    cheie = fara_diacritice(valoare).lower()
    if all(fara_diacritice(v).lower() != cheie for v in lista):
        lista.append(valoare)


class _Ocupat:
    """Intervalele de text deja atribuite unui rol."""

    def __init__(self) -> None:
        self.intervale: list[tuple[int, int]] = []

    def contine(self, span: tuple[int, int]) -> bool:
        return any(span[0] < b and a < span[1] for a, b in self.intervale)

    def adauga(self, span: tuple[int, int]) -> None:
        self.intervale.append(span)


def analizeaza(loc_text: str | None) -> Intentie:
    text = curata(loc_text)
    intentie = Intentie(text=text)
    if not text:
        intentie.semnale.append("text_gol")
        return intentie

    intentie.este_trecere = bool(RE_TRECERE.search(text))
    intentie.este_intersectie = bool(RE_INTERSECTIE.search(text))

    m_numar = RE_NUMAR.search(text)
    if m_numar:
        intentie.numar = (m_numar.group("numar") or m_numar.group("numar2")).upper()

    ocupat = _Ocupat()

    # 1. străzi cu prefix explicit
    for m in RE_STRADA.finditer(text):
        if _nume_valid(m.group("nume")):
            _adauga(intentie.strazi, normalizeaza_strada(f"{m.group('prefix')} {m.group('nume')}"))
            ocupat.adauga(m.span())

    # 2. zonele întâi: „în zona Gării” e o zonă, nu gara
    for m in RE_ZONA.finditer(text):
        if ocupat.contine(m.span("nume")) or not _nume_valid(m.group("nume")):
            continue
        _adauga(intentie.zone, normalizeaza_strada(m.group("nume")))
        ocupat.adauga(m.span("nume"))

    # 3. repere explicite („stația Târgu Cucului”)
    for m in RE_POI.finditer(text):
        if ocupat.contine(m.span("nume")) or not _nume_valid(m.group("nume")):
            continue
        intentie.poi.append(ReperExplicit(cheie_cuvant_poi(m.group("cuv")), curata(m.group("nume"))))
        ocupat.adauga(m.span())
    for m in RE_POI_GENERIC.finditer(text):
        if not ocupat.contine(m.span()):
            _adauga(intentie.poi_generic, cheie_cuvant_poi(m.group("cuv")))

    # 4. localități explicite și repere
    for regex, lista in ((RE_LOCALITATE, intentie.localitati), (RE_REPER, intentie.repere)):
        for m in regex.finditer(text):
            if ocupat.contine(m.span("nume")) or not _nume_valid(m.group("nume")):
                continue
            _adauga(lista, normalizeaza_strada(m.group("nume")) if lista is not intentie.repere
                    else curata(m.group("nume")))
            ocupat.adauga(m.span("nume"))

    # 5. „pe X” (stradă întâi), „la X” (nod cunoscut întâi), „din X” (zonă întâi)
    for regex, lista in ((RE_PE, intentie.pe), (RE_LA, intentie.la), (RE_DIN, intentie.din)):
        for m in regex.finditer(text):
            if ocupat.contine(m.span("nume")) or not _nume_valid(m.group("nume")):
                continue
            _adauga(lista, normalizeaza_strada(m.group("nume")))
            ocupat.adauga(m.span("nume"))

    # 6. perechi de străzi pentru intersecții
    if intentie.este_intersectie:
        for re_pereche in RE_PERECHE:
            for m in re_pereche.finditer(text):
                a, b = _membru(m.group("a")), _membru(m.group("b"))
                if a and b:
                    intentie.perechi.append((a, b))
            if intentie.perechi:
                break

    if not (intentie.strazi or intentie.pe or intentie.poi or intentie.repere or intentie.perechi):
        intentie.semnale.append(
            "doar_zona" if (intentie.zone or intentie.din or intentie.la or intentie.localitati)
            else "fara_referinta_locativa"
        )
    return intentie


def _membru(text: str) -> str | None:
    """Un membru de intersecție curat („Strada X”, „Păcurari”) sau None."""
    text = curata(text)
    text = re.sub(
        r"^(?i:[îi]n|la|de\s+la|de\s+pe|pe|din|dintre|zona|cartierul)\s+", "", text
    )
    text = curata(text)
    m = RE_MEMBRU.match(text)
    if not m:
        return None
    prefix = m.group("prefix")
    nume = m.group("nume_p") if prefix else m.group("nume")
    if not nume or not _nume_valid(nume):
        return None
    return normalizeaza_strada(f"{prefix} {nume}" if prefix else nume)
