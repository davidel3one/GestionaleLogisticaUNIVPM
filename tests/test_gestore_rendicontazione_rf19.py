from datetime import datetime, timedelta

from sqlalchemy import select

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Ordine, ReportConsuntivo, Viaggio
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione


def crea_viaggio(id_, data_partenza_prevista, composizione_id="C1"):
    return Viaggio(
        id=id_,
        data_partenza_prevista=data_partenza_prevista,
        data_arrivo_prevista=data_partenza_prevista + timedelta(hours=8),
        km_percorsi=None,
        stato_viaggio=StatoViaggio.IN_CORSO,
        composizione_id=composizione_id,
    )


def crea_ordine(id_, viaggio_id, stato, negozio_partner="Unieuro", peso=10.0, volume=0.1):
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
        data_consegna=None,
        viaggio_id=viaggio_id,
        negozio_partner=negozio_partner,
    )


def test_report_aggrega_esiti_per_negozio_partner(session_factory, tmp_path):
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", StatoOrdine.COMPLETATO, negozio_partner="Unieuro"))
        session.add(crea_ordine("ORD-2", "V-1", StatoOrdine.COMPLETATO, negozio_partner="Unieuro"))
        session.add(crea_ordine("ORD-3", "V-1", StatoOrdine.FALLITO, negozio_partner="Expert"))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
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


def test_report_ignora_ordini_non_ancora_rendicontabili(session_factory, tmp_path):
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", StatoOrdine.RICEVUTO))
        session.add(crea_ordine("ORD-2", "V-1", StatoOrdine.PIANIFICATO))
        session.add(crea_ordine("ORD-3", "V-1", StatoOrdine.IN_CONSEGNA))
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
        session.add(crea_ordine("ORD-1", "V-1", StatoOrdine.COMPLETATO))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    primo = gestore.genera_report_giornaliero(giorno)
    assert primo.generato

    secondo = gestore.genera_report_giornaliero(giorno)
    assert secondo.generato
    assert secondo.report_id == primo.report_id

    with session_factory() as session:
        reports = session.scalars(select(ReportConsuntivo)).all()
        assert len(reports) == 1


def test_report_rigenerato_include_ordine_completato_dopo_la_prima_generazione(session_factory, tmp_path):
    # Riproduce il bug: un ordine ancora IN_CONSEGNA al momento della prima generazione (es. il
    # job delle 21:00) veniva escluso per sempre dal report, anche una volta completato/fallito,
    # perche' il guard su report_esistente rifiutava qualunque rigenerazione successiva.
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", StatoOrdine.COMPLETATO))
        session.add(crea_ordine("ORD-2", "V-1", StatoOrdine.IN_CONSEGNA))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    primo = gestore.genera_report_giornaliero(giorno)
    assert primo.generato
    with session_factory() as session:
        report = session.get(ReportConsuntivo, primo.report_id)
        assert report.ordini_consegnati == 1
        assert report.ordini_falliti == 0
        assert {o.id for o in report.ordini} == {"ORD-1"}

    with session_factory() as session:
        ordine_2 = session.get(Ordine, "ORD-2")
        ordine_2.stato_ordine = StatoOrdine.COMPLETATO
        session.commit()

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
        session.add(crea_ordine("ORD-OGGI", "V-OGGI", StatoOrdine.COMPLETATO))
        session.add(crea_ordine("ORD-IERI", "V-IERI", StatoOrdine.COMPLETATO))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    risultato = gestore.genera_report_giornaliero(datetime(2026, 7, 20))

    with session_factory() as session:
        report = session.get(ReportConsuntivo, risultato.report_id)
        assert {o.id for o in report.ordini} == {"ORD-OGGI"}


def test_ordine_senza_negozio_partner_raggruppato_come_non_specificato(session_factory, tmp_path):
    giorno = datetime(2026, 7, 20, 8, 0)
    with session_factory() as session:
        session.add(crea_viaggio("V-1", giorno))
        session.add(crea_ordine("ORD-1", "V-1", StatoOrdine.COMPLETATO, negozio_partner=None))
        session.commit()

    gestore = GestoreRendicontazione(session_factory, cartella_output=tmp_path)
    risultato = gestore.genera_report_giornaliero(giorno)

    assert risultato.generato
    with session_factory() as session:
        report = session.get(ReportConsuntivo, risultato.report_id)
        assert report.negozi_partner == "Non specificato"
