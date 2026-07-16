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
    assert pagina._tabella._rows_layout.count() == 1  # solo lo stretch finale, nessuna riga


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
        if righe_correnti.itemAt(indice).widget() is not None
        for label in righe_correnti.itemAt(indice).widget().findChildren(QLabel)
    ]
    assert "AB123CD" in testi
    assert "XY999ZZ" not in testi


def test_camion_page_modifica_riga_disattiva_ricarica(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._modifica_riga({"id": "C1", "stato": "Attivo"})

    # La riga sparisce dalla vista di default (Dismesso nascosto), non solo cambia badge.
    assert pagina._etichetta_conteggio.text() == "0 camion"


def test_camion_page_modifica_riga_riattiva_ricarica(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.disattiva_camion("C1")
    pagina = CamionPage(gestore)

    pagina._modifica_riga({"id": "C1", "stato": "Dismesso"})

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Attivo" in testi


def test_camion_page_elimina_riga_soft_delete_vero(app, session_factory):
    # Soft-delete "vero" (flg_eliminato): la riga resta a database ma sparisce dalla vista di
    # default, con lo stesso risultato osservabile dell'hard-delete usato in precedenza.
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._conferma_elimina_riga({"id": "C1", "stato": "Attivo"})

    from gestionale_logistica.database.models import Camion

    with session_factory() as session:
        camion_obj = session.get(Camion, "C1")
        assert camion_obj is not None  # la riga resta a database (RF8)
        assert camion_obj.flg_eliminato is True
    assert pagina._etichetta_conteggio.text() == "0 camion"


def test_camion_page_elimina_riga_funziona_anche_se_gia_dismesso(app, session_factory):
    # Correzione esplicita dell'utente: il cestino deve eliminare la riga sia che il camion sia
    # Attivo sia che sia gia' Dismesso - nessuna distinzione, nessun errore "gia' dismesso".
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.disattiva_camion("C1")
    pagina = CamionPage(gestore)

    pagina._conferma_elimina_riga({"id": "C1", "stato": "Dismesso"})

    from gestionale_logistica.database.models import Camion

    with session_factory() as session:
        assert session.get(Camion, "C1").flg_eliminato is True
    # Non piu' consultabile nemmeno scegliendo esplicitamente il filtro Stato "Dismesso".
    from gestionale_logistica.risorse.gestore_camion import STATO_DISMESSO

    assert gestore.visualizza_camion(filtro_stato=STATO_DISMESSO).totale == 0


def test_camion_page_elimina_riga_apre_conferma_senza_eliminare_subito(app, session_factory):
    from gestionale_logistica.gui.components import ConfirmModal
    from gestionale_logistica.database.models import Camion

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._elimina_riga({"id": "C1", "stato": "Attivo", "targa": "AB123CD"})

    with session_factory() as session:
        assert session.get(Camion, "C1").flg_eliminato is False  # non ancora eliminato
    modali = pagina.findChildren(ConfirmModal)
    assert len(modali) == 1

    modali[0].confirmed.emit()

    with session_factory() as session:
        assert session.get(Camion, "C1").flg_eliminato is True


def test_camion_page_elimina_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import camion as modulo_camion
    from gestionale_logistica.database.models import ComposizioneSquadra, Dipendente, Squadra

    chiamate = []
    monkeypatch.setattr(
        modulo_camion.ToastManager, "show_error", lambda *args: chiamate.append(args) or None
    )

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
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._conferma_elimina_riga({"id": "CAM1", "stato": "Attivo"})

    assert len(chiamate) == 1
    from gestionale_logistica.database.models import Camion

    with session_factory() as session:
        assert session.get(Camion, "CAM1") is not None


def test_camion_page_modifica_riga_disattiva_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import camion as modulo_camion

    chiamate = []
    monkeypatch.setattr(
        modulo_camion.ToastManager, "show_error", lambda *args: chiamate.append(args) or None
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
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="C1",
        ))
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    pagina._modifica_riga({"id": "CAM1", "stato": "Attivo"})

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

    pagina._select_stato.set_value([STATO_ATTIVO])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._select_stato.set_value([])
    pagina._on_filtro_cambiato()
    # Tutti nasconde C2 (Dismesso): resta solo C1.
    assert pagina._etichetta_conteggio.text() == "1 camion"


def test_camion_page_filtro_tipo_si_puo_azzerare(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 3500.0, 22.0)
    pagina = CamionPage(gestore)

    pagina._select_tipo.set_value(["Furgone"])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._select_tipo.set_value([])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 camion"


def test_camion_page_filtro_tipo_multiplo(app, session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 3500.0, 22.0)
    gestore.inserisci_camion("C3", "ZZ111AA", "Bilico", datetime(2020, 1, 1), 8000.0, 40.0)
    pagina = CamionPage(gestore)

    # Piu' tipi selezionati insieme (MultiSelect): righe che soddisfano uno qualsiasi dei valori.
    pagina._select_tipo.set_value(["Furgone", "Bilico"])
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
    pagina._select_stato.set_value([STATO_ATTIVO])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._ripristina_filtri()

    assert pagina._campo_ricerca.value() == ""
    assert pagina._select_stato.value() == []
    assert pagina._select_tipo.value() == []
    assert pagina._select_sponda.value() == []
    # Tutti nasconde C2 (Dismesso): resta solo C1.
    assert pagina._etichetta_conteggio.text() == "1 camion"


def test_camion_page_filtro_sponda_idraulica(app, session_factory):
    from gestionale_logistica.gui.pages.camion import SPONDA_NO, SPONDA_SI

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion(
        "C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0, flg_sponda_idraulica=True
    )
    gestore.inserisci_camion(
        "C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 3500.0, 22.0, flg_sponda_idraulica=False
    )
    pagina = CamionPage(gestore)

    pagina._select_sponda.set_value([SPONDA_SI])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._select_sponda.set_value([SPONDA_NO])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 camion"

    pagina._select_sponda.set_value([])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 camion"


def test_camion_page_azione_e_unicona_toggle_non_una_matita(app, session_factory):
    from gestionale_logistica.gui.components.table import _IconButton

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)
    pagina = CamionPage(gestore)

    # Attivo: solo l'azione "Attivo — clicca per dismettere" (verde) e' presente, non la sua
    # controparte Dismesso - due RowAction (stessa icona arrow-left-right, colore diverso)
    # mutuamente esclusive via predicate, non un widget switch dedicato. (findChildren su tutta
    # la tabella include anche i bottoni del pager, non solo quelli della riga.)
    tooltip_per_bottone = {b.toolTip() for b in pagina._tabella.findChildren(_IconButton)}
    assert "Attivo — clicca per dismettere" in tooltip_per_bottone
    assert "Dismesso — clicca per riattivare" not in tooltip_per_bottone

    toggle = next(
        b for b in pagina._tabella.findChildren(_IconButton)
        if b.toolTip() == "Attivo — clicca per dismettere"
    )
    toggle.click()

    from gestionale_logistica.database.models import Camion

    with session_factory() as session:
        assert session.get(Camion, "C1").flg_attivo is False
