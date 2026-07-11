import random
import time
from datetime import datetime

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine
from gestionale_logistica.database.models import Ordine
from gestionale_logistica.ottimizzazione.clustering import raggruppa_ordini


def crea_ordine(id_, lat=None, lon=None):
    return Ordine(
        id=id_,
        indirizzo="Via Test 1",
        comune="Test",
        provincia="TT",
        lat=lat,
        lon=lon,
        cliente="Cliente Test",
        peso=10.0,
        volume_cargo=0.1,
        categoria_consegna=CategoriaConsegna.BORDO_STRADA,
        stato_ordine=StatoOrdine.RICEVUTO,
        data_consegna=None,
        viaggio_id=None,
    )


def _id_gruppi(gruppi):
    return [sorted(o.id for o in gruppo) for gruppo in gruppi]


def test_raggruppa_ordini_vicini_nello_stesso_cluster():
    # Ancona/Falconara: pochi km di distanza tra loro.
    ordini = [
        crea_ordine("ANCONA-1", lat=43.6158, lon=13.5189),
        crea_ordine("ANCONA-2", lat=43.6160, lon=13.5195),
        crea_ordine("FALCONARA", lat=43.6167, lon=13.3833),
    ]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)

    assert len(gruppi) == 1
    assert {o.id for o in gruppi[0]} == {"ANCONA-1", "ANCONA-2", "FALCONARA"}


def test_raggruppa_ordini_punto_isolato_e_proprio_cluster():
    ordini = [
        crea_ordine("ANCONA-1", lat=43.6158, lon=13.5189),
        crea_ordine("ANCONA-2", lat=43.6160, lon=13.5195),
        crea_ordine("PALERMO-ISOLATO", lat=38.1157, lon=13.3615),
    ]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)
    id_gruppi = _id_gruppi(gruppi)

    isolato = [g for g in id_gruppi if g == ["PALERMO-ISOLATO"]]
    assert len(isolato) == 1

    totale_ordini = sum(len(g) for g in id_gruppi)
    assert totale_ordini == 3


def test_raggruppa_ordini_senza_coordinate_non_causa_crash_ed_e_cluster_a_se():
    ordini = [
        crea_ordine("ANCONA-1", lat=43.6158, lon=13.5189),
        crea_ordine("ANCONA-2", lat=43.6160, lon=13.5195),
        crea_ordine("SENZA-COORD-1", lat=None, lon=None),
        crea_ordine("SENZA-COORD-2", lat=None, lon=None),
    ]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)
    id_gruppi = _id_gruppi(gruppi)

    assert ["SENZA-COORD-1"] in id_gruppi
    assert ["SENZA-COORD-2"] in id_gruppi
    totale_ordini = sum(len(g) for g in id_gruppi)
    assert totale_ordini == 4


def test_raggruppa_ordini_lista_vuota():
    assert raggruppa_ordini([], eps_km=50.0, min_samples=2) == []


# --- Stress test: casi limite aggiuntivi ---


def test_raggruppa_ordini_singolo_ordine():
    ordini = [crea_ordine("UNICO", lat=43.6158, lon=13.5189)]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)

    assert _id_gruppi(gruppi) == [["UNICO"]]


def test_raggruppa_ordini_coordinate_tutte_identiche_stesso_cluster():
    # Capita davvero nei dati reali: piu' ordini nello stesso comune hanno
    # esattamente le stesse coordinate (geocoding a livello di comune).
    ordini = [crea_ordine(f"ORD-{i}", lat=43.6158, lon=13.5189) for i in range(5)]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)

    assert len(gruppi) == 1
    assert {o.id for o in gruppi[0]} == {f"ORD-{i}" for i in range(5)}


def test_raggruppa_ordini_tutti_entro_eps_unico_cluster():
    centro_lat, centro_lon = 43.6158, 13.5189
    ordini = [
        crea_ordine(f"ORD-{i}", lat=centro_lat + i * 0.01, lon=centro_lon + i * 0.01) for i in range(6)
    ]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)

    assert len(gruppi) == 1
    assert len(gruppi[0]) == 6


def test_raggruppa_ordini_tutti_oltre_eps_tutti_isolati():
    # Citta' mutuamente a centinaia di km: nessuna coppia entro eps=50km, quindi
    # anche con min_samples=2 ogni ordine resta rumore (cluster a se').
    citta = [
        ("ANCONA", 43.6158, 13.5189),
        ("MILANO", 45.4642, 9.1900),
        ("PALERMO", 38.1157, 13.3615),
        ("TORINO", 45.0703, 7.6869),
        ("BARI", 41.1171, 16.8719),
    ]
    ordini = [crea_ordine(nome, lat=lat, lon=lon) for nome, lat, lon in citta]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)

    assert len(gruppi) == len(ordini)
    assert all(len(g) == 1 for g in gruppi)


def test_raggruppa_ordini_mix_con_e_senza_coordinate_conserva_tutti_gli_ordini():
    ordini = [
        crea_ordine("VICINO-1", lat=43.6158, lon=13.5189),
        crea_ordine("VICINO-2", lat=43.6160, lon=13.5195),
        crea_ordine("ISOLATO", lat=45.4642, lon=9.1900),
        crea_ordine("SENZA-COORD-1"),
        crea_ordine("SENZA-COORD-2"),
    ]

    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)

    assert sum(len(g) for g in gruppi) == len(ordini)
    id_gruppi = _id_gruppi(gruppi)
    assert ["SENZA-COORD-1"] in id_gruppi
    assert ["SENZA-COORD-2"] in id_gruppi


def test_raggruppa_ordini_dataset_grande_resta_veloce():
    rng = random.Random(123)
    ordini = [
        crea_ordine(f"ORD-{i}", lat=rng.uniform(36.0, 47.0), lon=rng.uniform(7.0, 18.0)) for i in range(500)
    ]

    inizio = time.perf_counter()
    gruppi = raggruppa_ordini(ordini, eps_km=50.0, min_samples=2)
    durata = time.perf_counter() - inizio

    assert sum(len(g) for g in gruppi) == 500
    assert durata < 10.0
