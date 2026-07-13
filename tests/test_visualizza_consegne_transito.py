from datetime import datetime, timedelta

from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Viaggio
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione
from test_logistica import crea_flotta_semplice, crea_ordine


def _crea_viaggio(session, comp_id, viaggio_id, stato, ordini_ids=()):
    crea_flotta_semplice(session, comp_id)
    data_partenza = datetime(2026, 7, 10, 8, 0)
    session.add(
        Viaggio(
            id=viaggio_id,
            data_partenza_prevista=data_partenza,
            data_arrivo_prevista=data_partenza + timedelta(hours=8),
            km_percorsi=None,
            stato_viaggio=stato,
            composizione_id=comp_id,
        )
    )
    for ordine_id in ordini_ids:
        ordine = crea_ordine(ordine_id)
        ordine.viaggio_id = viaggio_id
        session.add(ordine)
    session.commit()


def test_elenca_db_vuoto(session_factory):
    vista = GestoreRendicontazione(session_factory)
    assert vista.elenca_consegne_in_transito() == []


def test_elenca_solo_viaggi_in_corso(session_factory):
    with session_factory() as session:
        _crea_viaggio(session, "C1", "V1", StatoViaggio.IN_CORSO, ordini_ids=("O1",))
        _crea_viaggio(session, "C2", "V2", StatoViaggio.PIANIFICATO, ordini_ids=("O2",))
        _crea_viaggio(session, "C3", "V3", StatoViaggio.COMPLETATO, ordini_ids=("O3",))
        _crea_viaggio(session, "C4", "V4", StatoViaggio.IN_COMPOSIZIONE, ordini_ids=("O4",))

    vista = GestoreRendicontazione(session_factory)
    risultato = vista.elenca_consegne_in_transito()

    assert [v.id for v in risultato] == ["V1"]


def test_elenca_viaggio_in_corso_con_piu_ordini(session_factory):
    with session_factory() as session:
        _crea_viaggio(session, "C1", "V1", StatoViaggio.IN_CORSO, ordini_ids=("O1", "O2"))

    vista = GestoreRendicontazione(session_factory)
    risultato = vista.elenca_consegne_in_transito()

    assert len(risultato) == 1
    viaggio = risultato[0]
    assert viaggio.id == "V1"
    assert viaggio.data_partenza_prevista == datetime(2026, 7, 10, 8, 0)
    assert {o.id for o in viaggio.ordini} == {"O1", "O2"}

    ordine = next(o for o in viaggio.ordini if o.id == "O1")
    assert ordine.cliente == "Cliente Test"
    assert ordine.indirizzo == "Via Test 1"
    assert ordine.comune == "Ancona"
