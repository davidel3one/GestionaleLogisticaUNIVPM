"""Geocoding offline dei comuni italiani.

Dati coordinate da `data/geocoding/comuni_coordinate.csv`, derivato dal repo
`DarioCorno/database_comuni_italiani` (licenza MIT).
"""

import csv
import functools
import math
from pathlib import Path

COMUNI_PATH = Path(__file__).resolve().parent.parent / "data" / "geocoding" / "comuni_coordinate.csv"
RAGGIO_TERRESTRE_KM = 6371.0


@functools.lru_cache
def _tabella_comuni() -> dict[tuple[str, str], tuple[float, float]]:
    with open(COMUNI_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        return {
            (riga["Comune"].strip().casefold(), riga["Provincia"].strip().casefold()): (
                float(riga["Lat"]),
                float(riga["Lon"]),
            )
            for riga in reader
        }


def geocodifica_comune(comune: str, provincia: str) -> tuple[float, float] | None:
    return _tabella_comuni().get((comune.strip().casefold(), provincia.strip().casefold()))


def distanza_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza Haversine (km) tra due punti (lat, lon) in gradi decimali."""
    lat1_r, lon1_r, lat2_r, lon2_r = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return 2 * RAGGIO_TERRESTRE_KM * math.asin(math.sqrt(a))


def _convex_hull(punti: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Monotone chain (Andrew) su (lat, lon) trattate come piano cartesiano.

    E' un'approssimazione ma accettabile su scala
    nazionale: serve solo a restringere la ricerca del punto piu' distante
    (vedi distanza_penalita_km) a poche decine di vertici invece di ~7897 punti.
    """
    punti = sorted(set(punti))
    if len(punti) <= 2:
        return punti

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in punti:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list[tuple[float, float]] = []
    for p in reversed(punti):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


@functools.lru_cache
def distanza_penalita_km() -> float:
    """Distanza (km) di penalita' per ordini senza coordinate note.

    Definita come la distanza massima osservabile tra due comuni della tabella.
    Il calcolo esatto sarebbe O(n^2) su ~7897 comuni (~62M coppie Haversine),
    troppo lento per essere eseguito lazy dentro un piano da calcolare in <3
    minuti (RNF4). La distanza massima tra i punti di un insieme e' sempre raggiunta
    da due punti sul suo convex hull, quindi si restringe la ricerca esaustiva
    ai soli vertici del hull (tipicamente poche decine di punti).
    """
    coordinate = list(set(_tabella_comuni().values()))
    hull = _convex_hull(coordinate)
    if len(hull) < 2:
        return 0.0
    return max(
        distanza_km(lat1, lon1, lat2, lon2)
        for i, (lat1, lon1) in enumerate(hull)
        for lat2, lon2 in hull[i + 1 :]
    )
