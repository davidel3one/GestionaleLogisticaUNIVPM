from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from gestionale_logistica.database.enums import StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Allegato, CausaleFallimento, Ordine, RegistroEsiti, Viaggio
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione
from test_logistica import crea_flotta_semplice, crea_ordine


def _crea_viaggio_con_ordini(
    session,
    comp_id="C1",
    viaggio_id="V1",
    stato=StatoViaggio.IN_CORSO,
    data_partenza=datetime(2026, 7, 10, 8, 0),
    ordini_ids=("O1",),
):
    """Helper minimo: crea una flotta valida, un Viaggio nello stato richiesto e vi aggancia
    gli ordini indicati (gia' in stato PIANIFICATO, come farebbe RF10/RF11 prima del transito).
    """
    crea_flotta_semplice(session, comp_id)
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
        ordine.stato_ordine = StatoOrdine.PIANIFICATO
        session.add(ordine)
    session.commit()
    return viaggio_id


def _crea_causale(session, codice="CLIENTE_ASSENTE", descrizione="Cliente assente"):
    session.add(CausaleFallimento(codice=codice, descrizione=descrizione))
    session.commit()
    return codice


# --- registra_esito: happy path ---


def test_registra_esito_completato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    assert risultato.ok
    assert risultato.esito_id is not None
    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        assert ordine.stato_ordine == StatoOrdine.COMPLETATO
        assert ordine.data_consegna is not None
        assert ordine.viaggio_id == "V1"


def test_registra_esito_fallito_rimette_ordine_disponibile(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
        _crea_causale(session)

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("O1", StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE")

    assert risultato.ok
    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO
        assert ordine.viaggio_id is None
        assert ordine.data_consegna is not None


# --- registra_esito: validazioni ---


def test_registra_esito_ordine_inesistente_rifiutato(session_factory):
    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("INESISTENTE", StatoEsito.COMPLETATO)
    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_registra_esito_gia_presente_rifiutato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)

    gestore = GestoreRendicontazione(session_factory)
    assert gestore.registra_esito("O1", StatoEsito.COMPLETATO).ok

    risultato = gestore.registra_esito("O1", StatoEsito.COMPLETATO)
    assert not risultato.ok
    assert "gia'" in risultato.motivo


def test_registra_esito_viaggio_non_in_corso_rifiutato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session, stato=StatoViaggio.PIANIFICATO)

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("O1", StatoEsito.COMPLETATO)
    assert not risultato.ok
    assert "viaggio in corso" in risultato.motivo


def test_registra_esito_fallito_senza_causale_rifiutato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("O1", StatoEsito.FALLITO)
    assert not risultato.ok
    assert "Causale obbligatoria" in risultato.motivo


def test_registra_esito_fallito_causale_inesistente_rifiutato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("O1", StatoEsito.FALLITO, causale_codice="INESISTENTE")
    assert not risultato.ok
    assert "non trovata" in risultato.motivo


# --- Regressione pre-mortem: RegistroEsiti raggruppa per partenza del viaggio, non per oggi ---


def test_registro_esiti_usa_data_partenza_viaggio_non_data_odierna(session_factory):
    data_partenza = datetime(2026, 7, 10, 8, 0)  # nel passato rispetto a "oggi" (2026-07-12)
    with session_factory() as session:
        _crea_viaggio_con_ordini(session, data_partenza=data_partenza)

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("O1", StatoEsito.COMPLETATO)
    assert risultato.ok

    with session_factory() as session:
        registri = session.scalars(select(RegistroEsiti)).all()
        assert len(registri) == 1
        assert registri[0].data_riferimento == datetime(2026, 7, 10)


# --- End-to-end RF16 -> RF17: l'ordine Fallito ricade nel filtro usato da MotoreOttimizzazione ---


def test_ordine_fallito_soddisfa_filtro_candidati_motore_ottimizzazione(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
        _crea_causale(session)

    gestore = GestoreRendicontazione(session_factory)
    assert gestore.registra_esito("O1", StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE").ok

    with session_factory() as session:
        candidati = session.scalars(
            select(Ordine).where(
                Ordine.stato_ordine == StatoOrdine.RICEVUTO,
                Ordine.viaggio_id.is_(None),
            )
        ).all()
        assert [o.id for o in candidati] == ["O1"]


# --- Regressione bug schema: un ordine ripianificato (RF17) accetta un SECONDO esito ---


def test_secondo_esito_dopo_ripianificazione_su_nuovo_viaggio(session_factory):
    # Prima del fix (unique su EsitoConsegna.ordine_id + guard su ordine.esito) questo secondo
    # registra_esito veniva rifiutato con "gia' associato a un esito" e l'ordine restava bloccato.
    with session_factory() as session:
        _crea_viaggio_con_ordini(session, comp_id="C1", viaggio_id="V1")
        _crea_causale(session)

    gestore = GestoreRendicontazione(session_factory)
    assert gestore.registra_esito("O1", StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE").ok

    with session_factory() as session:
        crea_flotta_semplice(session, "C2")
        session.add(
            Viaggio(
                id="V2",
                data_partenza_prevista=datetime(2026, 7, 11, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 11, 16, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.IN_CORSO,
                composizione_id="C2",
            )
        )
        ordine = session.get(Ordine, "O1")
        ordine.viaggio_id = "V2"
        ordine.stato_ordine = StatoOrdine.IN_CONSEGNA
        session.commit()

    risultato = gestore.registra_esito("O1", StatoEsito.COMPLETATO)
    assert risultato.ok, risultato.motivo

    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        assert ordine.stato_ordine == StatoOrdine.COMPLETATO
        assert ordine.viaggio_id == "V2"
        assert {e.viaggio_id for e in ordine.esiti} == {"V1", "V2"}


# --- carica_prova_documentale ---


def _crea_esito_fallito(session_factory, viaggio_id="V1", ordine_id="O1"):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session, viaggio_id=viaggio_id, ordini_ids=(ordine_id,))
        _crea_causale(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito(ordine_id, StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE")
    assert risultato.ok
    return risultato.esito_id


def test_carica_prova_documentale_happy_path(session_factory, tmp_path):
    esito_id = _crea_esito_fallito(session_factory)

    sorgente = tmp_path / "prova.jpg"
    sorgente.write_bytes(b"contenuto foto")
    cartella_allegati = tmp_path / "allegati"

    gestore = GestoreRendicontazione(session_factory, cartella_allegati=cartella_allegati)
    risultato = gestore.carica_prova_documentale(esito_id, "prova.jpg", str(sorgente), "image/jpeg")

    assert risultato.ok
    with session_factory() as session:
        allegato = session.scalar(select(Allegato).where(Allegato.esito_id == esito_id))
        assert allegato is not None
        percorso_copia = allegato.percorso_file
    copia = Path(percorso_copia)
    assert copia.is_file()
    assert copia.read_bytes() == b"contenuto foto"


def test_carica_prova_documentale_esito_inesistente_rifiutato(session_factory, tmp_path):
    sorgente = tmp_path / "prova.jpg"
    sorgente.write_bytes(b"x")

    gestore = GestoreRendicontazione(session_factory, cartella_allegati=tmp_path / "allegati")
    risultato = gestore.carica_prova_documentale(999, "prova.jpg", str(sorgente), "image/jpeg")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_carica_prova_documentale_esito_completato_rifiutato(session_factory, tmp_path):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
    gestore = GestoreRendicontazione(session_factory, cartella_allegati=tmp_path / "allegati")
    risultato_esito = gestore.registra_esito("O1", StatoEsito.COMPLETATO)
    assert risultato_esito.ok

    sorgente = tmp_path / "prova.jpg"
    sorgente.write_bytes(b"x")
    risultato = gestore.carica_prova_documentale(risultato_esito.esito_id, "prova.jpg", str(sorgente), "image/jpeg")

    assert not risultato.ok
    assert "Fallito" in risultato.motivo


def test_carica_prova_documentale_file_sorgente_inesistente_rifiutato(session_factory, tmp_path):
    esito_id = _crea_esito_fallito(session_factory)

    gestore = GestoreRendicontazione(session_factory, cartella_allegati=tmp_path / "allegati")
    risultato = gestore.carica_prova_documentale(
        esito_id, "prova.jpg", str(tmp_path / "non_esiste.jpg"), "image/jpeg"
    )

    assert not risultato.ok
    assert "File non trovato" in risultato.motivo


# --- Regressione pre-mortem: la copia sopravvive alla cancellazione del file sorgente ---


def test_prova_documentale_sopravvive_a_cancellazione_file_sorgente(session_factory, tmp_path):
    esito_id = _crea_esito_fallito(session_factory)

    sorgente = tmp_path / "prova.jpg"
    sorgente.write_bytes(b"contenuto foto")
    cartella_allegati = tmp_path / "allegati"

    gestore = GestoreRendicontazione(session_factory, cartella_allegati=cartella_allegati)
    risultato = gestore.carica_prova_documentale(esito_id, "prova.jpg", str(sorgente), "image/jpeg")
    assert risultato.ok

    with session_factory() as session:
        percorso_copia = session.scalar(select(Allegato).where(Allegato.esito_id == esito_id)).percorso_file

    sorgente.unlink()

    copia = Path(percorso_copia)
    assert copia.is_file()
    assert copia.read_bytes() == b"contenuto foto"


# --- Regressione code review: nome_file non deve permettere di uscire da cartella_allegati ---


def test_carica_prova_documentale_nome_file_con_traversal_resta_confinato(session_factory, tmp_path):
    esito_id = _crea_esito_fallito(session_factory)

    sorgente = tmp_path / "prova.jpg"
    sorgente.write_bytes(b"contenuto foto")
    cartella_allegati = tmp_path / "allegati"

    gestore = GestoreRendicontazione(session_factory, cartella_allegati=cartella_allegati)
    risultato = gestore.carica_prova_documentale(
        esito_id, "../../../etc/passwd", str(sorgente), "image/jpeg"
    )

    assert risultato.ok
    with session_factory() as session:
        percorso_copia = session.scalar(select(Allegato).where(Allegato.esito_id == esito_id)).percorso_file
    copia = Path(percorso_copia)
    assert copia.is_relative_to(cartella_allegati)
    assert copia.name.endswith("_passwd")


def test_carica_prova_documentale_nome_file_duplicato_non_sovrascrive(session_factory, tmp_path):
    esito_id = _crea_esito_fallito(session_factory)
    cartella_allegati = tmp_path / "allegati"
    gestore = GestoreRendicontazione(session_factory, cartella_allegati=cartella_allegati)

    prima = tmp_path / "prova.jpg"
    prima.write_bytes(b"prima foto")
    assert gestore.carica_prova_documentale(esito_id, "prova.jpg", str(prima), "image/jpeg").ok

    seconda = tmp_path / "seconda_sorgente.jpg"
    seconda.write_bytes(b"seconda foto")
    assert gestore.carica_prova_documentale(esito_id, "prova.jpg", str(seconda), "image/jpeg").ok

    with session_factory() as session:
        allegati = session.scalars(select(Allegato).where(Allegato.esito_id == esito_id)).all()
        percorsi = [Path(a.percorso_file) for a in allegati]

    assert len(percorsi) == 2
    assert len({p.resolve() for p in percorsi}) == 2
    assert {p.read_bytes() for p in percorsi} == {b"prima foto", b"seconda foto"}
