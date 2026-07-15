"""Regressione GUI per CamionPage: stesso pattern headless di test_form_field.py."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from gestionale_logistica.gui.pages import CamionPage
from gestionale_logistica.risorse.gestore_camion import GestoreCamion


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_camion_page_vuota_non_crasha(app, session_factory):
    pagina = CamionPage(GestoreCamion(session_factory))

    assert pagina._etichetta_conteggio.text() == "0 camion"
    assert pagina._tabella._rows_layout.count() == 0


def test_camion_page_popola_tabella(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2021, 1, 1), 3500.0, 22.0)

    pagina = CamionPage(gestore)

    assert pagina._etichetta_conteggio.text() == "2 camion"
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "AB123CD" in testi
    assert "XY999ZZ" in testi
    assert "1200 kg · 8 m³" in testi


def test_camion_page_apri_modale_aggiungi_non_crasha(app, session_factory):
    pagina = CamionPage(GestoreCamion(session_factory))

    pagina._apri_modale_aggiungi()  # non deve sollevare eccezioni


def test_camion_page_apri_modale_modifica_non_crasha(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    riga = {"id": "C1", "tipo_mezzo": "Furgone", "flg_sponda_idraulica": False}
    pagina._apri_modale_modifica(riga)  # non deve sollevare eccezioni


def test_camion_page_ricerca_filtra_e_ricarica(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2021, 1, 1), 3500.0, 22.0)
    pagina = CamionPage(gestore)

    pagina._campo_ricerca.set_value("ab123")
    pagina._on_filtro_cambiato()

    righe_correnti = pagina._tabella._rows_layout
    testi = [
        label.text()
        for indice in range(righe_correnti.count())
        for label in righe_correnti.itemAt(indice).widget().findChildren(QLabel)
    ]
    assert "AB123CD" in testi
    assert "XY999ZZ" not in testi


def test_camion_page_disattiva_riga_ricarica(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._disattiva_riga({"id": "C1"})

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Dismesso" in testi


def test_camion_page_riattiva_riga_ricarica(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.disattiva_camion("C1")
    pagina = CamionPage(gestore)

    pagina._riattiva_riga({"id": "C1"})

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Attivo" in testi


def test_camion_page_riattiva_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import camion as modulo_camion

    chiamate = []
    monkeypatch.setattr(
        modulo_camion.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._riattiva_riga({"id": "C1"})

    assert len(chiamate) == 1


def test_camion_page_azione_ripristino_solo_per_dismessi(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 3500.0, 22.0)
    gestore.disattiva_camion("C2")
    pagina = CamionPage(gestore)

    colonna_azioni = pagina._tabella._columns[-1]
    azione_disattiva = colonna_azioni.actions[1]
    azione_riattiva = colonna_azioni.actions[2]

    riga_attiva = {"stato": "Attivo"}
    riga_dismessa = {"stato": "Dismesso"}

    assert azione_disattiva.predicate(riga_attiva) is True
    assert azione_disattiva.predicate(riga_dismessa) is False
    assert azione_riattiva.predicate(riga_attiva) is False
    assert azione_riattiva.predicate(riga_dismessa) is True


def test_camion_page_disattiva_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import camion as modulo_camion

    chiamate = []
    monkeypatch.setattr(
        modulo_camion.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    from gestionale_logistica.database.enums import StatoViaggio
    from gestionale_logistica.database.models import ComposizioneSquadra, Dipendente, Squadra, Viaggio

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
        session.add(ComposizioneSquadra(
            id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
            dipendente_1_id="D1", dipendente_2_id="D2",
            data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
        ))
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="C1",
        ))
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._disattiva_riga({"id": "CAM1"})

    assert len(chiamate) == 1
    with session_factory() as session:
        from gestionale_logistica.database.models import Camion

        assert session.get(Camion, "CAM1").flg_attivo is True


def test_camion_page_filtro_stato_si_puo_azzerare(app, session_factory):
    from gestionale_logistica.risorse.gestore_camion import STATO_ATTIVO

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 3500.0, 22.0)
    gestore.disattiva_camion("C2")
    pagina = CamionPage(gestore)

    pagina._select_stato.set_value(STATO_ATTIVO)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._select_stato.set_value(None)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 camion"


def test_camion_page_filtro_tipo_si_puo_azzerare(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 3500.0, 22.0)
    pagina = CamionPage(gestore)

    pagina._select_tipo.set_value("Furgone")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._select_tipo.set_value(None)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 camion"


def test_camion_page_ripristina_filtri_azzera_tutto_insieme(app, session_factory):
    from gestionale_logistica.risorse.gestore_camion import STATO_ATTIVO

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 3500.0, 22.0)
    gestore.disattiva_camion("C2")
    pagina = CamionPage(gestore)

    pagina._campo_ricerca.set_value("ab123")
    pagina._select_stato.set_value(STATO_ATTIVO)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._ripristina_filtri()

    assert pagina._campo_ricerca.value() == ""
    assert pagina._select_stato.value() is None
    assert pagina._select_tipo.value() is None
    assert pagina._etichetta_conteggio.text() == "2 camion"
