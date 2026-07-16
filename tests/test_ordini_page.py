"""Regressione GUI per OrdiniPage: stesso pattern headless di test_form_field.py."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Ordine
from gestionale_logistica.gui.pages import OrdiniPage
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def crea_ordine(id_, cliente="Cliente Test", indirizzo="Via Test 1", comune="Ancona",
                 peso=10.0, volume=0.1, stato=StatoOrdine.RICEVUTO):
    return Ordine(
        id=id_, indirizzo=indirizzo, comune=comune, provincia="AN", lat=None, lon=None,
        cliente=cliente, peso=peso, volume_cargo=volume,
        categoria_consegna=CategoriaConsegna.BORDO_STRADA, stato_ordine=stato,
        data_importazione=datetime.now(), data_consegna=None, viaggio_id=None,
    )


def test_ordini_page_vuota_non_crasha(app, session_factory):
    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))

    assert pagina._etichetta_conteggio.text() == "0 ordini"
    assert pagina._tabella._rows_layout.count() == 1  # solo lo stretch finale, nessuna riga


def test_ordini_page_popola_tabella(app, session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1", cliente="Mario Rossi", peso=45.0, volume=0.3))
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))

    assert pagina._etichetta_conteggio.text() == "1 ordini"
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "ORD-1" in testi
    assert "Mario Rossi" in testi
    assert "45 kg · 0.3 m³" in testi
    assert "Da pianificare" in testi
    assert "—" in testi  # nessun viaggio agganciato


def test_ordini_page_tab_bar_entrambe_le_tab_abilitate(app, session_factory):
    from gestionale_logistica.gui.components import TabBar

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))

    barre = pagina.findChildren(TabBar)
    assert len(barre) == 1
    assert barre[0]._tabs[0]._disabled is False
    assert barre[0]._tabs[1]._disabled is False


def test_ordini_page_cambio_tab_mostra_vista_esiti(app, session_factory):
    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))

    assert pagina._stack.currentIndex() == 0
    pagina._on_tab_cambiata(1)
    assert pagina._stack.currentIndex() == 1
    assert pagina._esiti_etichetta_conteggio.text() == "0 esiti"


def test_ordini_page_bottone_importa_csv_apre_il_modale(app, session_factory):
    from gestionale_logistica.gui.components import ImportCsvModal

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))

    pagina._apri_import_csv()  # non deve sollevare eccezioni

    assert isinstance(pagina._import_modal, ImportCsvModal)


def test_ordini_page_ricerca_filtra_e_ricarica(app, session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1", cliente="Mario Rossi"))
        session.add(crea_ordine("ORD-2", cliente="Bianchi S.r.l."))
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))
    pagina._campo_ricerca.set_value("mario")
    pagina._on_filtro_cambiato()

    righe_correnti = pagina._tabella._rows_layout
    testi = [
        label.text()
        for indice in range(righe_correnti.count())
        if righe_correnti.itemAt(indice).widget() is not None
        for label in righe_correnti.itemAt(indice).widget().findChildren(QLabel)
    ]
    assert "Mario Rossi" in testi
    assert "Bianchi S.r.l." not in testi


def test_ordini_page_filtro_stato_si_puo_azzerare(app, session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1", stato=StatoOrdine.RICEVUTO))
        session.add(crea_ordine("ORD-2", stato=StatoOrdine.FALLITO))
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))

    pagina._select_stato.set_value("Fallito")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 ordini"

    pagina._select_stato.set_value(None)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 ordini"


def test_ordini_page_filtro_data(app, session_factory):
    from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Squadra, Viaggio

    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(Dipendente(
            id="D1", nome="Mario", cognome="Rossi", codice_fiscale="AAAAAA80A01A001A",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=True, flg_certificazione_gas=False,
        ))
        session.add(Dipendente(
            id="D2", nome="Luca", cognome="Bianchi", codice_fiscale="BBBBBB80A01A002A",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=True, flg_certificazione_gas=False,
        ))
        session.add(Camion(
            id="CAM1", targa="AB123CD", tipo_mezzo="Furgone", peso_massimo=1000.0,
            volume_massimo=10.0, flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1),
            data_dismissione=None, flg_attivo=True,
        ))
        session.add(ComposizioneSquadra(
            id_composizione="SQ1", squadra_id="SQ1", camion_id="CAM1",
            dipendente_1_id="D1", dipendente_2_id="D2",
            data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
        ))
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        ordine_1 = crea_ordine("ORD-1")
        ordine_1.viaggio_id = "V1"
        session.add(ordine_1)
        session.add(crea_ordine("ORD-2"))
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))
    pagina._campo_data.set_value(QDate(2026, 7, 20))

    assert pagina._etichetta_conteggio.text() == "1 ordini"


def test_ordini_page_elimina_riga_definitiva(app, session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1"))
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))
    pagina._elimina_riga({"id": "ORD-1"})

    with session_factory() as session:
        assert session.get(Ordine, "ORD-1") is None
    assert pagina._etichetta_conteggio.text() == "0 ordini"


def test_ordini_page_elimina_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.database.enums import StatoEsito
    from gestionale_logistica.database.models import EsitoConsegna, RegistroEsiti
    from gestionale_logistica.gui.pages import ordini as modulo_ordini

    chiamate = []
    monkeypatch.setattr(
        modulo_ordini.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        session.add(crea_ordine("ORD-1", stato=StatoOrdine.FALLITO))
        session.add(RegistroEsiti(id=1, data_riferimento=datetime(2026, 7, 15)))
        session.add(EsitoConsegna(
            id=1, stato_esito=StatoEsito.FALLITO, data_registrazione=datetime(2026, 7, 15),
            ordine_id="ORD-1", viaggio_id="V-INESISTENTE", causale_id=None, registro_id=1,
        ))
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))
    pagina._elimina_riga({"id": "ORD-1"})

    assert len(chiamate) == 1
    with session_factory() as session:
        assert session.get(Ordine, "ORD-1") is not None


def test_ordini_page_ripristina_filtri_azzera_tutto_insieme(app, session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1", cliente="Mario Rossi", stato=StatoOrdine.RICEVUTO))
        session.add(crea_ordine("ORD-2", cliente="Bianchi S.r.l.", stato=StatoOrdine.FALLITO))
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))
    pagina._campo_ricerca.set_value("mario")
    pagina._select_stato.set_value("Da pianificare")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 ordini"

    pagina._ripristina_filtri()

    assert pagina._campo_ricerca.value() == ""
    assert pagina._select_stato.value() is None
    assert pagina._filtro_data is None
    assert pagina._etichetta_conteggio.text() == "2 ordini"


def _crea_flotta_e_viaggio_in_corso(session, viaggio_id="V1", squadra_id="SQ1"):
    from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Squadra, Viaggio

    session.add(Squadra(id=squadra_id, flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
    session.add(Dipendente(
        id=f"{squadra_id}-D1", nome="Mario", cognome="Rossi", codice_fiscale=f"CF{squadra_id}1",
        data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
        flg_attivo=True, flg_certificazione_gas=False,
    ))
    session.add(Dipendente(
        id=f"{squadra_id}-D2", nome="Luca", cognome="Bianchi", codice_fiscale=f"CF{squadra_id}2",
        data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
        flg_attivo=True, flg_certificazione_gas=False,
    ))
    session.add(Camion(
        id=f"{squadra_id}-CAM", targa=f"AB{squadra_id}CD", tipo_mezzo="Furgone", peso_massimo=1000.0,
        volume_massimo=10.0, flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1),
        data_dismissione=None, flg_attivo=True,
    ))
    session.add(ComposizioneSquadra(
        id_composizione=squadra_id, squadra_id=squadra_id, camion_id=f"{squadra_id}-CAM",
        dipendente_1_id=f"{squadra_id}-D1", dipendente_2_id=f"{squadra_id}-D2",
        data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
    ))
    session.add(Viaggio(
        id=viaggio_id, data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
        data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
        km_percorsi=None, stato_viaggio=StatoViaggio.IN_CORSO, composizione_id=squadra_id,
    ))


def test_ordini_page_registra_esito_apre_il_modale(app, session_factory):
    from gestionale_logistica.gui.pages.ordini._registra_esito_modal import RegistraEsitoModal

    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        ordine = crea_ordine("ORD-1")
        ordine.viaggio_id = "V1"
        session.add(ordine)
        session.commit()

    pagina = OrdiniPage(GestoreLogistica(session_factory), GestoreRendicontazione(session_factory))
    riga = {"id": "ORD-1", "cliente": "Cliente Test", "indirizzo": "Via Test 1, Ancona", "peso_volume": "10 kg · 0.1 m³"}

    pagina._registra_esito(riga)  # non deve sollevare eccezioni

    assert isinstance(pagina._esito_modal, RegistraEsitoModal)


def test_ordini_page_esito_registrato_ricarica_ordini_ed_esiti(app, session_factory):
    from gestionale_logistica.database.enums import StatoEsito

    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        ordine = crea_ordine("ORD-1")
        ordine.viaggio_id = "V1"
        session.add(ordine)
        session.commit()

    gestore_rendicontazione = GestoreRendicontazione(session_factory)
    pagina = OrdiniPage(GestoreLogistica(session_factory), gestore_rendicontazione)

    gestore_rendicontazione.registra_esito("ORD-1", StatoEsito.COMPLETATO)
    pagina._on_esito_registrato()

    assert pagina._etichetta_conteggio.text() == "1 ordini"
    pagina._on_tab_cambiata(1)
    assert pagina._esiti_etichetta_conteggio.text() == "1 esiti"


def test_ordini_page_esiti_ordinamento_su_data_registrazione(app, session_factory):
    from gestionale_logistica.database.enums import StatoEsito

    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session, viaggio_id="V1")
        _crea_flotta_e_viaggio_in_corso(session, viaggio_id="V2", squadra_id="SQ2")
        ordine_1 = crea_ordine("ORD-1")
        ordine_1.viaggio_id = "V1"
        session.add(ordine_1)
        ordine_2 = crea_ordine("ORD-2")
        ordine_2.viaggio_id = "V2"
        session.add(ordine_2)
        session.commit()

    gestore_rendicontazione = GestoreRendicontazione(session_factory)
    gestore_rendicontazione.registra_esito("ORD-1", StatoEsito.COMPLETATO)
    gestore_rendicontazione.registra_esito("ORD-2", StatoEsito.COMPLETATO)

    pagina = OrdiniPage(GestoreLogistica(session_factory), gestore_rendicontazione)
    pagina._on_tab_cambiata(1)

    pagina._on_esiti_sort_richiesto("data_registrazione", True)
    assert pagina._esiti_decrescente is False

    pagina._on_esiti_sort_richiesto("data_registrazione", False)
    assert pagina._esiti_decrescente is True


def test_ordini_page_modifica_esito_apre_il_modale_in_modalita_modifica(app, session_factory):
    from gestionale_logistica.database.enums import StatoEsito
    from gestionale_logistica.gui.pages.ordini._registra_esito_modal import RegistraEsitoModal

    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        ordine = crea_ordine("ORD-1")
        ordine.viaggio_id = "V1"
        session.add(ordine)
        session.commit()

    gestore_rendicontazione = GestoreRendicontazione(session_factory)
    risultato = gestore_rendicontazione.registra_esito("ORD-1", StatoEsito.COMPLETATO)

    pagina = OrdiniPage(GestoreLogistica(session_factory), gestore_rendicontazione)
    riga = {
        "id": "ORD-1", "cliente": "Cliente Test", "indirizzo": "Via Test 1, Ancona",
        "peso_volume": "10 kg · 0.1 m³", "esito": "Completato", "causale_codice": None,
        "esito_id": risultato.esito_id,
    }

    pagina._modifica_esito(riga)  # non deve sollevare eccezioni

    assert isinstance(pagina._esito_modal, RegistraEsitoModal)
    assert pagina._esito_modal._esito_id == risultato.esito_id


def test_ordini_page_elimina_esito_ricarica_ordini_ed_esiti(app, session_factory):
    from gestionale_logistica.database.enums import StatoEsito
    from gestionale_logistica.database.models import Ordine

    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        ordine = crea_ordine("ORD-1")
        ordine.viaggio_id = "V1"
        session.add(ordine)
        session.commit()

    gestore_rendicontazione = GestoreRendicontazione(session_factory)
    risultato = gestore_rendicontazione.registra_esito("ORD-1", StatoEsito.COMPLETATO)

    pagina = OrdiniPage(GestoreLogistica(session_factory), gestore_rendicontazione)
    pagina._elimina_esito({"esito_id": risultato.esito_id})

    with session_factory() as session:
        assert session.get(Ordine, "ORD-1").stato_ordine == StatoOrdine.PIANIFICATO
    assert pagina._etichetta_conteggio.text() == "1 ordini"
    pagina._on_tab_cambiata(1)
    assert pagina._esiti_etichetta_conteggio.text() == "0 esiti"


def test_ordini_page_elimina_esito_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import ordini as modulo_ordini

    chiamate = []
    monkeypatch.setattr(
        modulo_ordini.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    gestore_rendicontazione = GestoreRendicontazione(session_factory)
    pagina = OrdiniPage(GestoreLogistica(session_factory), gestore_rendicontazione)

    pagina._elimina_esito({"esito_id": 999})

    assert len(chiamate) == 1
