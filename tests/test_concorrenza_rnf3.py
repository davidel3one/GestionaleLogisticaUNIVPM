import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.concorrenza import esegui_in_background
from gestionale_logistica.database.base import Base
from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine
from gestionale_logistica.database.models import Dipendente, Ordine
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import MotoreOttimizzazione

DATI_ESEMPIO = Path(__file__).parent.parent / "dati_esempio"


def test_esegui_in_background_gira_su_un_thread_diverso_dal_chiamante():
    thread_chiamante = threading.get_ident()

    future = esegui_in_background(threading.get_ident)

    assert future.result(timeout=5) != thread_chiamante


def test_esegui_in_background_propaga_il_risultato():
    future = esegui_in_background(lambda: 21 * 2)

    assert future.result(timeout=5) == 42


def test_esegui_in_background_propaga_le_eccezioni():
    def esplode():
        raise ValueError("boom")

    future = esegui_in_background(esplode)

    try:
        future.result(timeout=5)
        assert False, "doveva sollevare ValueError"
    except ValueError as errore:
        assert str(errore) == "boom"


def test_importa_ordini_async_produce_lo_stesso_risultato_della_versione_sincrona(session_factory):
    thread_chiamante = threading.get_ident()
    thread_esecuzione = []

    gestore = GestoreLogistica(session_factory)
    percorso = DATI_ESEMPIO / "Ordini_Unieuro_20260706.csv"

    def importa_e_registra_thread():
        thread_esecuzione.append(threading.get_ident())
        return gestore.importa_ordini(percorso)

    future = esegui_in_background(importa_e_registra_thread)
    risultato = future.result(timeout=30)

    assert risultato.ordini_creati == 30
    assert risultato.errori == []
    assert thread_esecuzione[0] != thread_chiamante

    with session_factory() as session:
        assert session.get(Ordine, "UNI-2026-0001") is not None


def test_importa_ordini_async_ritorna_una_future_utilizzabile(session_factory):
    gestore = GestoreLogistica(session_factory)

    future = gestore.importa_ordini_async(DATI_ESEMPIO / "Ordini_Unieuro_20260706.csv")
    risultato = future.result(timeout=30)

    assert risultato.ordini_creati == 30


def test_calcola_piano_async_produce_lo_stesso_risultato_della_versione_sincrona(session_factory):
    with session_factory() as session:
        session.add(
            Ordine(
                id="ORD-1",
                indirizzo="Via Test 1",
                comune="Ancona",
                provincia="AN",
                lat=None,
                lon=None,
                cliente="Cliente Test",
                peso=10.0,
                volume_cargo=0.1,
                categoria_consegna=CategoriaConsegna.BORDO_STRADA,
                stato_ordine=StatoOrdine.RICEVUTO,
                data_consegna=None,
                viaggio_id=None,
            )
        )
        session.commit()

    motore = MotoreOttimizzazione(session_factory)
    ora_partenza = datetime(2026, 7, 10, 8, 0)

    future = motore.calcola_piano_async(ora_partenza)
    piano = future.result(timeout=30)

    assert piano.assegnazioni == []
    assert piano.ordini_non_assegnati == ["ORD-1"]


def test_engine_sqlite_su_file_e_utilizzabile_da_piu_worker_thread(tmp_path):
    # Stessa configurazione di database/base.py (sqlite su file, non ":memory:", con
    # connect_args={"check_same_thread": False}): a differenza dei test con l'engine ":memory:"
    # + StaticPool di conftest.py, qui la sessionmaker di produzione (QueuePool) puo' assegnare a
    # un worker thread una connessione fisica aperta in precedenza da un thread diverso -
    # senza check_same_thread=False pysqlite la rifiuterebbe. Regressione per il fix in base.py.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rnf3.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def scrivi_su_un_thread():
        with session_factory() as session:
            session.add(
                Dipendente(
                    id="D1",
                    nome="Nome",
                    cognome="Cognome",
                    codice_fiscale="CF-D1",
                    data_assunzione=datetime(2020, 1, 1),
                    data_licenziamento=None,
                    flg_attivo=True,
                    flg_certificazione_gas=False,
                )
            )
            session.commit()

    def leggi_su_un_altro_thread():
        with session_factory() as session:
            return session.scalar(select(Dipendente).where(Dipendente.id == "D1"))

    esegui_in_background(scrivi_su_un_thread).result(timeout=5)
    dipendente = esegui_in_background(leggi_su_un_altro_thread).result(timeout=5)

    assert dipendente is not None
    assert dipendente.id == "D1"
