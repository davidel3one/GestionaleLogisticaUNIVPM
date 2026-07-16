from datetime import date, datetime

from gestionale_logistica.gui.pianificazione.pianificazione_data import (
    giorni_con_composizioni_disponibili,
)
from test_logistica import crea_flotta_semplice, crea_ordine


def test_giorni_con_composizioni_disponibili_segna_i_giorni_validi(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(
            session,
            "C1",
            data_inizio=datetime(2026, 7, 10),
            data_fine=datetime(2026, 7, 20),
        )
        session.commit()

    giorni = giorni_con_composizioni_disponibili(date(2026, 7, 1), session_factory)

    assert date(2026, 7, 10) in giorni
    assert date(2026, 7, 20) in giorni
    assert date(2026, 7, 9) not in giorni
    assert date(2026, 7, 21) not in giorni


def test_giorni_con_composizioni_disponibili_esclude_composizioni_non_attive(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(
            session,
            "C1",
            data_inizio=datetime(2026, 7, 1),
            data_fine=None,
            attiva=False,
        )
        session.commit()

    giorni = giorni_con_composizioni_disponibili(date(2026, 7, 1), session_factory)

    assert giorni == set()


def test_giorni_con_composizioni_disponibili_esclude_giorno_gia_occupato(session_factory):
    from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica

    with session_factory() as session:
        crea_flotta_semplice(session, "C1", data_inizio=datetime(2026, 7, 1), data_fine=None)
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 15, 8, 0))
    assert avvio.ok

    giorni = giorni_con_composizioni_disponibili(date(2026, 7, 1), session_factory)

    # L'unica squadra e' gia' impegnata il 15/07 su un viaggio: quel giorno non ha piu'
    # composizioni disponibili, ma i giorni adiacenti si' (stessa composizione, non occupata).
    assert date(2026, 7, 15) not in giorni
    assert date(2026, 7, 14) in giorni
