"""Regressione GUI per DipendentiPage: stesso pattern headless di test_page_header.py, combinato
con la fixture session_factory (in-memory) di conftest.py."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from gestionale_logistica.gui.components import BooleanToggle, Button, Modal, Select
from gestionale_logistica.gui.pages import DipendentiPage
from gestionale_logistica.risorse.gestore_dipendenti import GestoreDipendenti


def _trova_bottone(genitore, testo):
    for bottone in genitore.findChildren(Button):
        etichetta = bottone.findChild(QLabel)
        if etichetta is not None and etichetta.text() == testo:
            return bottone
    return None


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_dipendenti_page_vuota_non_crasha(app, session_factory):
    pagina = DipendentiPage(GestoreDipendenti(session_factory))

    assert pagina._etichetta_conteggio.text() == "0 dipendenti"
    assert pagina._tabella._rows_layout.count() == 1  # solo lo stretch finale, nessuna riga


def test_dipendenti_page_popola_tabella(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2021, 1, 1))

    pagina = DipendentiPage(gestore)

    assert pagina._etichetta_conteggio.text() == "2 dipendenti"
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Mario Rossi" in testi
    assert "Luca Bianchi" in testi


def test_dipendenti_page_apri_modale_aggiungi_non_crasha(app, session_factory):
    pagina = DipendentiPage(GestoreDipendenti(session_factory))

    pagina._apri_modale_aggiungi()  # non deve sollevare eccezioni


def test_dipendenti_page_aggiungi_dipendente_aggiorna_tabella(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    pagina = DipendentiPage(gestore)

    # gestore.inserisci_dipendente() e' gia' testato a parte in test_gestore_dipendenti.py, qui
    # verifichiamo solo che la tabella si aggiorni dopo un inserimento riuscito.
    gestore.inserisci_dipendente(
        "EEEEEE80A01A005A", "Anna", "Verdi", "EEEEEE80A01A005A", datetime(2022, 1, 1)
    )
    pagina._reload()

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Anna Verdi" in testi


def test_dipendenti_page_ricerca_filtra_e_ricarica(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2021, 1, 1))
    pagina = DipendentiPage(gestore)

    pagina._campo_ricerca.set_value("mario")
    pagina._on_filtro_cambiato()

    # Table._clear_layout usa solo deleteLater() senza setParent(None) (bug preesistente in
    # table.py, non introdotto qui - gia' segnalato a parte): il widget vecchio resta agganciato
    # all'albero (visibile a findChildren() su tutta la tabella) finche' l'event loop non gira,
    # anche se e' gia' stato tolto dal layout. Per non dipendere da quel timing, si ispezionano
    # solo i widget attualmente nel layout delle righe, non l'intero sotto-albero della tabella.
    righe_correnti = pagina._tabella._rows_layout
    testi = [
        label.text()
        for indice in range(righe_correnti.count())
        if righe_correnti.itemAt(indice).widget() is not None
        for label in righe_correnti.itemAt(indice).widget().findChildren(QLabel)
    ]
    assert "Mario Rossi" in testi
    assert "Luca Bianchi" not in testi


def test_dipendenti_page_modifica_riga_cambia_stato_a_cessato_ricarica(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    pagina = DipendentiPage(gestore)

    pagina._apri_modale_modifica(
        {"id": "D1", "nome": "Mario Rossi", "stato": "Attivo", "flg_certificazione_gas": False}
    )
    modale = pagina.findChildren(Modal)[-1]
    modale.findChild(Select).set_value("Cessato")
    _trova_bottone(modale, "Salva").click()

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Cessato" in testi


def test_dipendenti_page_modifica_riga_cambia_certificazione_gas(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    pagina = DipendentiPage(gestore)

    pagina._apri_modale_modifica(
        {"id": "D1", "nome": "Mario Rossi", "stato": "Attivo", "flg_certificazione_gas": False}
    )
    modale = pagina.findChildren(Modal)[-1]
    modale.findChild(BooleanToggle).set_value(True)
    _trova_bottone(modale, "Salva").click()

    from gestionale_logistica.database.models import Dipendente

    with session_factory() as session:
        assert session.get(Dipendente, "D1").flg_certificazione_gas is True


def test_dipendenti_page_elimina_riga_soft_delete(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    pagina = DipendentiPage(gestore)

    pagina._elimina_riga({"id": "D1", "stato": "Attivo"})

    from gestionale_logistica.database.models import Dipendente

    with session_factory() as session:
        assert session.get(Dipendente, "D1").flg_attivo is False
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Cessato" in testi


def test_dipendenti_page_licenzia_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    # Regressione: senza feedback, un licenziamento rifiutato dal backend (dipendente coinvolto
    # in un viaggio in corso) sembrava un bottone "che non fa nulla" - verifichiamo che venga
    # mostrato un avviso invece di fallire silenziosamente. QMessageBox.warning() e' bloccante
    # (apre un dialogo reale in attesa di click), quindi va sostituito nel test.
    from gestionale_logistica.gui.pages import dipendenti as modulo_dipendenti

    chiamate = []
    monkeypatch.setattr(
        modulo_dipendenti.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        from gestionale_logistica.database.enums import StatoViaggio
        from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Squadra, Viaggio

        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(Camion(
            id="CAM1", targa="AB123CD", tipo_mezzo="Furgone", peso_massimo=100.0, volume_massimo=5.0,
            flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1), data_dismissione=None,
            flg_attivo=True,
        ))
        session.add(ComposizioneSquadra(
            id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
            dipendente_1_id="D1", dipendente_2_id="D2",
            data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
        ))
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="C1",
        ))
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2020, 1, 1))
    pagina = DipendentiPage(gestore)

    pagina._apri_modale_modifica(
        {"id": "D1", "nome": "Mario Rossi", "stato": "Attivo", "flg_certificazione_gas": False}
    )
    modale = pagina.findChildren(Modal)[-1]
    modale.findChild(Select).set_value("Cessato")
    _trova_bottone(modale, "Salva").click()

    assert len(chiamate) == 1
    with session_factory() as session:
        from gestionale_logistica.database.models import Dipendente

        assert session.get(Dipendente, "D1").flg_attivo is True


def test_dipendenti_page_modifica_riga_riassumi_ricarica(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    gestore.licenzia_dipendente("D1")
    pagina = DipendentiPage(gestore)

    pagina._apri_modale_modifica(
        {"id": "D1", "nome": "Mario Rossi", "stato": "Cessato", "flg_certificazione_gas": False}
    )
    modale = pagina.findChildren(Modal)[-1]
    modale.findChild(Select).set_value("Attivo")
    _trova_bottone(modale, "Salva").click()

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Attivo" in testi


def test_dipendenti_page_elimina_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import dipendenti as modulo_dipendenti
    from gestionale_logistica.database.enums import StatoViaggio
    from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Squadra, Viaggio

    chiamate = []
    monkeypatch.setattr(
        modulo_dipendenti.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(Camion(
            id="CAM1", targa="AB123CD", tipo_mezzo="Furgone", peso_massimo=100.0, volume_massimo=5.0,
            flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1), data_dismissione=None,
            flg_attivo=True,
        ))
        session.add(ComposizioneSquadra(
            id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
            dipendente_1_id="D1", dipendente_2_id="D2",
            data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
        ))
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="C1",
        ))
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2020, 1, 1))
    pagina = DipendentiPage(gestore)

    pagina._elimina_riga({"id": "D1", "stato": "Attivo"})

    assert len(chiamate) == 1
    from gestionale_logistica.database.models import Dipendente

    with session_factory() as session:
        assert session.get(Dipendente, "D1").flg_attivo is True


def test_dipendenti_page_filtro_stato_si_puo_azzerare(app, session_factory):
    from gestionale_logistica.risorse.gestore_dipendenti import FILTRO_TUTTI, STATO_ATTIVO

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2020, 1, 1))
    gestore.licenzia_dipendente("D2")
    pagina = DipendentiPage(gestore)

    assert FILTRO_TUTTI in pagina._select_stato._options

    pagina._select_stato.set_value(STATO_ATTIVO)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 dipendenti"

    pagina._select_stato.set_value(FILTRO_TUTTI)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 dipendenti"


def test_dipendenti_page_filtro_squadra_si_puo_azzerare(app, session_factory):
    from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Squadra

    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(Camion(
            id="CAM1", targa="AB123CD", tipo_mezzo="Furgone", peso_massimo=100.0, volume_massimo=5.0,
            flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1), data_dismissione=None,
            flg_attivo=True,
        ))
        session.add(ComposizioneSquadra(
            id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
            dipendente_1_id="D1", dipendente_2_id="D2",
            data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
        ))
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D3", "Anna", "Neri", "CCCCCC80A01A003A", datetime(2020, 1, 1))
    pagina = DipendentiPage(gestore)

    from gestionale_logistica.gui.pages.dipendenti import FILTRO_TUTTE_SQUADRE

    assert FILTRO_TUTTE_SQUADRE in pagina._select_squadra._options

    pagina._select_squadra.set_value("Squadra SQ1")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 dipendenti"

    pagina._select_squadra.set_value(FILTRO_TUTTE_SQUADRE)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "3 dipendenti"


def test_dipendenti_page_filtro_certificazione_gas(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente(
        "D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1), flg_certificazione_gas=True
    )
    gestore.inserisci_dipendente(
        "D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2020, 1, 1), flg_certificazione_gas=False
    )
    pagina = DipendentiPage(gestore)

    pagina._select_cert_gas.set_value("Sì")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 dipendenti"

    pagina._select_cert_gas.set_value("No")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 dipendenti"

    pagina._select_cert_gas.set_value(None)
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 dipendenti"


def test_dipendenti_page_ripristina_filtri_azzera_cert_gas(app, session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente(
        "D1", "Mario", "Rossi", "AAAAAA80A01A001A", datetime(2020, 1, 1), flg_certificazione_gas=True
    )
    gestore.inserisci_dipendente(
        "D2", "Luca", "Bianchi", "BBBBBB80A01A002A", datetime(2020, 1, 1), flg_certificazione_gas=False
    )
    pagina = DipendentiPage(gestore)
    pagina._select_cert_gas.set_value("Sì")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 dipendenti"

    pagina._ripristina_filtri()

    assert pagina._select_cert_gas.value() is None
    assert pagina._etichetta_conteggio.text() == "2 dipendenti"
