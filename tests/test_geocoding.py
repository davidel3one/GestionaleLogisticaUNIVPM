import time

import pytest

from gestionale_logistica.logistica.geocoding import (
    distanza_km,
    distanza_penalita_km,
    geocodifica_comune,
)


@pytest.mark.parametrize("comune,provincia", [("Fabriano", "AN"), ("Ancona", "AN")])
def test_comune_reale_dentro_bounding_box_italia(comune, provincia):
    coordinate = geocodifica_comune(comune, provincia)

    assert coordinate is not None
    lat, lon = coordinate
    assert 35 <= lat <= 47
    assert 6 <= lon <= 19


def test_comune_inesistente_ritorna_none():
    assert geocodifica_comune("Comuneinesistentexyz", "ZZ") is None


def test_distanza_km_stesso_punto_e_zero():
    assert distanza_km(43.6158, 13.5189, 43.6158, 13.5189) == pytest.approx(0.0, abs=1e-6)


def test_distanza_km_roma_milano():
    # Distanza in linea d'aria nota Roma-Milano: ~ 477 km
    distanza = distanza_km(41.9028, 12.4964, 45.4642, 9.1900)
    assert distanza == pytest.approx(477, rel=0.05)


def test_distanza_km_ancona_fabriano():
    # Distanza in linea d'aria nota Ancona-Fabriano: ~ 60 km
    distanza = distanza_km(43.6158, 13.5189, 43.3369, 12.9036)
    assert distanza == pytest.approx(60, rel=0.15)


def test_distanza_penalita_km_maggiore_di_distanze_reali_e_veloce():
    inizio = time.perf_counter()
    penalita = distanza_penalita_km()
    durata = time.perf_counter() - inizio

    assert penalita > distanza_km(41.9028, 12.4964, 45.4642, 9.1900)
    assert durata < 5.0
