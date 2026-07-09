"""Geocoding offline dei comuni italiani.

Dati coordinate da `data/geocoding/comuni_coordinate.csv`, derivato dal repo
`DarioCorno/database_comuni_italiani` (licenza MIT).
"""

import csv
import functools
from pathlib import Path

COMUNI_PATH = Path(__file__).resolve().parent.parent / "data" / "geocoding" / "comuni_coordinate.csv"


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
