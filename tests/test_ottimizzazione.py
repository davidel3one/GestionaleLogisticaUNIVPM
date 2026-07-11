import inspect
import itertools
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Camion,
    ComposizioneSquadra,
    Dipendente,
    Ordine,
    Squadra,
    Viaggio,
)
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.logistica.geocoding import distanza_km, distanza_penalita_km
from gestionale_logistica.ottimizzazione import motore_ottimizzazione as modulo_motore
from gestionale_logistica.ottimizzazione import stima_durata as modulo_stima_durata
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import (
    LIMITE_RNF4_SECONDI,
    MINIMO_TIME_LIMIT_KNAPSACK_SECONDI,
    AssegnazioneViaggio,
    MotoreOttimizzazione,
    PianoGiornaliero,
    _time_limit_residuo,
)
from gestionale_logistica.ottimizzazione.stima_durata import stima_durata_viaggio

DATI_ESEMPIO = Path(__file__).parent.parent / "dati_esempio"


def crea_dipendente(id_, certificazione_gas=False):
    return Dipendente(
        id=id_,
        nome="Nome",
        cognome="Cognome",
        codice_fiscale=f"CF-{id_}",
        data_assunzione=datetime(2020, 1, 1),
        data_licenziamento=None,
        flg_attivo=True,
        flg_certificazione_gas=certificazione_gas,
    )


def crea_camion(id_, peso_massimo=100.0, volume_massimo=5.0, sponda_idraulica=False):
    return Camion(
        id=id_,
        targa=f"TARGA-{id_}",
        tipo_mezzo="Furgone",
        peso_massimo=peso_massimo,
        volume_massimo=volume_massimo,
        flg_sponda_idraulica=sponda_idraulica,
        data_acquisizione=datetime(2020, 1, 1),
        data_dismissione=None,
        flg_attivo=True,
    )


def crea_composizione(
    id_,
    camion_id,
    dipendente_1_id,
    dipendente_2_id,
    data_inizio=datetime(2020, 1, 1),
    data_fine=None,
    attiva=True,
):
    return ComposizioneSquadra(
        id_composizione=id_,
        squadra_id=id_,
        camion_id=camion_id,
        dipendente_1_id=dipendente_1_id,
        dipendente_2_id=dipendente_2_id,
        data_inizio_validita=data_inizio,
        data_fine_validita=data_fine,
        flg_attiva=attiva,
    )


def crea_ordine(
    id_,
    peso=10.0,
    volume=0.1,
    categoria=CategoriaConsegna.BORDO_STRADA,
    stato=StatoOrdine.RICEVUTO,
    lat=None,
    lon=None,
    viaggio_id=None,
):
    return Ordine(
        id=id_,
        indirizzo="Via Test 1",
        comune="Ancona",
        provincia="AN",
        lat=lat,
        lon=lon,
        cliente="Cliente Test",
        peso=peso,
        volume_cargo=volume,
        categoria_consegna=categoria,
        stato_ordine=stato,
        data_consegna=None,
        viaggio_id=viaggio_id,
    )


def crea_flotta_semplice(
    session,
    comp_id="C1",
    peso_massimo=100.0,
    volume_massimo=5.0,
    sponda=False,
    gas=False,
    data_inizio=datetime(2020, 1, 1),
    data_fine=None,
    attiva=True,
):
    session.add(Squadra(id=comp_id, flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
    session.add(crea_dipendente(f"{comp_id}-D1", certificazione_gas=gas))
    session.add(crea_dipendente(f"{comp_id}-D2", certificazione_gas=False))
    session.add(crea_camion(f"{comp_id}-CAM", peso_massimo=peso_massimo, volume_massimo=volume_massimo, sponda_idraulica=sponda))
    session.add(
        crea_composizione(
            comp_id,
            f"{comp_id}-CAM",
            f"{comp_id}-D1",
            f"{comp_id}-D2",
            data_inizio=data_inizio,
            data_fine=data_fine,
            attiva=attiva,
        )
    )


# --- RF12: suggerisci_ordini ---


def test_suggerisci_ordini_filtra_idoneita_rispetta_capacita_e_non_scrive_su_db(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=100.0, volume_massimo=5.0, sponda=False, gas=False)
        session.add(
            Viaggio(
                id="V1",
                data_partenza_prevista=datetime(2026, 7, 10, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 10, 16, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.PIANIFICATO,
                composizione_id="C1",
            )
        )
        session.add(crea_ordine("ORD-ESISTENTE", peso=30.0, volume=1.0, viaggio_id="V1"))

        session.add(crea_ordine("ORD-NORMALE-1", peso=20.0, volume=0.5))
        session.add(crea_ordine("ORD-NORMALE-2", peso=20.0, volume=0.5))
        session.add(crea_ordine("ORD-PESANTE", peso=60.0, volume=0.5))
        session.add(crea_ordine("ORD-BIG-NO-SPONDA", peso=10.0, volume=0.2, categoria=CategoriaConsegna.BIG))
        session.add(
            crea_ordine(
                "ORD-GAS-NO-CERT", peso=10.0, volume=0.2, categoria=CategoriaConsegna.CERTIFICAZIONE_GAS
            )
        )
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    suggerimento = motore.suggerisci_ordini("V1")

    assert set(suggerimento.ordini_suggeriti) == {"ORD-NORMALE-1", "ORD-NORMALE-2"}
    assert suggerimento.peso_utilizzato == pytest.approx(30.0 + 20.0 + 20.0)
    assert suggerimento.volume_utilizzato == pytest.approx(1.0 + 0.5 + 0.5)
    assert suggerimento.peso_disponibile == 100.0
    assert suggerimento.volume_disponibile == 5.0

    with session_factory() as session:
        for ordine_id in [
            "ORD-NORMALE-1",
            "ORD-NORMALE-2",
            "ORD-PESANTE",
            "ORD-BIG-NO-SPONDA",
            "ORD-GAS-NO-CERT",
        ]:
            ordine = session.get(Ordine, ordine_id)
            assert ordine.viaggio_id is None
            assert ordine.stato_ordine == StatoOrdine.RICEVUTO


def test_suggerisci_ordini_nessun_ordine_idoneo(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", sponda=False, gas=False)
        session.add(
            Viaggio(
                id="V1",
                data_partenza_prevista=datetime(2026, 7, 10, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 10, 16, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.PIANIFICATO,
                composizione_id="C1",
            )
        )
        session.add(crea_ordine("ORD-BIG", categoria=CategoriaConsegna.BIG))
        session.add(crea_ordine("ORD-GAS", categoria=CategoriaConsegna.CERTIFICAZIONE_GAS))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    suggerimento = motore.suggerisci_ordini("V1")

    assert suggerimento.ordini_suggeriti == []


# --- RF13: calcola_piano ---


def test_calcola_piano_assegna_su_piu_viaggi_rispettando_capacita(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=100.0, volume_massimo=10.0)
        crea_flotta_semplice(session, "C2", peso_massimo=100.0, volume_massimo=10.0)
        for i in range(4):
            session.add(crea_ordine(f"ORD-{i}", peso=60.0, volume=0.5))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert len(piano.assegnazioni) == 2
    for assegnazione in piano.assegnazioni:
        assert len(assegnazione.ordini_ids) == 1
    assert len(piano.ordini_non_assegnati) == 2


def test_calcola_piano_preferisce_raggruppamenti_vicini(session_factory):
    # Ancona/Falconara: vicine. Milano/Palermo: molto lontane tra loro e da Ancona.
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=100.0, volume_massimo=10.0)
        session.add(crea_ordine("ORD-ANCONA", peso=45.0, lat=43.6158, lon=13.5189))
        session.add(crea_ordine("ORD-FALCONARA", peso=45.0, lat=43.6167, lon=13.3833))
        session.add(crea_ordine("ORD-MILANO", peso=45.0, lat=45.4642, lon=9.1900))
        session.add(crea_ordine("ORD-PALERMO", peso=45.0, lat=38.1157, lon=13.3615))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert len(piano.assegnazioni) == 1
    assert set(piano.assegnazioni[0].ordini_ids) == {"ORD-ANCONA", "ORD-FALCONARA"}
    assert set(piano.ordini_non_assegnati) == {"ORD-MILANO", "ORD-PALERMO"}


def test_calcola_piano_nessuna_composizione_disponibile(session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1"))
        session.add(crea_ordine("ORD-2"))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert piano.assegnazioni == []
    assert set(piano.ordini_non_assegnati) == {"ORD-1", "ORD-2"}


def test_calcola_piano_ordini_senza_coordinate_non_causano_crash_ne_vantaggio_gratuito(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=100.0, volume_massimo=10.0)
        session.add(crea_ordine("ORD-VICINO-A", peso=45.0, lat=43.6158, lon=13.5189))
        session.add(crea_ordine("ORD-VICINO-B", peso=45.0, lat=43.6167, lon=13.3833))
        session.add(crea_ordine("ORD-SENZA-COORD-1", peso=45.0, lat=None, lon=None))
        session.add(crea_ordine("ORD-SENZA-COORD-2", peso=45.0, lat=None, lon=None))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert len(piano.assegnazioni) == 1
    assert set(piano.assegnazioni[0].ordini_ids) == {"ORD-VICINO-A", "ORD-VICINO-B"}
    assert set(piano.ordini_non_assegnati) == {"ORD-SENZA-COORD-1", "ORD-SENZA-COORD-2"}


def test_calcola_piano_non_accetta_piu_un_parametro_data_indipendente_da_ora_partenza():
    # Regressione: calcola_piano prendeva in origine sia `data` (per la finestra
    # "composizioni occupate quel giorno") sia `ora_partenza` (con cui applica_piano
    # timbra i nuovi Viaggio) come parametri indipendenti - un chiamante poteva
    # passarli su giorni diversi, facendo risultare una composizione "libera" qui
    # ma doppio-prenotata all'applicazione del piano. Il giorno va derivato
    # internamente da ora_partenza.date(): non deve piu' esistere un parametro
    # `data` separato che possa disallinearsi.
    parametri = inspect.signature(MotoreOttimizzazione.calcola_piano).parameters

    assert "data" not in parametri
    assert "ora_partenza" in parametri


# --- RF13: applica_piano ---


def test_applica_piano_id_sequenziale_e_persistenza(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        crea_flotta_semplice(session, "C2")
        session.add(crea_ordine("ORD-1", peso=10.0))
        session.add(crea_ordine("ORD-2", peso=10.0))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = PianoGiornaliero(
        assegnazioni=[
            AssegnazioneViaggio(composizione_id="C1", ordini_ids=["ORD-1"]),
            AssegnazioneViaggio(composizione_id="C2", ordini_ids=["ORD-2"]),
        ],
        ordini_non_assegnati=[],
    )

    ora_partenza = datetime(2026, 7, 10, 8, 0)
    risultato = motore.applica_piano(piano, ora_partenza, durata_viaggio=timedelta(hours=6))

    assert risultato.viaggi_creati == ["V-20260710-01", "V-20260710-02"]
    assert risultato.ordini_assegnati == 2

    with session_factory() as session:
        viaggio_1 = session.get(Viaggio, "V-20260710-01")
        assert viaggio_1.composizione_id == "C1"
        assert viaggio_1.data_partenza_prevista == ora_partenza
        assert viaggio_1.data_arrivo_prevista == ora_partenza + timedelta(hours=6)
        assert viaggio_1.stato_viaggio == StatoViaggio.PIANIFICATO

        ordine_1 = session.get(Ordine, "ORD-1")
        assert ordine_1.viaggio_id == "V-20260710-01"
        assert ordine_1.stato_ordine == StatoOrdine.PIANIFICATO

    # Un secondo giorno riparte da 01
    with session_factory() as session:
        crea_flotta_semplice(session, "C3")
        session.add(crea_ordine("ORD-3", peso=10.0))
        session.commit()

    piano_giorno_2 = PianoGiornaliero(
        assegnazioni=[AssegnazioneViaggio(composizione_id="C3", ordini_ids=["ORD-3"])],
        ordini_non_assegnati=[],
    )
    risultato_2 = motore.applica_piano(piano_giorno_2, datetime(2026, 7, 11, 8, 0))

    assert risultato_2.viaggi_creati == ["V-20260711-01"]


def test_applica_piano_stesso_giorno_continua_il_progressivo(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        crea_flotta_semplice(session, "C2")
        session.add(crea_ordine("ORD-1", peso=10.0))
        session.add(crea_ordine("ORD-2", peso=10.0))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    ora_partenza = datetime(2026, 7, 10, 8, 0)

    primo = motore.applica_piano(
        PianoGiornaliero(
            assegnazioni=[AssegnazioneViaggio(composizione_id="C1", ordini_ids=["ORD-1"])],
            ordini_non_assegnati=[],
        ),
        ora_partenza,
    )
    secondo = motore.applica_piano(
        PianoGiornaliero(
            assegnazioni=[AssegnazioneViaggio(composizione_id="C2", ordini_ids=["ORD-2"])],
            ordini_non_assegnati=[],
        ),
        ora_partenza,
    )

    assert primo.viaggi_creati == ["V-20260710-01"]
    assert secondo.viaggi_creati == ["V-20260710-02"]


# --- Coerenza incrociata _ordine_idoneo (RF11) ---


@pytest.mark.parametrize(
    "categoria,sponda,gas_certificato,atteso",
    [
        (CategoriaConsegna.BIG, True, False, True),
        (CategoriaConsegna.BIG, False, False, False),
        (CategoriaConsegna.CERTIFICAZIONE_GAS, False, True, True),
        (CategoriaConsegna.CERTIFICAZIONE_GAS, False, False, False),
        (CategoriaConsegna.BORDO_STRADA, False, False, True),
    ],
)
def test_ordine_idoneo_coerente_tra_suggerisci_e_calcola_piano(
    session_factory, categoria, sponda, gas_certificato, atteso
):
    motore = MotoreOttimizzazione(session_factory)
    camion = crea_camion("CAM-TEST", sponda_idraulica=sponda)
    dipendenti = [
        crea_dipendente("D1", certificazione_gas=gas_certificato),
        crea_dipendente("D2", certificazione_gas=False),
    ]
    ordine = crea_ordine("ORD-TEST", categoria=categoria)

    risultato = motore._ordine_idoneo(ordine, camion, dipendenti)

    assert risultato is atteso


# --- Guardrail RNF4 sul timeLimit del knapsack ---


def test_time_limit_residuo_riflette_il_tempo_gia_trascorso(monkeypatch):
    tempi = iter([1000.0, 1050.0])
    monkeypatch.setattr(modulo_motore.time, "perf_counter", lambda: next(tempi))

    inizio_esecuzione = modulo_motore.time.perf_counter()  # 1000.0
    limite = _time_limit_residuo(inizio_esecuzione)  # ora=1050.0 -> trascorsi 50s

    assert limite == pytest.approx(LIMITE_RNF4_SECONDI - 50.0)


def test_time_limit_residuo_non_scende_sotto_il_minimo_pratico(monkeypatch):
    monkeypatch.setattr(modulo_motore.time, "perf_counter", lambda: 10_000.0)

    limite = _time_limit_residuo(inizio_esecuzione=0.0)

    assert limite == MINIMO_TIME_LIMIT_KNAPSACK_SECONDI


# --- Benchmark RNF4 (<3 minuti) ---


def test_benchmark_calcola_piano_dataset_sintetico(session_factory):
    random.seed(42)
    categorie = list(CategoriaConsegna)

    with session_factory() as session:
        for i in range(15):
            crea_flotta_semplice(
                session,
                f"C{i}",
                peso_massimo=200.0,
                volume_massimo=8.0,
                sponda=(i % 3 == 0),
                gas=(i % 4 == 0),
            )

        comuni = list(
            {
                ("Ancona", "AN", 43.6158, 13.5189),
                ("Fabriano", "AN", 43.3369, 12.9036),
                ("Milano", "MI", 45.4642, 9.1900),
                ("Palermo", "PA", 38.1157, 13.3615),
                ("Roma", "RM", 41.9028, 12.4964),
            }
        )
        for i in range(150):
            comune = random.choice(comuni)
            usa_coordinate = random.random() > 0.1
            session.add(
                crea_ordine(
                    f"ORD-{i}",
                    peso=random.uniform(5.0, 40.0),
                    volume=random.uniform(0.05, 1.5),
                    categoria=random.choice(categorie),
                    lat=comune[2] if usa_coordinate else None,
                    lon=comune[3] if usa_coordinate else None,
                )
            )
        session.commit()

    motore = MotoreOttimizzazione(session_factory)

    inizio = time.perf_counter()
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))
    durata = time.perf_counter() - inizio

    print(f"\n[benchmark sintetico] durata calcola_piano: {durata:.2f}s")
    assert durata < 180.0

    # Il piano e' coerente: nessun ordine duplicato tra viaggi diversi, e
    # assegnati + non assegnati coprono esattamente tutti i 150 ordini generati
    # (la flotta di 15 composizioni copre sponda idraulica e certificazione gas,
    # quindi ogni ordine e' candidato idoneo per almeno una composizione).
    tutti_ordini_assegnati = [oid for a in piano.assegnazioni for oid in a.ordini_ids]
    assert len(tutti_ordini_assegnati) == len(set(tutti_ordini_assegnati))
    assert len(tutti_ordini_assegnati) + len(piano.ordini_non_assegnati) == 150


def test_benchmark_calcola_piano_dati_reali(session_factory):
    gestore = GestoreLogistica(session_factory)
    risultato_import = gestore.importa_ordini(DATI_ESEMPIO / "Ordini_Unieuro_20260706.csv")
    assert risultato_import.errori == []

    with session_factory() as session:
        for i in range(5):
            crea_flotta_semplice(
                session,
                f"C{i}",
                peso_massimo=300.0,
                volume_massimo=10.0,
                sponda=True,
                gas=True,
            )
        session.commit()

    motore = MotoreOttimizzazione(session_factory)

    inizio = time.perf_counter()
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))
    durata = time.perf_counter() - inizio

    print(f"\n[benchmark dati reali] durata calcola_piano: {durata:.2f}s")
    assert durata < 180.0


# --- Stress test: casi limite aggiuntivi RF12 (suggerisci_ordini) ---


def test_suggerisci_ordini_viaggio_gia_a_capacita_massima(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=50.0, volume_massimo=1.0)
        session.add(
            Viaggio(
                id="V1",
                data_partenza_prevista=datetime(2026, 7, 10, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 10, 16, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.PIANIFICATO,
                composizione_id="C1",
            )
        )
        session.add(crea_ordine("ORD-GIA-CARICATO", peso=50.0, volume=1.0, viaggio_id="V1"))
        session.add(crea_ordine("ORD-CANDIDATO-1", peso=10.0, volume=0.1))
        session.add(crea_ordine("ORD-CANDIDATO-2", peso=5.0, volume=0.05))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    suggerimento = motore.suggerisci_ordini("V1")

    assert suggerimento.ordini_suggeriti == []
    assert suggerimento.peso_utilizzato == pytest.approx(50.0)
    assert suggerimento.volume_utilizzato == pytest.approx(1.0)


def test_suggerisci_ordini_nessun_ordine_nel_sistema(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(
            Viaggio(
                id="V1",
                data_partenza_prevista=datetime(2026, 7, 10, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 10, 16, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.PIANIFICATO,
                composizione_id="C1",
            )
        )
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    suggerimento = motore.suggerisci_ordini("V1")

    assert suggerimento.ordini_suggeriti == []


# Nota: "tutti i candidati strutturalmente non idonei per quel camion/squadra"
# e' gia' coperto da test_suggerisci_ordini_nessun_ordine_idoneo sopra.


# --- Stress test: composizioni escluse da calcola_piano per motivi diversi ---


def test_calcola_piano_composizione_inattiva_esclusa(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", attiva=False)
        session.add(crea_ordine("ORD-1"))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert piano.assegnazioni == []
    assert piano.ordini_non_assegnati == ["ORD-1"]


def test_calcola_piano_composizione_fuori_intervallo_validita_esclusa(session_factory):
    with session_factory() as session:
        # Composizione valida solo a partire dal giorno successivo alla data pianificata.
        crea_flotta_semplice(session, "C1", data_inizio=datetime(2026, 7, 11))
        session.add(crea_ordine("ORD-1"))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert piano.assegnazioni == []
    assert piano.ordini_non_assegnati == ["ORD-1"]


def test_calcola_piano_composizione_gia_occupata_quel_giorno_esclusa(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(
            Viaggio(
                id="V-OCCUPATO",
                data_partenza_prevista=datetime(2026, 7, 10, 7, 0),
                data_arrivo_prevista=datetime(2026, 7, 10, 15, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.PIANIFICATO,
                composizione_id="C1",
            )
        )
        session.add(crea_ordine("ORD-1"))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert piano.assegnazioni == []
    assert piano.ordini_non_assegnati == ["ORD-1"]


def test_calcola_piano_nessun_ordine_candidato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert piano.assegnazioni == []
    assert piano.ordini_non_assegnati == []


# --- Stress test: idoneita' impossibile su tutta la flotta disponibile ---


def test_calcola_piano_tutti_big_nessun_camion_con_sponda_finiscono_non_assegnati(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", sponda=False)
        crea_flotta_semplice(session, "C2", sponda=False)
        for i in range(3):
            session.add(crea_ordine(f"ORD-BIG-{i}", categoria=CategoriaConsegna.BIG))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert piano.assegnazioni == []
    assert set(piano.ordini_non_assegnati) == {"ORD-BIG-0", "ORD-BIG-1", "ORD-BIG-2"}


def test_calcola_piano_tutti_gas_nessun_dipendente_certificato_finiscono_non_assegnati(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", gas=False)
        crea_flotta_semplice(session, "C2", gas=False)
        for i in range(3):
            session.add(crea_ordine(f"ORD-GAS-{i}", categoria=CategoriaConsegna.CERTIFICAZIONE_GAS))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert piano.assegnazioni == []
    assert set(piano.ordini_non_assegnati) == {"ORD-GAS-0", "ORD-GAS-1", "ORD-GAS-2"}


# --- Stress test: vincolo di durata cosi' stretto che nemmeno un ordine solo rientra ---


def test_calcola_piano_durata_troppo_stretta_anche_per_un_solo_ordine(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", sponda=True)
        session.add(crea_ordine("ORD-BIG-SOLO", categoria=CategoriaConsegna.BIG, peso=10.0, volume=0.1))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    # Il tempo di installazione di una BIG (60 min) supera da solo il budget di 30 min:
    # il ciclo di riduzione per durata deve arrivare a un sottoinsieme vuoto senza
    # errori ne' loop infiniti, e l'ordine deve finire tra i non assegnati.
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0), durata_viaggio=timedelta(minutes=30))

    assert piano.assegnazioni == []
    assert piano.ordini_non_assegnati == ["ORD-BIG-SOLO"]


# --- Stress test: guardrail RNF4 (60% del budget) verificato end-to-end ---


def test_calcola_piano_guardrail_tempo_transizione_esatto_poi_euristico(session_factory, monkeypatch):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=1000.0, volume_massimo=100.0)
        crea_flotta_semplice(session, "C2", peso_massimo=1000.0, volume_massimo=100.0)
        # Due cluster geografici distinti (Ancona a 3 ordini, Milano a 2), entrambi
        # sotto SOGLIA_NODI_HELD_KARP: l'ordinamento per dimensione decrescente in
        # calcola_piano elabora prima Ancona (piu' numeroso) e poi Milano.
        for i in range(3):
            session.add(
                crea_ordine(
                    f"ORD-ANCONA-{i}", categoria=CategoriaConsegna.BORDO_STRADA, lat=43.6158, lon=13.5189
                )
            )
        for i in range(2):
            session.add(
                crea_ordine(
                    f"ORD-MILANO-{i}", categoria=CategoriaConsegna.BORDO_STRADA, lat=45.4642, lon=9.1900
                )
            )
        session.commit()

    tour_esatto_reale = modulo_motore.tour_esatto
    tour_euristico_reale = modulo_motore.tour_euristico
    chiamate_esatto = []
    chiamate_euristico = []

    def spia_esatto(ordini):
        chiamate_esatto.append({o.id for o in ordini})
        return tour_esatto_reale(ordini)

    def spia_euristico(ordini):
        chiamate_euristico.append({o.id for o in ordini})
        return tour_euristico_reale(ordini)

    # Spia su entrambi i namespace: quello di motore_ottimizzazione (usato da
    # _rimuovi_ordine_piu_dispersivo) e quello di stima_durata (usato
    # internamente da stima_durata_viaggio) - il guardrail deve forzare
    # l'euristico su entrambi i percorsi di chiamata.
    monkeypatch.setattr(modulo_motore, "tour_esatto", spia_esatto)
    monkeypatch.setattr(modulo_motore, "tour_euristico", spia_euristico)
    monkeypatch.setattr(modulo_stima_durata, "tour_esatto", spia_esatto)
    monkeypatch.setattr(modulo_stima_durata, "tour_euristico", spia_euristico)

    # Sequenza di tempi trascorsi restituiti da perf_counter ad ogni chiamata
    # successiva: durante l'elaborazione del cluster Ancona (primo, piu'
    # numeroso) il tempo resta sotto la soglia del 60% del budget RNF4 (108s
    # su 180s); prima che inizi l'elaborazione del cluster Milano (secondo) la
    # soglia e' gia' superata. Riproduce una transizione realistica, non il
    # caso degenere in cui il guardrail scatta gia' sul primissimo cluster.
    tempi = [0.0, 10.0, 50.0, 120.0, 150.0]
    stato_perf_counter = {"n": 0}

    def perf_counter_simulato():
        indice = min(stato_perf_counter["n"], len(tempi) - 1)
        stato_perf_counter["n"] += 1
        return tempi[indice]

    monkeypatch.setattr(modulo_motore.time, "perf_counter", perf_counter_simulato)

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0), durata_viaggio=timedelta(hours=4))

    ordini_ancona_ids = {f"ORD-ANCONA-{i}" for i in range(3)}
    ordini_milano_ids = {f"ORD-MILANO-{i}" for i in range(2)}

    assert any(chiamata == ordini_ancona_ids for chiamata in chiamate_esatto), (
        "il cluster Ancona (elaborato per primo, sotto soglia) doveva usare tour_esatto"
    )
    assert any(chiamata == ordini_milano_ids for chiamata in chiamate_euristico), (
        "il cluster Milano (elaborato per secondo, sopra soglia) doveva usare tour_euristico"
    )
    assert not any(chiamata == ordini_milano_ids for chiamata in chiamate_esatto), (
        "il cluster Milano non doveva usare tour_esatto dopo il superamento della soglia"
    )
    assert not any(chiamata == ordini_ancona_ids for chiamata in chiamate_euristico), (
        "il cluster Ancona non doveva usare tour_euristico mentre era ancora sotto soglia"
    )

    # Il piano resta comunque coerente: nessun ordine perso, entrambi i cluster assegnati.
    assert len(piano.assegnazioni) == 2
    tutti_ordini_assegnati = {oid for a in piano.assegnazioni for oid in a.ordini_ids}
    assert tutti_ordini_assegnati == ordini_ancona_ids | ordini_milano_ids
    assert piano.ordini_non_assegnati == []


# --- Stress test: cluster troppo grande per una composizione, converge a un sottoinsieme valido ---


def test_calcola_piano_cluster_troppo_grande_per_durata_converge_a_sottoinsieme_valido(session_factory):
    with session_factory() as session:
        # Capacita' peso/volume ampiamente sufficiente per tutti e 4 gli ordini:
        # il vincolo stringente qui e' solo la durata.
        crea_flotta_semplice(session, "C1", peso_massimo=1000.0, volume_massimo=100.0)
        for i in range(4):
            session.add(crea_ordine(f"ORD-{i}", categoria=CategoriaConsegna.INCASSO, lat=43.6158, lon=13.5189))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    # 4x45min installazione = 180min > 120min budget; 3x45=135 ancora oltre;
    # 2x45=90 rientra: il sottoinsieme finale atteso ha quindi 2 ordini, non 0.
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0), durata_viaggio=timedelta(minutes=120))

    assert len(piano.assegnazioni) == 1
    assegnazione = piano.assegnazioni[0]
    assert len(assegnazione.ordini_ids) == 2
    assert len(piano.ordini_non_assegnati) == 2

    with session_factory() as session:
        ordini_assegnati = [session.get(Ordine, oid) for oid in assegnazione.ordini_ids]
        durata_effettiva = stima_durata_viaggio(ordini_assegnati, usa_esatto=True)
    assert durata_effettiva <= timedelta(minutes=120)


# --- Stress test: determinismo e idempotenza ---


def test_calcola_piano_e_deterministico_su_chiamate_ripetute(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=100.0, volume_massimo=10.0)
        crea_flotta_semplice(session, "C2", peso_massimo=100.0, volume_massimo=10.0)
        session.add(crea_ordine("ORD-ANCONA", peso=45.0, lat=43.6158, lon=13.5189))
        session.add(crea_ordine("ORD-FALCONARA", peso=45.0, lat=43.6167, lon=13.3833))
        session.add(crea_ordine("ORD-MILANO", peso=45.0, lat=45.4642, lon=9.1900))
        session.add(crea_ordine("ORD-PALERMO", peso=45.0, lat=38.1157, lon=13.3615))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)

    def normalizza(piano):
        return (
            frozenset((a.composizione_id, frozenset(a.ordini_ids)) for a in piano.assegnazioni),
            frozenset(piano.ordini_non_assegnati),
        )

    piano_1 = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))
    piano_2 = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    assert normalizza(piano_1) == normalizza(piano_2)


def test_calcola_piano_multi_giorno_idempotente_su_composizioni_e_ordini_gia_pianificati(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=100.0, volume_massimo=10.0)
        crea_flotta_semplice(session, "C2", peso_massimo=100.0, volume_massimo=10.0)
        session.add(crea_ordine("ORD-GIORNO1-A", peso=20.0))
        session.add(crea_ordine("ORD-GIORNO1-B", peso=20.0))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    ora_partenza_1 = datetime(2026, 7, 10, 8, 0)

    piano_1 = motore.calcola_piano(ora_partenza_1)
    assert len(piano_1.assegnazioni) >= 1
    composizioni_usate_giorno1 = {a.composizione_id for a in piano_1.assegnazioni}
    ordini_pianificati_giorno1 = {oid for a in piano_1.assegnazioni for oid in a.ordini_ids}

    motore.applica_piano(piano_1, ora_partenza_1)

    # Ripetere calcola_piano per lo STESSO giorno: le composizioni gia' usate
    # non devono ricomparire disponibili, e gli ordini gia' pianificati (ora
    # PIANIFICATO) non devono ricomparire tra i candidati.
    piano_1_bis = motore.calcola_piano(ora_partenza_1)

    assert not any(a.composizione_id in composizioni_usate_giorno1 for a in piano_1_bis.assegnazioni)
    assert not any(
        oid in ordini_pianificati_giorno1 for a in piano_1_bis.assegnazioni for oid in a.ordini_ids
    )
    assert not any(oid in ordini_pianificati_giorno1 for oid in piano_1_bis.ordini_non_assegnati)

    # Giorno 2: le composizioni tornano disponibili.
    ora_partenza_2 = datetime(2026, 7, 11, 8, 0)
    with session_factory() as session:
        session.add(crea_ordine("ORD-GIORNO2-A", peso=20.0))
        session.commit()

    piano_2 = motore.calcola_piano(ora_partenza_2)
    composizioni_usate_giorno2 = {a.composizione_id for a in piano_2.assegnazioni}
    assert composizioni_usate_giorno2 & composizioni_usate_giorno1


# --- Stress test: nessun ordine mai duplicato tra viaggi diversi dello stesso piano ---


def test_calcola_piano_nessun_ordine_assegnato_a_due_viaggi_diversi(session_factory):
    with session_factory() as session:
        for i in range(6):
            crea_flotta_semplice(session, f"C{i}", peso_massimo=60.0, volume_massimo=5.0)
        # Due cluster geografici distinti, con piu' ordini di quanti un solo
        # viaggio possa portare (peso 40 x2 > capacita' 60): forza calcola_piano
        # a usare piu' composizioni sullo stesso cluster.
        for i in range(4):
            session.add(crea_ordine(f"ORD-ANCONA-{i}", peso=40.0, lat=43.6158, lon=13.5189))
        for i in range(4):
            session.add(crea_ordine(f"ORD-MILANO-{i}", peso=40.0, lat=45.4642, lon=9.1900))
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))

    tutti_ordini_assegnati = [oid for a in piano.assegnazioni for oid in a.ordini_ids]
    assert len(tutti_ordini_assegnati) == len(set(tutti_ordini_assegnati))


# --- Stress test: scala realistica con verifica indipendente di tutti i vincoli ---

# Sopra questa taglia la forza bruta su tutte le permutazioni (n!) diventa
# impraticabile in un test (8! = 40320, gia' 9! richiederebbe ~9x piu' tempo).
LIMITE_BRUTE_FORCE_VERIFICA_INDIPENDENTE = 8


def _idoneo_indipendente(ordine, camion, dipendenti):
    """Reimplementazione da zero della regola di idoneita' (RF11), senza chiamare _ordine_idoneo."""
    if ordine.categoria_consegna == CategoriaConsegna.BIG:
        return camion.flg_sponda_idraulica
    if ordine.categoria_consegna == CategoriaConsegna.CERTIFICAZIONE_GAS:
        return any(dipendente.flg_certificazione_gas for dipendente in dipendenti)
    return True


def _distanza_sequenza(ordini_lista):
    totale = 0.0
    for a, b in zip(ordini_lista, ordini_lista[1:]):
        if a.lat is None or a.lon is None or b.lat is None or b.lon is None:
            totale += distanza_penalita_km()
        else:
            totale += distanza_km(a.lat, a.lon, b.lat, b.lon)
    return totale


def _tour_euristico_indipendente(ordini_viaggio):
    """Nearest-neighbor greedy scritto da zero per il test (non chiama tour_euristico)."""
    n = len(ordini_viaggio)
    if n <= 1:
        return list(ordini_viaggio)

    visitati = [False] * n
    visitati[0] = True
    percorso = [ordini_viaggio[0]]
    corrente = 0
    for _ in range(n - 1):
        migliore_j, migliore_d = None, None
        for j in range(n):
            if visitati[j]:
                continue
            a, b = ordini_viaggio[corrente], ordini_viaggio[j]
            d = (
                distanza_penalita_km()
                if a.lat is None or a.lon is None or b.lat is None or b.lon is None
                else distanza_km(a.lat, a.lon, b.lat, b.lon)
            )
            if migliore_d is None or d < migliore_d:
                migliore_j, migliore_d = j, d
        visitati[migliore_j] = True
        percorso.append(ordini_viaggio[migliore_j])
        corrente = migliore_j
    return percorso


def _distanza_tour_indipendente(ordini_viaggio):
    """Distanza del tour, calcolata senza chiamare tour_esatto/tour_euristico.

    Per gruppi piccoli prova tutte le permutazioni (minimo esatto, come farebbe
    Held-Karp ma per forza bruta). Per gruppi troppo grandi per la forza bruta,
    usa un nearest-neighbor greedy scritto da zero (algoritmo indipendente da
    quello di produzione, non la stessa funzione): resta un limite SUPERIORE
    valido sul tour ottimo (che e' per definizione il piu' corto fra tutte le
    permutazioni), quindi se la durata calcolata su questa approssimazione
    rientra nel budget, quella vera (minore o uguale) ci rientra a maggior
    ragione - ma a differenza di un ordine arbitrario resta abbastanza vicina
    all'ottimo da non produrre falsi negativi sui casi limite.
    """
    if len(ordini_viaggio) <= LIMITE_BRUTE_FORCE_VERIFICA_INDIPENDENTE:
        return min(
            _distanza_sequenza(list(permutazione)) for permutazione in itertools.permutations(ordini_viaggio)
        )
    return _distanza_sequenza(_tour_euristico_indipendente(ordini_viaggio))


def _durata_indipendente(ordini_viaggio):
    minuti_installazione = sum(
        modulo_stima_durata.TEMPO_INSTALLAZIONE_MINUTI[o.categoria_consegna] for o in ordini_viaggio
    )
    minuti_percorrenza = (
        _distanza_tour_indipendente(ordini_viaggio) / modulo_stima_durata.VELOCITA_MEDIA_KMH
    ) * 60
    return timedelta(minutes=minuti_installazione + minuti_percorrenza)


def test_calcola_piano_scala_realistica_rispetta_tutti_i_vincoli(session_factory):
    random.seed(2024)
    categorie = list(CategoriaConsegna)
    comuni_densi = [
        (43.6158, 13.5189),  # Ancona
        (43.6167, 13.3833),  # Falconara
        (43.3369, 12.9036),  # Fabriano
    ]

    with session_factory() as session:
        for i in range(20):
            crea_flotta_semplice(
                session,
                f"C{i}",
                peso_massimo=random.uniform(80.0, 300.0),
                volume_massimo=random.uniform(3.0, 12.0),
                sponda=(i % 3 == 0),
                gas=(i % 4 == 0),
            )

        for i in range(160):
            usa_coordinate = random.random() > 0.15
            if usa_coordinate:
                # 70% concentrati in pochi comuni densi, il resto sparso in Italia.
                if random.random() < 0.7:
                    lat, lon = random.choice(comuni_densi)
                else:
                    lat, lon = random.uniform(36.0, 47.0), random.uniform(7.0, 18.0)
            else:
                lat = lon = None
            session.add(
                crea_ordine(
                    f"ORD-{i}",
                    peso=random.uniform(5.0, 40.0),
                    volume=random.uniform(0.05, 1.5),
                    categoria=random.choice(categorie),
                    lat=lat,
                    lon=lon,
                )
            )
        session.commit()

    motore = MotoreOttimizzazione(session_factory)

    inizio = time.perf_counter()
    piano = motore.calcola_piano(datetime(2026, 7, 10, 8, 0))
    durata = time.perf_counter() - inizio

    print(f"\n[scala realistica] durata calcola_piano: {durata:.2f}s")
    assert durata < 180.0

    tutti_ordini_assegnati = [oid for a in piano.assegnazioni for oid in a.ordini_ids]
    assert len(tutti_ordini_assegnati) == len(set(tutti_ordini_assegnati))
    assert len(tutti_ordini_assegnati) + len(piano.ordini_non_assegnati) == 160

    # Verifica indipendente post-hoc: per OGNI viaggio del piano, ricalcolo qui
    # (senza fidarmi che l'algoritmo l'abbia gia' rispettato) peso, volume,
    # idoneita' e durata stimata.
    with session_factory() as session:
        composizioni_per_id = {c.id_composizione: c for c in session.scalars(select(ComposizioneSquadra))}
        for assegnazione in piano.assegnazioni:
            composizione = composizioni_per_id[assegnazione.composizione_id]
            camion = composizione.camion
            dipendenti = [composizione.dipendente_1, composizione.dipendente_2]
            ordini_viaggio = [session.get(Ordine, oid) for oid in assegnazione.ordini_ids]

            peso_totale = sum(o.peso for o in ordini_viaggio)
            volume_totale = sum(o.volume_cargo for o in ordini_viaggio)
            assert peso_totale <= camion.peso_massimo + 1e-6
            assert volume_totale <= camion.volume_massimo + 1e-6

            for ordine in ordini_viaggio:
                assert _idoneo_indipendente(ordine, camion, dipendenti)

            durata_indipendente = _durata_indipendente(ordini_viaggio)
            assert durata_indipendente <= timedelta(hours=8)
