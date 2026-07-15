from datetime import datetime, timedelta

from sqlalchemy import select

from gestionale_logistica.database.enums import CategoriaConsegna, StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import CausaleFallimento, Ordine, ReportConsuntivo, Viaggio
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione


def crea_viaggio(id_, data_partenza_prevista, composizione_id="C1"):
    return Viaggio(
        id=id_,
        data_partenza_prevista=data_partenza_prevista,
        data_arrivo_prevista=data_partenza_prevista + timedelta(hours=8),
        data_creazione=data_partenza_prevista,
        km_percorsi=None,
        stato_viaggio=StatoViaggio.IN_CORSO,
        composizione_id=composizione_id,
    )


def crea_ordine(id_, viaggio_id, stato=StatoOrdine.PIANIFICATO, negozio_partner="Unieuro", peso=10.0, volume=0.1):
    return Ordine(
        id=id_,
        indirizzo="Via Test 1",
        comune="Ancona",
        provincia="AN",
        lat=None,
        lon=None,
        cliente="Cliente Test",
        peso=peso,
        volume_cargo=volume,
        categoria_consegna=CategoriaConsegna.BORDO_STRADA,
        stato_ordine=stato,
        data_importazione=datetime.now(),
        data_consegna=None,
        viaggio_id=viaggio_id,
        negozio_partner=negozio_partner,
    )


def _crea_causale(session, codice="CLIENTE_ASSENTE"):
    session.add(CausaleFallimento(codice=codice, descrizione="Cliente assente"))
    session.commit()


def _registra(gestore, ordine_id, stato, causale=None):
    risultato = gestore.registra_esito(ordine_id, stato, causale_codice=causale)
    assert risultato.ok, risultato.motivo
    return risultato


def test_report_aggrega_esiti_per_negozio_partner(session_factory, tmp_path):
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", negozio_partner="Unieuro"))
        session.add(crea_ordine("ORD-2", "V-1", negozio_partner="Unieuro"))
        session.add(crea_ordine("ORD-3", "V-1", negozio_partner="Expert"))
        _crea_causale(session)
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    _registra(gestore, "ORD-1", StatoEsito.COMPLETATO)
    _registra(gestore, "ORD-2", StatoEsito.COMPLETATO)
    _registra(gestore, "ORD-3", StatoEsito.FALLITO, causale="CLIENTE_ASSENTE")

    risultato = gestore.genera_report_giornaliero(giorno)

    assert risultato.generato
    assert risultato.percorso_file is not None
    assert (tmp_path / "report_20260720.pdf").exists()

    with session_factory() as session:
        report = session.get(ReportConsuntivo, risultato.report_id)
        assert report.ordini_consegnati == 2
        assert report.ordini_falliti == 1
        assert report.negozi_partner == "Expert, Unieuro"
        assert report.formato_output == "PDF"
        assert {o.id for o in report.ordini} == {"ORD-1", "ORD-2", "ORD-3"}


def test_report_senza_consegne_non_generato(session_factory, tmp_path):
    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)

    risultato = gestore.genera_report_giornaliero(datetime(2026, 7, 20))

    assert not risultato.generato
    assert "Nessuna consegna" in risultato.motivo
    assert list(tmp_path.iterdir()) == []


def test_report_ignora_ordini_senza_esito_registrato(session_factory, tmp_path):
    # Ordini a bordo di un viaggio ma senza esito registrato (RF16 non ancora eseguita) non
    # devono comparire nel report: la fonte e' l'esito persistente, non lo stato dell'ordine.
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", stato=StatoOrdine.RICEVUTO))
        session.add(crea_ordine("ORD-2", "V-1", stato=StatoOrdine.PIANIFICATO))
        session.add(crea_ordine("ORD-3", "V-1", stato=StatoOrdine.IN_CONSEGNA))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    risultato = gestore.genera_report_giornaliero(giorno)

    assert not risultato.generato


def test_report_gia_generato_per_la_data_viene_rigenerato_senza_duplicare(session_factory, tmp_path):
    # RF19 e' schedulato periodicamente: rigenerare lo stesso giorno deve aggiornare la riga
    # esistente (stesso report_id, stesso registro), non rifiutare ne' crearne una seconda.
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1"))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    _registra(gestore, "ORD-1", StatoEsito.COMPLETATO)

    primo = gestore.genera_report_giornaliero(giorno)
    assert primo.generato

    secondo = gestore.genera_report_giornaliero(giorno)
    assert secondo.generato
    assert secondo.report_id == primo.report_id

    with session_factory() as session:
        reports = session.scalars(select(ReportConsuntivo)).all()
        assert len(reports) == 1


def test_report_rigenerato_include_esito_registrato_dopo_la_prima_generazione(session_factory, tmp_path):
    # Un ordine ancora in consegna al momento della prima generazione (es. il job delle 21:00)
    # riceve il suo esito piu' tardi: la rigenerazione deve includerlo.
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1"))
        session.add(crea_ordine("ORD-2", "V-1"))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    _registra(gestore, "ORD-1", StatoEsito.COMPLETATO)

    primo = gestore.genera_report_giornaliero(giorno)
    assert primo.generato
    with session_factory() as session:
        report = session.get(ReportConsuntivo, primo.report_id)
        assert report.ordini_consegnati == 1
        assert report.ordini_falliti == 0
        assert {o.id for o in report.ordini} == {"ORD-1"}

    _registra(gestore, "ORD-2", StatoEsito.COMPLETATO)

    secondo = gestore.genera_report_giornaliero(giorno)
    assert secondo.generato
    assert secondo.report_id == primo.report_id

    with session_factory() as session:
        reports = session.scalars(select(ReportConsuntivo)).all()
        assert len(reports) == 1
        report = reports[0]
        assert report.ordini_consegnati == 2
        assert report.ordini_falliti == 0
        assert {o.id for o in report.ordini} == {"ORD-1", "ORD-2"}


def test_report_esclude_ordini_di_viaggi_partiti_in_altri_giorni(session_factory, tmp_path):
    with session_factory() as session:
        session.add(crea_viaggio("V-OGGI", datetime(2026, 7, 20, 8, 0)))
        session.add(crea_viaggio("V-IERI", datetime(2026, 7, 19, 8, 0)))
        session.add(crea_ordine("ORD-OGGI", "V-OGGI"))
        session.add(crea_ordine("ORD-IERI", "V-IERI"))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    _registra(gestore, "ORD-OGGI", StatoEsito.COMPLETATO)
    _registra(gestore, "ORD-IERI", StatoEsito.COMPLETATO)

    risultato = gestore.genera_report_giornaliero(datetime(2026, 7, 20))

    with session_factory() as session:
        report = session.get(ReportConsuntivo, risultato.report_id)
        assert {o.id for o in report.ordini} == {"ORD-OGGI"}


def test_ordine_senza_negozio_partner_raggruppato_come_non_specificato(session_factory, tmp_path):
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", negozio_partner=None))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    _registra(gestore, "ORD-1", StatoEsito.COMPLETATO)

    risultato = gestore.genera_report_giornaliero(giorno)

    assert risultato.generato
    with session_factory() as session:
        report = session.get(ReportConsuntivo, risultato.report_id)
        assert report.negozi_partner == "Non specificato"


def test_report_conta_fallito_da_flusso_reale_rf16(session_factory, tmp_path):
    # Regressione del bug: registra_esito(FALLITO) riporta l'ordine a RICEVUTO e viaggio_id=None,
    # quindi contare i falliti dallo stato dell'ordine dava sempre 0. La fonte corretta e' l'esito.
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", negozio_partner="Unieuro"))
        _crea_causale(session)
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    _registra(gestore, "ORD-1", StatoEsito.FALLITO, causale="CLIENTE_ASSENTE")

    # Precondizione: il flusso reale ha davvero sganciato l'ordine dal viaggio e lo ha riportato
    # a RICEVUTO (lo stato transitorio su cui il vecchio report contava non esiste piu').
    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-1")
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO
        assert ordine.viaggio_id is None

    risultato = gestore.genera_report_giornaliero(giorno)

    assert risultato.generato
    with session_factory() as session:
        report = session.get(ReportConsuntivo, risultato.report_id)
        assert report.ordini_consegnati == 0
        assert report.ordini_falliti == 1
        assert {o.id for o in report.ordini} == {"ORD-1"}


def test_ciclo_completo_fallimento_ripianificazione_nuovo_esito(session_factory, tmp_path):
    # Ciclo RF16 -> RF17 -> RF16 -> RF19: ORD-1 fallisce su V-1 (giorno 1), viene ripianificato
    # su V-2 (giorno 2) e consegnato. Deve poter ricevere un SECONDO esito, e i due report
    # giornalieri devono contare rispettivamente 1 fallito (giorno 1) e 1 completato (giorno 2).
    giorno_1 = datetime(2026, 7, 20, 8, 0)
    giorno_2 = datetime(2026, 7, 21, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno_1))
        session.add(crea_ordine("ORD-1", "V-1", negozio_partner="Unieuro"))
        _crea_causale(session)
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    _registra(gestore, "ORD-1", StatoEsito.FALLITO, causale="CLIENTE_ASSENTE")

    # RF17: l'ordine tornato in coda viene ripianificato su un nuovo viaggio in corso.
    with session_factory() as session:
        session.add(crea_viaggio("V-2", giorno_2))
        ordine = session.get(Ordine, "ORD-1")
        ordine.viaggio_id = "V-2"
        ordine.stato_ordine = StatoOrdine.IN_CONSEGNA
        session.commit()

    # Il secondo esito ora e' registrabile (prima veniva rifiutato: "gia' associato a un esito").
    secondo = gestore.registra_esito("ORD-1", StatoEsito.COMPLETATO)
    assert secondo.ok, secondo.motivo

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-1")
        assert ordine.stato_ordine == StatoOrdine.COMPLETATO
        assert len(ordine.esiti) == 2

    report_1 = gestore.genera_report_giornaliero(giorno_1)
    report_2 = gestore.genera_report_giornaliero(giorno_2)

    with session_factory() as session:
        r1 = session.get(ReportConsuntivo, report_1.report_id)
        r2 = session.get(ReportConsuntivo, report_2.report_id)
        assert (r1.ordini_consegnati, r1.ordini_falliti) == (0, 1)
        assert (r2.ordini_consegnati, r2.ordini_falliti) == (1, 0)
        assert r1.id != r2.id
