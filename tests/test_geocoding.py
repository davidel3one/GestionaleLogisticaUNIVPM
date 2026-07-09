import pytest

from gestionale_logistica.logistica.geocoding import geocodifica_comune


@pytest.mark.parametrize("comune,provincia", [("Fabriano", "AN"), ("Ancona", "AN")])
def test_comune_reale_dentro_bounding_box_italia(comune, provincia):
    coordinate = geocodifica_comune(comune, provincia)

    assert coordinate is not None
    lat, lon = coordinate
    assert 35 <= lat <= 47
    assert 6 <= lon <= 19


def test_comune_inesistente_ritorna_none():
    assert geocodifica_comune("Comuneinesistentexyz", "ZZ") is None
