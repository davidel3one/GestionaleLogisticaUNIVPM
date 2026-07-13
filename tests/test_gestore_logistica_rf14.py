from datetime import datetime, timedelta

from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Viaggio
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica


def crea_viaggio(id_, stato, data_partenza_prevista, composizione_id="C1"):
    return Viaggio(
        id=id_,
        data_partenza_prevista=data_partenza_prevista,
        data_arrivo_prevista=data_partenza_prevista + timedelta(hours=8),
        km_percorsi=None,
        stato_viaggio=stato,
        composizione_id=composizione_id,
    )


def test_viaggio_pianificato_con_partenza_scaduta_passa_a_in_corso(session_factory):
    with session_factory() as session:
        session.add(crea_viaggio("V-1", StatoViaggio.PIANIFICATO, datetime(2026, 7, 20, 8, 0)))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avviati = gestore.verifica_partenze(ora_riferimento=datetime(2026, 7, 20, 8, 1))

    assert avviati == ["V-1"]
    with session_factory() as session:
        assert session.get(Viaggio, "V-1").stato_viaggio == StatoViaggio.IN_CORSO


def test_viaggio_pianificato_con_partenza_futura_non_viene_toccato(session_factory):
    with session_factory() as session:
        session.add(crea_viaggio("V-1", StatoViaggio.PIANIFICATO, datetime(2026, 7, 20, 8, 0)))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avviati = gestore.verifica_partenze(ora_riferimento=datetime(2026, 7, 20, 7, 59))

    assert avviati == []
    with session_factory() as session:
        assert session.get(Viaggio, "V-1").stato_viaggio == StatoViaggio.PIANIFICATO


def test_viaggio_in_composizione_con_partenza_scaduta_non_viene_toccato(session_factory):
    # Una bozza (IN_COMPOSIZIONE) non e' "partita": deve restare modificabile finche' non
    # viene chiusa esplicitamente (RF10), anche se la data_partenza_prevista e' nel passato.
    with session_factory() as session:
        session.add(crea_viaggio("V-1", StatoViaggio.IN_COMPOSIZIONE, datetime(2026, 7, 20, 8, 0)))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avviati = gestore.verifica_partenze(ora_riferimento=datetime(2026, 7, 20, 9, 0))

    assert avviati == []
    with session_factory() as session:
        assert session.get(Viaggio, "V-1").stato_viaggio == StatoViaggio.IN_COMPOSIZIONE


def test_viaggio_gia_in_corso_non_riprocessato(session_factory):
    with session_factory() as session:
        session.add(crea_viaggio("V-1", StatoViaggio.IN_CORSO, datetime(2026, 7, 20, 8, 0)))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avviati = gestore.verifica_partenze(ora_riferimento=datetime(2026, 7, 20, 9, 0))

    assert avviati == []


def test_piu_viaggi_scaduti_vengono_avviati_insieme(session_factory):
    with session_factory() as session:
        session.add(crea_viaggio("V-1", StatoViaggio.PIANIFICATO, datetime(2026, 7, 20, 8, 0)))
        session.add(crea_viaggio("V-2", StatoViaggio.PIANIFICATO, datetime(2026, 7, 20, 8, 30)))
        session.add(crea_viaggio("V-3", StatoViaggio.PIANIFICATO, datetime(2026, 7, 20, 20, 0)))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avviati = gestore.verifica_partenze(ora_riferimento=datetime(2026, 7, 20, 9, 0))

    assert set(avviati) == {"V-1", "V-2"}
    with session_factory() as session:
        assert session.get(Viaggio, "V-3").stato_viaggio == StatoViaggio.PIANIFICATO
