import itertools
import math
import random
import time
from datetime import datetime, timedelta

import pytest

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine
from gestionale_logistica.database.models import Ordine
from gestionale_logistica.logistica.geocoding import distanza_km
from gestionale_logistica.ottimizzazione.stima_durata import (
    TEMPO_INSTALLAZIONE_MINUTI,
    VELOCITA_MEDIA_KMH,
    stima_durata_viaggio,
    tour_esatto,
    tour_euristico,
)


def crea_ordine(id_, lat=None, lon=None, categoria=CategoriaConsegna.BORDO_STRADA):
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
        categoria_consegna=categoria,
        stato_ordine=StatoOrdine.RICEVUTO,
        data_importazione=datetime.now(),
        data_consegna=None,
        viaggio_id=None,
    )


def _lunghezza_percorso(ordini):
    return sum(
        distanza_km(ordini[i].lat, ordini[i].lon, ordini[i + 1].lat, ordini[i + 1].lon)
        for i in range(len(ordini) - 1)
    )


def _minimo_a_forza_bruta(ordini):
    """Minimo su tutte le permutazioni del cammino aperto con ordini[0] fisso come partenza."""
    primo, resto = ordini[0], ordini[1:]
    return min(_lunghezza_percorso([primo, *perm]) for perm in itertools.permutations(resto))


# --- tour_esatto: verifica su un caso con soluzione nota (forza bruta) ---


def test_tour_esatto_trova_il_giro_piu_corto_su_un_pentagono():
    # 5 punti su un pentagono regolare, raggio piccolo (~0.05 gradi) cosi' la
    # distanza Haversine approssima bene quella planare euclidea.
    centro_lat, centro_lon, raggio = 43.6, 13.5, 0.05
    vertici = [
        crea_ordine(
            f"P{i}",
            lat=centro_lat + raggio * math.sin(2 * math.pi * i / 5),
            lon=centro_lon + raggio * math.cos(2 * math.pi * i / 5),
        )
        for i in range(5)
    ]
    # Input mescolato: il primo elemento non e' gia' un vertice "ovvio".
    ordini_input = [vertici[2], vertici[0], vertici[4], vertici[1], vertici[3]]

    tour, distanza = tour_esatto(ordini_input)

    minimo_atteso = _minimo_a_forza_bruta(ordini_input)
    assert distanza == pytest.approx(minimo_atteso, rel=1e-9)
    assert tour[0].id == ordini_input[0].id
    assert {o.id for o in tour} == {o.id for o in ordini_input}


def test_tour_esatto_caso_banale_zero_o_un_ordine():
    assert tour_esatto([]) == ([], 0.0)
    singolo = crea_ordine("UNICO", lat=43.6, lon=13.5)
    tour, distanza = tour_esatto([singolo])
    assert tour == [singolo]
    assert distanza == 0.0


# --- Costanti di installazione per categoria ---


@pytest.mark.parametrize(
    "categoria,minuti_attesi",
    [
        (CategoriaConsegna.BORDO_STRADA, 15),
        (CategoriaConsegna.INSTALLAZIONE_SEMPLICE_AL_PIANO, 30),
        (CategoriaConsegna.INCASSO, 45),
        (CategoriaConsegna.BIG, 60),
        (CategoriaConsegna.CERTIFICAZIONE_GAS, 60),
    ],
)
def test_stima_durata_viaggio_usa_tempo_installazione_per_categoria(categoria, minuti_attesi):
    ordine = crea_ordine("ORD-1", lat=43.6, lon=13.5, categoria=categoria)

    durata = stima_durata_viaggio([ordine], usa_esatto=True)

    assert durata == timedelta(minutes=minuti_attesi)
    assert TEMPO_INSTALLAZIONE_MINUTI[categoria] == minuti_attesi


def test_stima_durata_viaggio_somma_installazione_e_percorrenza():
    a = crea_ordine("A", lat=43.6158, lon=13.5189, categoria=CategoriaConsegna.BORDO_STRADA)
    b = crea_ordine("B", lat=43.6167, lon=13.3833, categoria=CategoriaConsegna.INCASSO)

    durata = stima_durata_viaggio([a, b], usa_esatto=True)

    _, distanza_tour = tour_esatto([a, b])
    atteso = timedelta(
        minutes=TEMPO_INSTALLAZIONE_MINUTI[a.categoria_consegna]
        + TEMPO_INSTALLAZIONE_MINUTI[b.categoria_consegna]
        + (distanza_tour / VELOCITA_MEDIA_KMH) * 60
    )
    assert durata == atteso


def test_stima_durata_viaggio_lista_vuota():
    assert stima_durata_viaggio([], usa_esatto=True) == timedelta()


# --- tour_esatto vs tour_euristico: l'esatto non e' mai peggiore ---


def test_tour_euristico_non_e_mai_piu_corto_dell_esatto():
    rng = random.Random(7)
    ordini = [
        crea_ordine(f"O{i}", lat=rng.uniform(38.0, 46.0), lon=rng.uniform(9.0, 16.0)) for i in range(8)
    ]

    _, distanza_esatta = tour_esatto(ordini)
    _, distanza_euristica = tour_euristico(ordini)

    assert distanza_esatta <= distanza_euristica + 1e-9


# --- Stress test: casi limite piccoli (n=0,1,2) su entrambi gli algoritmi ---


def test_tour_euristico_caso_banale_zero_o_un_ordine():
    assert tour_euristico([]) == ([], 0.0)
    singolo = crea_ordine("UNICO", lat=43.6, lon=13.5)
    tour, distanza = tour_euristico([singolo])
    assert tour == [singolo]
    assert distanza == 0.0


def test_tour_esatto_e_euristico_concordano_su_due_ordini():
    a = crea_ordine("A", lat=43.6158, lon=13.5189)
    b = crea_ordine("B", lat=43.6167, lon=13.3833)

    tour_e, distanza_e = tour_esatto([a, b])
    tour_h, distanza_h = tour_euristico([a, b])

    attesa = distanza_km(a.lat, a.lon, b.lat, b.lon)
    assert [o.id for o in tour_e] == ["A", "B"]
    assert [o.id for o in tour_h] == ["A", "B"]
    assert distanza_e == pytest.approx(attesa)
    assert distanza_h == pytest.approx(attesa)


# --- Coordinate duplicate (distanza 0): non deve confondere Held-Karp con pareggi ---


def test_tour_esatto_con_coordinate_duplicate():
    # Tre ordini nello stesso comune (stesse coordinate): ogni tratta costa 0,
    # quindi qualunque permutazione e' un tour ottimo valido di costo 0.
    ordini = [crea_ordine(f"O{i}", lat=43.6158, lon=13.5189) for i in range(4)]

    tour, distanza = tour_esatto(ordini)

    assert distanza == pytest.approx(0.0)
    assert {o.id for o in tour} == {o.id for o in ordini}
    assert tour[0].id == "O0"


# --- tour_esatto: caso noto calcolabile a mano (punti su una retta) ---


def test_tour_esatto_su_punti_allineati_su_una_retta():
    # Punti equispaziati su un meridiano (stessa lon, lat crescente): il tour
    # ottimo ovvio e' l'ordine lungo la retta, in un verso o nell'altro.
    base_lat, lon = 43.0, 13.0
    ordini_in_ordine = [crea_ordine(f"P{i}", lat=base_lat + i * 0.1, lon=lon) for i in range(6)]
    # Input mescolato apposta, ma con l'estremo P0 come partenza fissa.
    ordini_input = [ordini_in_ordine[0], ordini_in_ordine[3], ordini_in_ordine[5], ordini_in_ordine[1], ordini_in_ordine[4], ordini_in_ordine[2]]

    tour, distanza = tour_esatto(ordini_input)

    minimo_atteso = _minimo_a_forza_bruta(ordini_input)
    assert distanza == pytest.approx(minimo_atteso, rel=1e-9)
    # Partendo da P0 (l'estremo), il tour ottimo su una retta e' percorrerla
    # in ordine crescente di lat, cioe' P0,P1,P2,P3,P4,P5.
    assert [o.id for o in tour] == [f"P{i}" for i in range(6)]


# --- Somma installazione con tutte le 5 categorie miste nello stesso viaggio ---


def test_stima_durata_viaggio_somma_tutte_le_categorie_miste():
    ordini = [
        crea_ordine("A", lat=43.6, lon=13.5, categoria=CategoriaConsegna.BORDO_STRADA),
        crea_ordine("B", lat=43.6, lon=13.5, categoria=CategoriaConsegna.INSTALLAZIONE_SEMPLICE_AL_PIANO),
        crea_ordine("C", lat=43.6, lon=13.5, categoria=CategoriaConsegna.INCASSO),
        crea_ordine("D", lat=43.6, lon=13.5, categoria=CategoriaConsegna.BIG),
        crea_ordine("E", lat=43.6, lon=13.5, categoria=CategoriaConsegna.CERTIFICAZIONE_GAS),
    ]

    durata = stima_durata_viaggio(ordini, usa_esatto=True)

    # Coordinate identiche => distanza di percorrenza nulla, la durata e' solo
    # la somma dei tempi di installazione delle 5 categorie.
    totale_atteso = sum(TEMPO_INSTALLAZIONE_MINUTI[o.categoria_consegna] for o in ordini)
    assert totale_atteso == 15 + 30 + 45 + 60 + 60
    assert durata == timedelta(minutes=totale_atteso)


# --- Performance: tour_euristico con n grande ---


def test_tour_euristico_dataset_grande_resta_veloce():
    rng = random.Random(99)
    ordini = [
        crea_ordine(f"O{i}", lat=rng.uniform(36.0, 47.0), lon=rng.uniform(7.0, 18.0)) for i in range(200)
    ]

    inizio = time.perf_counter()
    tour, distanza = tour_euristico(ordini)
    durata = time.perf_counter() - inizio

    assert len(tour) == 200
    assert distanza > 0.0
    assert durata < 5.0
