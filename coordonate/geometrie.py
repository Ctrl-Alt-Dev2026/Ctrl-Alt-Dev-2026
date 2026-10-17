"""Geometrie minimă, fără dependențe externe.

Convenție: în cod lucrăm cu `(lat, lon)`; în GeoJSON ordinea este
`[lon, lat]` (vezi contractul din plan, secțiunea 4).
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

Punct = tuple[float, float]  # (lat, lon)

RAZA_PAMANT_M = 6_371_008.8


def distanta_m(a: Punct, b: Punct) -> float:
    """Distanța haversine în metri între două puncte (lat, lon)."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RAZA_PAMANT_M * math.asin(min(1.0, math.sqrt(h)))


def punct_median_polilinie(coordonate: Sequence[Punct]) -> Punct | None:
    """Punctul de la jumătatea lungimii unei polilinii.

    Pentru o stradă e mai onest decât media aritmetică a nodurilor (care e
    trasă de porțiunile cu multe noduri).
    """
    puncte = [p for p in coordonate if p is not None]
    if not puncte:
        return None
    if len(puncte) == 1:
        return puncte[0]
    lungimi = [distanta_m(puncte[i], puncte[i + 1]) for i in range(len(puncte) - 1)]
    total = sum(lungimi)
    if total == 0:
        return puncte[0]
    tinta = total / 2
    parcurs = 0.0
    for i, seg in enumerate(lungimi):
        if parcurs + seg >= tinta:
            if seg == 0:
                return puncte[i]
            t = (tinta - parcurs) / seg
            lat = puncte[i][0] + t * (puncte[i + 1][0] - puncte[i][0])
            lon = puncte[i][1] + t * (puncte[i + 1][1] - puncte[i][1])
            return (lat, lon)
        parcurs += seg
    return puncte[-1]


def _orientare(p: Punct, q: Punct, r: Punct) -> float:
    return (q[1] - p[1]) * (r[0] - p[0]) - (q[0] - p[0]) * (r[1] - p[1])


def intersectie_segmente(p1: Punct, p2: Punct, p3: Punct, p4: Punct) -> Punct | None:
    """Punctul de intersecție a două segmente, sau None.

    Aproximare plană: la scara unui oraș, eroarea e sub nivelul la care ne
    pasă (folosim rezultatul doar ca indiciu „străzile se suprapun în plan”).
    """
    x1, y1 = p1[1], p1[0]
    x2, y2 = p2[1], p2[0]
    x3, y3 = p3[1], p3[0]
    x4, y4 = p4[1], p4[0]
    num = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(num) < 1e-14:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / num
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / num
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None
    return (y1 + t * (y2 - y1), x1 + t * (x2 - x1))


def intersectii_polilinii(a: Sequence[Punct], b: Sequence[Punct]) -> list[Punct]:
    """Toate punctele în care două polilinii se taie în plan."""
    rezultat: list[Punct] = []
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            p = intersectie_segmente(a[i], a[i + 1], b[j], b[j + 1])
            if p is not None:
                rezultat.append(p)
    return rezultat


def grupeaza_puncte(puncte: Iterable[Punct], raza_m: float) -> list[list[Punct]]:
    """Grupează punctele apropiate (ex. mai multe noduri ale aceleiași intersecții)."""
    grupuri: list[list[Punct]] = []
    for p in puncte:
        for g in grupuri:
            if any(distanta_m(p, q) <= raza_m for q in g):
                g.append(p)
                break
        else:
            grupuri.append([p])
    return grupuri


def centru_grup(grup: Sequence[Punct]) -> Punct:
    return (
        sum(p[0] for p in grup) / len(grup),
        sum(p[1] for p in grup) / len(grup),
    )


# ------------------------------------------------------------------ poligoane


def _in_inel(lat: float, lon: float, inel: Sequence[Sequence[float]]) -> bool:
    """Ray casting pe un inel GeoJSON ([lon, lat], ...)."""
    inauntru = False
    n = len(inel)
    for i in range(n):
        x1, y1 = inel[i][0], inel[i][1]
        x2, y2 = inel[(i + 1) % n][0], inel[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            if y2 == y1:
                continue
            x_tai = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_tai:
                inauntru = not inauntru
    return inauntru


def _in_poligon(lat: float, lon: float, poligon: Sequence[Sequence[Sequence[float]]]) -> bool:
    if not poligon:
        return False
    if not _in_inel(lat, lon, poligon[0]):
        return False
    for gaura in poligon[1:]:
        if _in_inel(lat, lon, gaura):
            return False
    return True


def punct_in_geometrie(lat: float, lon: float, geometrie: dict) -> bool:
    """Test punct-în-poligon pentru geometrii GeoJSON Polygon / MultiPolygon."""
    tip = (geometrie or {}).get("type")
    coord = (geometrie or {}).get("coordinates")
    if not tip or not coord:
        return False
    if tip == "Polygon":
        return _in_poligon(lat, lon, coord)
    if tip == "MultiPolygon":
        return any(_in_poligon(lat, lon, p) for p in coord)
    if tip == "GeometryCollection":
        return any(punct_in_geometrie(lat, lon, g) for g in geometrie.get("geometries", []))
    return False


def bbox_geometrie(geometrie: dict) -> tuple[float, float, float, float] | None:
    """(sud, vest, nord, est) pentru o geometrie GeoJSON."""
    lats: list[float] = []
    lons: list[float] = []

    def adauga(c) -> None:
        if not c:
            return
        if isinstance(c[0], (int, float)):
            lons.append(float(c[0]))
            lats.append(float(c[1]))
            return
        for sub in c:
            adauga(sub)

    adauga((geometrie or {}).get("coordinates"))
    if not lats:
        return None
    return (min(lats), min(lons), max(lats), max(lons))
