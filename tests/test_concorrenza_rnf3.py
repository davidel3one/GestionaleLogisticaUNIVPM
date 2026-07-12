import logging
import threading
from datetime import datetime
from pathlib import Path

from gestionale_logistica.concorrenza import esegui_in_background
from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine
from gestionale_logistica.database.models import Ordine
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import MotoreOttimizzazione

DATI_ESEMPIO = Path(__file__).parent.parent / "dati_esempio"


def test_operazioni_sequenziali_condividono_lo_stesso_worker_thread_e_vedono_lo_stato_scritto():
    # Proprieta' da cui dipende in produzione l'uso di SessionLocal (database/base.py) dai worker
    # RNF3: due submit distinti a esegui_in_background, il secondo dopo il .result() del primo,
    # devono girare in modo coerente (stesso worker, con max_workers=1) e lo stato scritto dal
    # primo deve essere visibile al secondo. Verificata qui con un dict Python in memoria, non con
    # un database reale, cosi' il test resta indipendente da SQLite/SQLAlchemy.
    archivio: dict[str, object] = {}

    def scrivi():
        archivio["thread"] = threading.get_ident()
        archivio["valore"] = "scritto dal primo worker"

    def leggi():
        return archivio.get("thread"), archivio.get("valore")

    esegui_in_background(scrivi).result(timeout=5)
    thread_scrittura, valore_letto = esegui_in_background(leggi).result(timeout=5)

    assert valore_letto == "scritto dal primo worker"
    assert thread_scrittura == esegui_in_background(threading.get_ident).result(timeout=5)


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


def test_eccezione_non_recuperata_viene_comunque_loggata(caplog):
    # concurrent.futures, a differenza di asyncio, non segnala mai un'eccezione rimasta in una
    # Future il cui .result() non viene chiamato: senza il done_callback di esegui_in_background
    # questo test fallirebbe (nessun log), pur non sollevando alcun errore visibile.
    def esplode():
        raise ValueError("boom mai raccolto")

    completata = threading.Event()

    with caplog.at_level(logging.ERROR, logger="gestionale_logistica.concorrenza"):
        future = esegui_in_background(esplode)
        future.add_done_callback(lambda f: completata.set())
        assert completata.wait(timeout=5)

    assert any("Operazione in background fallita" in r.message for r in caplog.records)


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
