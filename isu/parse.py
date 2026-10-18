"""Rule-based reading of one ISU release. No LLM: the releases follow a few fixed templates.

Every field is taken from the release text or stays None. The quoted passage that supports a field is
kept in `dovezi`, so a reader can check it against the PDF.
"""
from __future__ import annotations

import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
     "septembrie", "octombrie", "noiembrie", "decembrie"], 1)}

TITLE_NO = re.compile(r"SP[\s-]*nr\.?[\s-]*(\d+)[\s-]+din[\s-]+(\d{2})\.(\d{2})\.(\d{4})", re.I)
HEADER_DATE = re.compile(r"IA[ŞȘS]I,\s*(\d{2})\.\s?(\d{2})\.\s?(\d{4})")
HEADER_NO = re.compile(r"[ȘŞS]TIRE DE PRES[ĂA] NR\.?\s*(\d+)", re.I)

# The release body sits between the header and the safety advice, which mentions speed, alcohol etc.
# and must never be read as a cause or a participant.
BODY_START = re.compile(r"[ȘŞS]TIRE DE PRES[ĂA] NR\.?\s*\d+", re.I)
# The footer repeats the ISU address (Strada Lascăr Catargi), which must not be read as the crash site.
BODY_END = re.compile(r"Recomand[ăa]ri|Pentru prevenirea|Reamintim|Le recomand[ăa]m|recomand[ăa]m|Sfaturi|"
                      r"Cazul a r[ăa]mas|Personalul Inspectoratului|Compartimentul Informare|Strada Lasc[ăa]r Catargi,\s*nr", re.I)

BODY_CRASH = re.compile(r"accident\w*\s+rutier|accident\w* de circula|acro[șs]at|a fost lovit|lovit[ăa]? de|"
                        r"coliziune|în afara carosabilului|s-a r[ăa]sturnat|r[ăa]sturnat", re.I)
BODY_NOT_ROAD = re.compile(r"accident\w* (feroviar|aviatic|de muncă)|exerci[țt]iu|simulare", re.I)

NUM_DATE = re.compile(r"(?:în\s+)?(?:data|ziua|zilei)\s+de\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", re.I)
WORD_DATE = re.compile(r"(?:în\s+)?(?:data|ziua|zilei)\s+de\s+(\d{1,2})\s+([a-zăâîșț]+)\s*,?\s*(\d{4}|a\.\s?c\.)", re.I)
TIME = re.compile(r"\bora\s+(\d{1,2})[:.](\d{2})\b", re.I)

STREET_WORD = (r"(?i:strada|str\.|bulevardul|b-dul|bd\.|[șş]oseaua|[șş]os\.|calea|aleea|splaiul|pia[țt]a|podul|str[ăa]pungerea|"
               r"pasajul|sensul giratoriu|intersec[țt]ia|trecerea de pietoni|cartierul|zona)")
STREET = re.compile(rf"\b{STREET_WORD}\s+(?:din\s+)?(?i:str[ăa]zii\s+|dintre\s+)?(?:[A-ZĂÂÎȘŞȚŢ]\.\s?)*[A-ZĂÂÎȘŞȚŢ0-9„\"][^,.;:\n()]{{1,80}}")
ROAD = re.compile(r"\b(?:DN|DJ|DC|E)\s?\d{1,3}[A-Z]?\b")
PLACE = re.compile(r"\b(municipiul|ora[șş]ul|comuna|satul|sat|localitatea)\s+([A-ZĂÂÎȘŞȚŢ][\wăâîșşțţ-]*(?:[ -][A-ZĂÂÎȘŞȚŢ][\wăâîșşțţ-]*)*)")
CITY = re.compile(r"municipiul\s+Ia[șş]i|în\s+Ia[șş]i\b|din\s+Ia[șş]i\b|ora[șş]ul\s+Ia[șş]i", re.I)

VEHICLES = [
    ("pieton", r"\bpieton\w*"),
    ("biciclist", r"biciclet\w*|biciclist\w*"),
    ("trotineta", r"trotinet\w*"),
    ("motocicleta", r"motociclet\w*|motociclist\w*|moped\w*|scuter\w*"),
    ("tramvai", r"tramvai\w*"),
    ("autobuz", r"autobuz\w*|microbuz\w*"),
    ("camion", r"autocamion\w*|camion\w*|autotren\w*|\bTIR\b|cap tractor"),
    ("autoutilitara", r"autoutilitar\w*"),
    ("autoturism", r"autoturism\w*|ma[șş]in[ăia]\w*"),
]

DEATH = re.compile(r"decedat\w*|[șş]i-a pierdut via[țt]a|f[ăa]r[ăa] semne vitale|declarat\w* decesul|"
                   r"constatat\w* decesul|nu a mai putut fi salvat|mortal|au murit|a murit", re.I)
SERIOUS = re.compile(r"(?<![a-zăâîșț])(?:stare\s+grav[ăa]|r[ăa]ni\w*\s+grav|grav\s+r[ăa]nit\w*|inconștien\w*|"
                     r"in\s*con[șş]tien\w*|politraumat\w*|resuscit\w*|stop cardio)", re.I)
VICTIM = re.compile(r"victim[ăe]|persoan[ăe]\s+(?:r[ăa]nit|a necesitat|au necesitat|transportat)|"
                    r"îngrijiri medicale|transportat\w* la spital|a refuzat transportul|au refuzat transportul", re.I)
NO_VICTIM = re.compile(r"nu au (?:fost înregistrate|rezultat) victime|f[ăa]r[ăa] victime|nu s-au înregistrat victime|"
                       r"nu au fost victime", re.I)


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start)) + 1
    right = text.find(". ", end)
    return re.sub(r"\s+", " ", text[left:right if right != -1 else len(text)]).strip()[:300]


def release_meta(title: str, text: str) -> tuple[str | None, date | None]:
    """Number and date of the release. Title and PDF header each carry typos at times (18.11 for 18.01,
    a header left from an older release), so the later valid one is taken: a release is never dated
    before the event it reports."""
    t, n, d = TITLE_NO.search(title), HEADER_NO.search(text), HEADER_DATE.search(text)
    number = n.group(1) if n else (t.group(1) if t else None)
    dates = []
    for m, (y, mo, dd) in ((t, (4, 3, 2)), (d, (3, 2, 1))):
        if m:
            try:
                dates.append(date(int(m.group(y)), int(m.group(mo)), int(m.group(dd))))
            except ValueError:
                pass
    return number, max(dates) if dates else None


def body(text: str) -> str:
    m = BODY_START.search(text)
    text = text[m.end():] if m else text
    end = BODY_END.search(text)
    return re.sub(r"\s+", " ", text[:end.start()] if end else text).strip()


def event_date(text: str, released: date | None) -> tuple[str | None, str | None]:
    candidates = []
    for m in NUM_DATE.finditer(text):
        d, mo, y = map(int, m.groups())
        candidates.append((m, d, mo, y))
    for m in WORD_DATE.finditer(text):
        month = MONTHS.get(m.group(2).lower())
        if not month:
            continue
        year = m.group(3)
        # "a.c." = the current year of the release; ISU never uses it across New Year in the samples,
        # but a December event released in January would be wrong, so take the previous year then.
        if year.lower().startswith("a"):
            if not released:
                continue
            y = released.year - (1 if month > released.month else 0)
        else:
            y = int(year)
        candidates.append((m, int(m.group(1)), month, y))
    for m, d, mo, y in sorted(candidates, key=lambda c: c[0].start()):
        try:
            found = date(y, mo, d)
        except ValueError:
            continue
        # -1: a night event released with the previous day's header date.
        if released and not (-1 <= (released - found).days <= 40):
            continue
        return found.isoformat(), _sentence(text, m.start(), m.end())
    return None, None


def event_time(text: str) -> tuple[str | None, str | None]:
    m = TIME.search(text)
    if not m:
        return None, None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None, None
    return f"{h:02d}:{mi:02d}", _sentence(text, m.start(), m.end())


def _clean_place(phrase: str) -> str:
    phrase = re.sub(r"\s+", " ", phrase).strip(" ,-–")
    # Line breaks in the PDF hide sentence ends: "șoseaua Tudor Neculai În data de ...".
    phrase = re.split(r"\s+(?:În|La|Pe|Pompierii|Echipaj\w*|Dispeceratul|Un|O|Au|A)\s", phrase, maxsplit=1)[0]
    # "strada Eternitate – intervenție a echipajelor" (a dash before lowercase text is a title clause).
    phrase = re.split(r"\s+[–-]\s+(?=[a-zăâîșț])", phrase, maxsplit=1)[0]
    # "strada Vasile Lupu din municipiul Iași" -> the street part only; the locality is added separately.
    return re.split(r"\s+(?:din|în|la|de pe|unde|pe raza|jude[țt]ul|municipiul|comuna|satul|localitatea)\s+",
                    phrase, maxsplit=1)[0].strip(" ,-–")


def location(title: str, text: str) -> dict:
    """Street/road phrase + locality, title first (it is the shortest summary), then the body."""
    tail = re.sub(r"^.*?SP[\s-]*nr\.?[\s-]*\d+[\s-]+din[\s-]+[\d.]+\s*[-–]\s*", "", title).replace("-", " ") \
        if "-" in title else title
    street = None
    evidence = None
    for source in (tail, text):
        for m in STREET.finditer(source):
            candidate = _clean_place(m.group(0))
            if len(candidate.split()) >= 2:
                street, evidence = candidate, _sentence(source, m.start(), m.end())
                break
        if street:
            break
    road = None
    if not street:
        for source in (tail, text):
            m = ROAD.search(source)
            if m:
                road, evidence = m.group(0).replace(" ", ""), _sentence(source, m.start(), m.end())
                break
    places = [(m.group(1).lower(), m.group(2)) for src in (tail, text) for m in PLACE.finditer(src)]
    locality = next((f"{kind} {name}" for kind, name in places if kind not in ("municipiul",) and name.lower() != "iași"),
                    None)
    in_city = bool(CITY.search(tail) or CITY.search(text))
    if in_city and not any(k in ("satul", "sat", "localitatea", "comuna") for k, _ in places[:2]):
        locality = "municipiul Iași"
    if not evidence and places:
        m = PLACE.search(tail) or PLACE.search(text)
        src = tail if PLACE.search(tail) else text
        evidence = _sentence(src, m.start(), m.end())
    parts = [p for p in (street or road, locality) if p]
    return {"loc_text": ", ".join(parts) if parts else None, "strada": street, "drum": road,
            "localitate": locality, "municipiu": locality == "municipiul Iași", "dovada": evidence}


def participants(text: str) -> list[str]:
    return [name for name, pattern in VEHICLES if re.search(pattern, text, re.I)]


def severity(title: str, text: str) -> tuple[str, str | None, bool | None]:
    """(gravitate, evidence, any_victim). ISU's own words decide; see README for the mapping."""
    for pattern, level in ((DEATH, "deces"), (SERIOUS, "grav")):
        m = pattern.search(text)
        if m:
            return level, _sentence(text, m.start(), m.end()), True
    if re.search(r"accident\w* rutier grav|grav accident", title, re.I):
        return "grav", title, True
    m = NO_VICTIM.search(text)
    if m:
        return "necunoscut", _sentence(text, m.start(), m.end()), False
    m = VICTIM.search(text)
    if m:
        return "usor", _sentence(text, m.start(), m.end()), True
    return "necunoscut", None, None


def parse(title: str, text: str) -> dict | None:
    """One release -> one event dict, or None when the release is not a road crash."""
    number, released = release_meta(title, text)
    main = body(text)
    if BODY_NOT_ROAD.search(title) or not BODY_CRASH.search(main + " " + title):
        return None
    if BODY_NOT_ROAD.search(main) and not re.search(r"accident\w* rutier", main, re.I):
        return None
    day, day_ev = event_date(main, released)
    hour, hour_ev = event_time(main)
    loc = location(title, main)
    gravity, gravity_ev, victims = severity(title, main)
    dovezi = {k: v for k, v in {
        "data_eveniment": day_ev, "ora": hour_ev, "loc_text": loc["dovada"], "gravitate": gravity_ev,
    }.items() if v}
    return {
        "nr_comunicat": number,
        "publicat_la": released.isoformat() if released else None,
        "data_eveniment": day,
        "ora": hour,
        **{k: loc[k] for k in ("loc_text", "strada", "drum", "localitate", "municipiu")},
        "participanti": participants(main),
        "gravitate": gravity,
        "victime": victims,
        "dovezi": dovezi,
        "text": main,
    }
