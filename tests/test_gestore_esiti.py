from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from gestionale_logistica.database.enums import StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Allegato,
    CausaleFallimento,
    EsitoConsegna,
    Ordine,
    RegistroEsiti,
    ReportConsuntivo,
    Viaggio,
)
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
            data_creazione=data_partenza,
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
                data_creazione=datetime(2026, 7, 11, 8, 0),
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


# --- elenco_causali_fallimento ---


def test_elenco_causali_fallimento_vuoto_su_db_pulito(session_factory):
    gestore = GestoreRendicontazione(session_factory)
    assert gestore.elenco_causali_fallimento() == []


def test_elenco_causali_fallimento_ordinato_per_descrizione(session_factory):
    with session_factory() as session:
        _crea_causale(session, "IND_ERRATO", "Indirizzo non raggiungibile")
        _crea_causale(session, "CLIENTE_ASSENTE", "Cliente assente alla consegna")

    gestore = GestoreRendicontazione(session_factory)
    assert gestore.elenco_causali_fallimento() == [
        ("CLIENTE_ASSENTE", "Cliente assente alla consegna"),
        ("IND_ERRATO", "Indirizzo non raggiungibile"),
    ]


# --- elenca_esiti ---


def test_elenca_esiti_su_db_vuoto(session_factory):
    gestore = GestoreRendicontazione(session_factory)
    pagina = gestore.elenca_esiti()
    assert pagina.esiti == []
    assert pagina.totale == 0


def test_elenca_esiti_completato_senza_causale(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
    gestore = GestoreRendicontazione(session_factory)
    gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    pagina = gestore.elenca_esiti()

    assert pagina.totale == 1
    riga = pagina.esiti[0]
    assert riga.ordine_id == "O1"
    assert riga.esito == "Completato"
    assert riga.causale is None


def test_elenca_esiti_fallito_con_descrizione_causale(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
        _crea_causale(session, "CLIENTE_ASSENTE", "Cliente assente alla consegna")
    gestore = GestoreRendicontazione(session_factory)
    gestore.registra_esito("O1", StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE")

    pagina = gestore.elenca_esiti()

    assert pagina.esiti[0].esito == "Fallito"
    assert pagina.esiti[0].causale == "Cliente assente alla consegna"


def test_elenca_esiti_filtro_esito(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session, viaggio_id="V1", ordini_ids=("O1",))
        _crea_viaggio_con_ordini(session, comp_id="C2", viaggio_id="V2", ordini_ids=("O2",))
        _crea_causale(session)
    gestore = GestoreRendicontazione(session_factory)
    gestore.registra_esito("O1", StatoEsito.COMPLETATO)
    gestore.registra_esito("O2", StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE")

    solo_completati = gestore.elenca_esiti(filtro_esito="Completato").esiti
    solo_falliti = gestore.elenca_esiti(filtro_esito="Fallito").esiti

    assert [r.ordine_id for r in solo_completati] == ["O1"]
    assert [r.ordine_id for r in solo_falliti] == ["O2"]


def test_elenca_esiti_ricerca_su_cliente_id_e_causale(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session, viaggio_id="V1", ordini_ids=("O1",))
        _crea_causale(session, "CLIENTE_ASSENTE", "Cliente assente alla consegna")
    gestore = GestoreRendicontazione(session_factory)
    gestore.registra_esito("O1", StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE")

    assert [r.ordine_id for r in gestore.elenca_esiti(ricerca="o1").esiti] == ["O1"]
    assert [r.ordine_id for r in gestore.elenca_esiti(ricerca="assente").esiti] == ["O1"]
    assert gestore.elenca_esiti(ricerca="nessuno").esiti == []


def test_elenca_esiti_ordinati_per_data_registrazione_decrescente(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(
            session, viaggio_id="V1", ordini_ids=("O1",), data_partenza=datetime(2026, 7, 10, 8, 0)
        )
        _crea_viaggio_con_ordini(
            session, comp_id="C2", viaggio_id="V2", ordini_ids=("O2",),
            data_partenza=datetime(2026, 7, 11, 8, 0),
        )
    gestore = GestoreRendicontazione(session_factory)
    gestore.registra_esito("O1", StatoEsito.COMPLETATO)
    gestore.registra_esito("O2", StatoEsito.COMPLETATO)

    assert [r.ordine_id for r in gestore.elenca_esiti().esiti] == ["O2", "O1"]


# --- modifica_esito ---


def test_modifica_esito_cambia_causale_restando_fallito(session_factory):
    esito_id = _crea_esito_fallito(session_factory)
    with session_factory() as session:
        _crea_causale(session, "IND_ERRATO", "Indirizzo non raggiungibile")

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.modifica_esito(esito_id, StatoEsito.FALLITO, causale_codice="IND_ERRATO")

    assert risultato.ok
    with session_factory() as session:
        esito = session.get(EsitoConsegna, esito_id)
        assert esito.causale_id == "IND_ERRATO"
        assert session.get(Ordine, "O1").stato_ordine == StatoOrdine.RICEVUTO


def test_modifica_esito_completato_a_fallito(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
        _crea_causale(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato_iniziale = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    risultato = gestore.modifica_esito(
        risultato_iniziale.esito_id, StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE"
    )

    assert risultato.ok
    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO
        assert ordine.viaggio_id is None
        assert session.get(EsitoConsegna, risultato_iniziale.esito_id).stato_esito == StatoEsito.FALLITO


def test_modifica_esito_completato_a_fallito_senza_causale_rifiutato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato_iniziale = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    risultato = gestore.modifica_esito(risultato_iniziale.esito_id, StatoEsito.FALLITO)

    assert not risultato.ok
    assert "Causale" in risultato.motivo


def test_modifica_esito_fallito_a_completato(session_factory):
    esito_id = _crea_esito_fallito(session_factory)

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.modifica_esito(esito_id, StatoEsito.COMPLETATO)

    assert risultato.ok
    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        assert ordine.stato_ordine == StatoOrdine.COMPLETATO
        assert ordine.viaggio_id == "V1"
        esito = session.get(EsitoConsegna, esito_id)
        assert esito.stato_esito == StatoEsito.COMPLETATO
        assert esito.causale_id is None


def test_modifica_esito_completato_a_fallito_rifiutato_se_ordine_cambiato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
        _crea_causale(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato_iniziale = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    with session_factory() as session:
        # Simula un intervento manuale successivo sull'ordine (non dovrebbe succedere via
        # backend per un ordine gia' Completato, ma la guardia deve reggere comunque).
        ordine = session.get(Ordine, "O1")
        ordine.stato_ordine = StatoOrdine.PIANIFICATO
        session.commit()

    risultato = gestore.modifica_esito(
        risultato_iniziale.esito_id, StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE"
    )

    assert not risultato.ok
    assert "cambiato" in risultato.motivo


def test_modifica_esito_fallito_a_completato_rifiutato_se_ordine_ripianificato(session_factory):
    esito_id = _crea_esito_fallito(session_factory)
    with session_factory() as session:
        # RF17 lo ha gia' rimesso RICEVUTO/senza viaggio; simula una successiva ripianificazione.
        ordine = session.get(Ordine, "O1")
        ordine.stato_ordine = StatoOrdine.PIANIFICATO
        ordine.viaggio_id = "V1"
        session.commit()

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.modifica_esito(esito_id, StatoEsito.COMPLETATO)

    assert not risultato.ok
    assert "ripianificato" in risultato.motivo


def test_modifica_esito_inesistente_rifiutato(session_factory):
    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.modifica_esito(999, StatoEsito.COMPLETATO)
    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_modifica_esito_rifiutato_se_report_gia_generato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato_iniziale = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    with session_factory() as session:
        esito = session.get(EsitoConsegna, risultato_iniziale.esito_id)
        session.add(ReportConsuntivo(
            data_generazione=datetime.now(), ordini_consegnati=1, ordini_falliti=0,
            formato_output="pdf", negozi_partner="Test", percorso_file="report/test.pdf",
            registro_id=esito.registro_id,
        ))
        session.commit()

    risultato = gestore.modifica_esito(risultato_iniziale.esito_id, StatoEsito.FALLITO, causale_codice=None)

    assert not risultato.ok
    assert "report" in risultato.motivo.lower()


# --- elimina_esito ---


def test_elimina_esito_completato_ripristina_pianificato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato_iniziale = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    risultato = gestore.elimina_esito(risultato_iniziale.esito_id)

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Ordine, "O1").stato_ordine == StatoOrdine.PIANIFICATO
        assert session.get(EsitoConsegna, risultato_iniziale.esito_id) is None


def test_elimina_esito_fallito_non_tocca_ordine_gia_ripianificato(session_factory):
    esito_id = _crea_esito_fallito(session_factory)
    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        ordine.stato_ordine = StatoOrdine.PIANIFICATO
        ordine.viaggio_id = "V1"
        session.commit()

    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.elimina_esito(esito_id)

    assert risultato.ok
    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        assert ordine.stato_ordine == StatoOrdine.PIANIFICATO
        assert ordine.viaggio_id == "V1"


def test_elimina_esito_rimuove_allegati_e_cartella(session_factory, tmp_path):
    esito_id = _crea_esito_fallito(session_factory)
    cartella_allegati = tmp_path / "allegati"
    gestore = GestoreRendicontazione(session_factory, cartella_allegati=cartella_allegati)

    sorgente = tmp_path / "prova.jpg"
    sorgente.write_bytes(b"contenuto foto")
    assert gestore.carica_prova_documentale(esito_id, "prova.jpg", str(sorgente), "image/jpeg").ok
    assert (cartella_allegati / str(esito_id)).is_dir()

    risultato = gestore.elimina_esito(esito_id)

    assert risultato.ok
    with session_factory() as session:
        assert session.scalars(select(Allegato).where(Allegato.esito_id == esito_id)).all() == []
    assert not (cartella_allegati / str(esito_id)).exists()


def test_elimina_esito_inesistente_rifiutato(session_factory):
    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.elimina_esito(999)
    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_elimina_esito_completato_rifiutato_se_ordine_cambiato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato_iniziale = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    with session_factory() as session:
        ordine = session.get(Ordine, "O1")
        ordine.stato_ordine = StatoOrdine.PIANIFICATO
        session.commit()

    risultato = gestore.elimina_esito(risultato_iniziale.esito_id)

    assert not risultato.ok
    assert "cambiato" in risultato.motivo


def test_elimina_esito_rifiutato_se_report_gia_generato(session_factory):
    with session_factory() as session:
        _crea_viaggio_con_ordini(session)
    gestore = GestoreRendicontazione(session_factory)
    risultato_iniziale = gestore.registra_esito("O1", StatoEsito.COMPLETATO)

    with session_factory() as session:
        esito = session.get(EsitoConsegna, risultato_iniziale.esito_id)
        session.add(ReportConsuntivo(
            data_generazione=datetime.now(), ordini_consegnati=1, ordini_falliti=0,
            formato_output="pdf", negozi_partner="Test", percorso_file="report/test.pdf",
            registro_id=esito.registro_id,
        ))
        session.commit()

    risultato = gestore.elimina_esito(risultato_iniziale.esito_id)

    assert not risultato.ok
    assert "report" in risultato.motivo.lower()


# --- elenco_allegati ---


def test_elenco_allegati_vuoto_su_esito_senza_prove(session_factory):
    esito_id = _crea_esito_fallito(session_factory)
    gestore = GestoreRendicontazione(session_factory)

    assert gestore.elenco_allegati(esito_id) == []


def test_elenco_allegati_multipli_in_ordine_di_caricamento(session_factory, tmp_path):
    esito_id = _crea_esito_fallito(session_factory)
    gestore = GestoreRendicontazione(session_factory, cartella_allegati=tmp_path / "allegati")

    prima = tmp_path / "prima.jpg"
    prima.write_bytes(b"1")
    seconda = tmp_path / "seconda.jpg"
    seconda.write_bytes(b"2")
    gestore.carica_prova_documentale(esito_id, "prima.jpg", str(prima), "image/jpeg")
    gestore.carica_prova_documentale(esito_id, "seconda.jpg", str(seconda), "image/jpeg")

    allegati = gestore.elenco_allegati(esito_id)

    assert [a.nome_file for a in allegati] == ["prima.jpg", "seconda.jpg"]
