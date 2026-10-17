"""Normalizarea numelor de străzi și locuri, pentru căutarea în indexul OSM.

„Bd.”, „B-dul” și „Bulevardul” trebuie să ducă la aceeași cheie. Persoana 2
păstrează `loc_text` exact cum apare în articol (vezi `ai/engine.py`, `norm`),
deci normalizăm aici, la citire, fără să rescriem textul primit.
"""

from __future__ import annotations

import re
import unicodedata

# ------------------------------------------------------- diacritice și spații

_HARTA_DIACRITICE = str.maketrans(
    {
        "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
        "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T",
    }
)


def fara_diacritice(text: str) -> str:
    text = text.translate(_HARTA_DIACRITICE)
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def curata(text: str | None) -> str:
    """Spații colapsate, ghilimele și punctuație de margine eliminate."""
    if not text:
        return ""
    text = text.replace("\u00a0", " ").replace("„", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(" ,;:.-–—\"'()")


# ------------------------------------------------------- prefixe de stradă

# formă scurtă (fără diacritice, litere mici, fără punct) -> formă canonică
PREFIXE: dict[str, str] = {
    "str": "Strada", "strada": "Strada", "stradela": "Stradela",
    "bd": "Bulevardul", "bdul": "Bulevardul", "b-dul": "Bulevardul",
    "bulevard": "Bulevardul", "bulevardul": "Bulevardul", "blvd": "Bulevardul",
    "sos": "Șoseaua", "soseaua": "Șoseaua",
    "cal": "Calea", "calea": "Calea",
    # „al” lipsește intenționat: „Al. I. Cuza” e Alexandru, nu Aleea.
    "ale": "Aleea", "aleea": "Aleea",
    "pta": "Piața", "p-ta": "Piața", "piata": "Piața", "piateta": "Piațeta",
    "splai": "Splaiul", "splaiul": "Splaiul",
    # „Podu Roș”, „Podu Iloaiei” sunt nume proprii, nu „Podul” + nume.
    "drumul": "Drumul", "pasajul": "Pasajul", "podul": "Podul",
    "intrarea": "Intrarea", "intr": "Intrarea",
    "fundacul": "Fundacul", "trecatoarea": "Trecătoarea",
    # genitiv („intersecția străzii Sărărie cu...”)
    "strazii": "Strada", "bulevardului": "Bulevardul", "soselei": "Șoseaua",
    "caii": "Calea", "aleii": "Aleea", "pietei": "Piața",
}

# Abrevieri de nume proprii din presă. Doar text -> text, fără coordonate.
ALIAS_NUME: dict[str, str] = {
    "al i cuza": "Alexandru Ioan Cuza",
    "al ioan cuza": "Alexandru Ioan Cuza",
    "a i cuza": "Alexandru Ioan Cuza",
    "t vladimirescu": "Tudor Vladimirescu",
    "m costachescu": "Mihai Costăchescu",
    "n iorga": "Nicolae Iorga",
    "v lupu": "Vasile Lupu",
    "m eminescu": "Mihai Eminescu",
    "i creanga": "Ion Creangă",
}


# Sensul cel mai des întâlnit al unui reper scurt (confirmat de echipă).
# Se aplică doar la căutarea reperelor, nu și a străzilor.
ALIAS_REPERE: dict[str, str] = {}


def alias_reper(nume: str) -> str:
    """„Palas” -> „Palas Mall”, dacă echipa a confirmat sensul."""
    return ALIAS_REPERE.get(_cheie_simpla(nume.replace(".", " ")), nume)


def _incarca_alias_extern() -> None:
    """Alias-uri suplimentare din `date_referinta/alias_nume.json`, dacă există."""
    import json

    from . import config

    cale = config.FISIER_ALIAS
    if not cale.exists():
        return
    try:
        with cale.open("r", encoding="utf-8") as f:
            extern = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    for cheie, valoare in (extern.get("alias_nume") or {}).items():
        ALIAS_NUME[_cheie_simpla(str(cheie))] = str(valoare)
    for cheie, valoare in (extern.get("repere") or {}).items():
        ALIAS_REPERE[_cheie_simpla(str(cheie))] = str(valoare)
    for cheie, valoare in (extern.get("prefixe") or {}).items():
        PREFIXE[_cheie_simpla(str(cheie))] = str(valoare)


def _cheie_simpla(text: str) -> str:
    text = re.sub(r"[^a-z0-9\- ]", " ", fara_diacritice(text).lower())
    return re.sub(r"\s+", " ", text).strip()


_RE_PREFIX = re.compile(r"^\s*(?P<prefix>[A-Za-zĂÂÎȘȚăâîșț\-]{2,12})\s*\.?\s*(?=\S)")


def desparte_prefix(text: str) -> tuple[str | None, str]:
    """Separă prefixul de tip stradă de numele propriu-zis."""
    text = curata(text)
    m = _RE_PREFIX.match(text)
    if not m:
        return None, text
    cheie = fara_diacritice(m.group("prefix")).lower().strip(".")
    rest = curata(text[m.end():])
    if cheie in PREFIXE and rest:
        return PREFIXE[cheie], rest
    return None, text


_CUVINTE_MICI = {"de", "cel", "cea", "cei", "lui", "din", "și", "si", "al", "a", "la", "pe", "cu"}


def _capitalizeaza(nume: str) -> str:
    """Majuscule doar dacă textul a venit integral cu litere mici."""
    if any(c.isupper() for c in nume):
        return nume
    return " ".join(
        c if i > 0 and c in _CUVINTE_MICI else (c[:1].upper() + c[1:])
        for i, c in enumerate(nume.split())
    )


def normalizeaza_nume(nume: str) -> str:
    """Aplică alias-urile de nume propriu, dacă există."""
    cheie = _cheie_simpla(nume.replace(".", " "))
    if cheie in ALIAS_NUME:
        return ALIAS_NUME[cheie]
    return _capitalizeaza(curata(nume))


def normalizeaza_strada(text: str) -> str:
    """„Bd. Demo” / „B-dul Demo” / „bulevardul demo” -> „Bulevardul Demo”."""
    prefix, nume = desparte_prefix(text)
    nume = normalizeaza_nume(nume)
    if not nume:
        return curata(text)
    return f"{prefix} {nume}" if prefix else nume


# ------------------------------------------------------- chei de căutare


def cheie_nume(text: str) -> str:
    """Cheia completă: prefix canonic + nume, fără diacritice, litere mici.

    „B-dul Carol I” -> „bulevardul carol i”; „Str. Gării” -> „strada garii”.
    """
    prefix, nume = desparte_prefix(text)
    nume = normalizeaza_nume(nume)
    baza = f"{prefix} {nume}" if prefix else nume
    baza = re.sub(r"[^a-z0-9]+", " ", fara_diacritice(baza).lower())
    return re.sub(r"\s+", " ", baza).strip()


def cheie_baza(text: str) -> str:
    """Cheia fără prefixul de tip stradă: „Bulevardul Socola” -> „socola”."""
    _, nume = desparte_prefix(text)
    return cheie_nume(nume) if nume else cheie_nume(text)


def cuvinte(text: str) -> set[str]:
    return set(cheie_nume(text).split())


def prefix_canonic(text: str) -> str | None:
    return desparte_prefix(text)[0]


# Genitiv -> nominativ, doar pentru căutarea de cartiere/repere („zona Gării”).
# Străzile din OSM au deja forma de genitiv („Bulevardul Independenței”), deci
# pentru ele nu folosim aceste variante.
_GENITIV = (
    (r"arii$", "ara"),
    (r"atii$", "atea"),
    (r"itii$", "itatea"),
    (r"iei$", "ia"),
    (r"ei$", "a"),
    (r"ului$", "ul"),
    (r"ului$", ""),
)


def variante_nominativ(text: str) -> list[str]:
    """Forme de nominativ pentru ultimul cuvânt al unui nume, ca chei."""
    cheie = cheie_nume(text)
    if not cheie:
        return []
    bucati = cheie.split()
    ultim = bucati[-1]
    variante: list[str] = []
    for model, inlocuire in _GENITIV:
        if re.search(model, ultim):
            nou = re.sub(model, inlocuire, ultim)
            if nou and nou != ultim:
                v = " ".join(bucati[:-1] + [nou])
                if v not in variante:
                    variante.append(v)
    return variante


_incarca_alias_extern()
