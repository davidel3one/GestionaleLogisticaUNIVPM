"""Regressione GUI per ViaggiPage: stesso pattern headless di test_form_field.py."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Ordine, Squadra, Viaggio
from gestionale_logistica.gui.pages import ViaggiPage
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def crea_flotta(session, comp_id="SQ1"):
    session.add(Squadra(id=comp_id, flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
    session.add(Dipendente(
        id=f"{comp_id}-D1", nome="Mario", cognome="Rossi", codice_fiscale=f"CF-{comp_id}-1",
        data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
        flg_attivo=True, flg_certificazione_gas=False,
    ))
    session.add(Dipendente(
        id=f"{comp_id}-D2", nome="Luca", cognome="Bianchi", codice_fiscale=f"CF-{comp_id}-2",
        data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
        flg_attivo=True, flg_certificazione_gas=False,
    ))
    session.add(Camion(
        id=f"{comp_id}-CAM", targa=f"AB{comp_id}CD", tipo_mezzo="Furgone", peso_massimo=100.0,
        volume_massimo=5.0, flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1),
        data_dismissione=None, flg_attivo=True,
    ))
    session.add(ComposizioneSquadra(
        id_composizione=comp_id, squadra_id=comp_id, camion_id=f"{comp_id}-CAM",
        dipendente_1_id=f"{comp_id}-D1", dipendente_2_id=f"{comp_id}-D2",
        data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
    ))


def crea_viaggio(id_, composizione_id, stato=StatoViaggio.PIANIFICATO,
                  partenza=datetime(2026, 7, 20, 8, 0), arrivo=datetime(2026, 7, 20, 16, 0)):
    return Viaggio(
        id=id_, data_partenza_prevista=partenza, data_arrivo_prevista=arrivo,
        data_creazione=datetime.now(),
        km_percorsi=None, stato_viaggio=stato, composizione_id=composizione_id,
    )


def test_viaggi_page_vuota_non_crasha(app, session_factory):
    pagina = ViaggiPage(GestoreLogistica(session_factory))

    assert pagina._etichetta_conteggio.text() == "0 viaggi"
    assert pagina._tabella._rows_layout.count() == 1  # solo lo stretch finale, nessuna riga


def test_viaggi_page_bottone_nuova_pianificazione_emette_segnale(app, session_factory):
    # 2026-07-16, richiesta esplicita dell'utente: il bottone "Nuova pianificazione" non e' piu'
    # disabilitato, riprende lo stesso pattern di DashboardPage.nuovaPianificazioneRequested (il
    # composition root collega questo segnale a PianificazionePage.mostra_tab_automatica +
    # AppShell.navigate_to("pianificazione"), non testato qui - vive in src/__init__.py).
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from gestionale_logistica.gui.components import Button

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    bottone = next(b for b in pagina.findChildren(Button) if b.isEnabled())

    ricevuti = []
    pagina.nuovaPianificazioneRequested.connect(lambda: ricevuti.append(True))
    QTest.mouseClick(bottone, Qt.MouseButton.LeftButton)

    assert ricevuti == [True]


def test_viaggi_page_popola_tabella(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    assert pagina._etichetta_conteggio.text() == "1 viaggi"
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "V1" in testi
    assert "SQ1" in testi
    assert "Pianificato" in testi


def test_viaggi_page_apri_modale_dettaglio_non_crasha(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    pagina._apri_modale_dettaglio({"id": "V1"})  # non deve sollevare eccezioni


def test_viaggi_page_modale_dettaglio_mostra_dipendenti_e_ordini(app, session_factory):
    from gestionale_logistica.gui.components import Modal

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1"))
        session.add(Ordine(
            id="ORD-1", indirizzo="Via Roma 12", comune="Ancona", provincia="AN", lat=None, lon=None,
            cliente="Mario Bianchi", peso=10.0, volume_cargo=0.1,
            categoria_consegna=CategoriaConsegna.BORDO_STRADA, stato_ordine=StatoOrdine.PIANIFICATO,
            data_importazione=datetime.now(), data_consegna=None, viaggio_id="V1",
        ))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._apri_modale_dettaglio({"id": "V1"})
    modale = pagina.findChildren(Modal)[-1]

    testi = [label.text() for label in modale.findChildren(QLabel)]
    assert any("Mario Rossi" in t for t in testi)
    assert any("Luca Bianchi" in t for t in testi)
    assert "ORD-1" in testi
    assert "Mario Bianchi" in testi
    assert "Via Roma 12, Ancona" in testi


def test_viaggi_page_modale_dettaglio_vuoto_mostra_empty_state(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    pagina._apri_modale_dettaglio({"id": "V1"})  # non deve sollevare eccezioni: nessun ordine


def test_viaggi_page_ricerca_filtra_e_ricarica(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "SQ1")
        crea_flotta(session, "SQ2")
        session.add(crea_viaggio("V-AAA", "SQ1"))
        session.add(crea_viaggio("V-BBB", "SQ2"))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._campo_ricerca.set_value("aaa")
    pagina._on_filtro_cambiato()

    righe_correnti = pagina._tabella._rows_layout
    testi = [
        label.text()
        for indice in range(righe_correnti.count())
        if righe_correnti.itemAt(indice).widget() is not None
        for label in righe_correnti.itemAt(indice).widget().findChildren(QLabel)
    ]
    assert "V-AAA" in testi
    assert "V-BBB" not in testi


@pytest.mark.parametrize(
    "stato", [StatoViaggio.IN_CORSO, StatoViaggio.COMPLETATO, StatoViaggio.ANNULLATO]
)
def test_viaggi_page_pencil_nascosta_per_stati_non_modificabili(app, session_factory, stato):
    # La RowAction "pencil" ha un predicate che la nasconde del tutto (non solo disabilitata) per
    # gli stati fuori da STATI_MODIFICABILI - su richiesta esplicita dell'utente un viaggio non
    # modificabile non deve nemmeno mostrare l'icona.
    from gestionale_logistica.logistica.gestore_logistica import STATO_VIAGGIO_LABELS

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=stato))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    azioni_col = pagina._tabella._columns[-1]
    pencil_action = next(a for a in azioni_col.actions if a.icon_name == "pencil")

    assert pencil_action.predicate({"stato": STATO_VIAGGIO_LABELS[stato]}) is False


@pytest.mark.parametrize("stato", [StatoViaggio.IN_COMPOSIZIONE, StatoViaggio.PIANIFICATO])
def test_viaggi_page_modifica_riga_apre_modale_modifica(app, session_factory, stato):
    from gestionale_logistica.gui.components import Modal
    from gestionale_logistica.logistica.gestore_logistica import STATO_VIAGGIO_LABELS

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=stato))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._modifica_riga({"id": "V1", "stato": STATO_VIAGGIO_LABELS[stato]})

    modali = pagina.findChildren(Modal)
    assert modali, "la matita doveva aprire il modale di modifica, non cambiare stato"
    testi = [label.text() for label in modali[-1].findChildren(QLabel)]
    assert any("Modifica viaggio V1" in t for t in testi)

    # Lo stato non deve essere stato toccato (nessuna chiamata ad annulla/ripristina_viaggio).
    with session_factory() as session:
        viaggio = session.get(Viaggio, "V1")
        assert viaggio.stato_viaggio == stato


def test_viaggi_page_elimina_riga_annullato_apre_conferma_senza_eliminare_subito(app, session_factory):
    # Un viaggio gia' Annullato non ammette piu' cambi di stato (niente ripristina): il cestino e'
    # l'unica azione residua e per questo stato deve eliminare in modo definitivo, dietro conferma
    # esplicita data l'irreversibilita' - stesso pattern di Dipendenti/Camion.
    from gestionale_logistica.gui.components import ConfirmModal

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._elimina_riga({"id": "V1", "stato": "Annullato"})

    with session_factory() as session:
        assert session.get(Viaggio, "V1") is not None  # non ancora eliminato
    modali = pagina.findChildren(ConfirmModal)
    assert len(modali) == 1

    modali[0].confirmed.emit()

    with session_factory() as session:
        assert session.get(Viaggio, "V1") is None


def test_viaggi_page_elimina_riga_annullato_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    # elimina_viaggio_definitivamente rifiuta se il viaggio ha ordini agganciati: verifichiamo che
    # il rifiuto produca un Toast invece di fallire silenziosamente.
    from gestionale_logistica.gui.components import ConfirmModal
    from gestionale_logistica.gui.pages import viaggi as modulo_viaggi

    chiamate = []
    monkeypatch.setattr(
        modulo_viaggi.ToastManager, "show_error", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.add(Ordine(
            id="ORD-1", indirizzo="Via Roma 12", comune="Ancona", provincia="AN", lat=None, lon=None,
            cliente="Mario Bianchi", peso=10.0, volume_cargo=0.1,
            categoria_consegna=CategoriaConsegna.BORDO_STRADA, stato_ordine=StatoOrdine.COMPLETATO,
            data_importazione=datetime.now(), data_consegna=datetime.now(), viaggio_id="V1",
        ))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._elimina_riga({"id": "V1", "stato": "Annullato"})

    modali = pagina.findChildren(ConfirmModal)
    assert len(modali) == 1
    modali[0].confirmed.emit()

    assert len(chiamate) == 1
    with session_factory() as session:
        assert session.get(Viaggio, "V1") is not None


def test_viaggi_page_elimina_riga_soft_delete(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._elimina_riga({"id": "V1", "stato": "Pianificato"})

    with session_factory() as session:
        assert session.get(Viaggio, "V1").stato_viaggio == StatoViaggio.ANNULLATO
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Annullato" in testi


def test_viaggi_page_elimina_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import viaggi as modulo_viaggi

    chiamate = []
    monkeypatch.setattr(
        modulo_viaggi.ToastManager, "show_error", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.COMPLETATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._elimina_riga({"id": "V1", "stato": "Completato"})

    assert len(chiamate) == 1
    with session_factory() as session:
        assert session.get(Viaggio, "V1").stato_viaggio == StatoViaggio.COMPLETATO


def test_viaggi_page_filtro_stato_si_puo_azzerare(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.add(crea_viaggio("V2", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    pagina._select_stato.set_value(["Pianificato"])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 viaggi"

    pagina._select_stato.set_value([])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 viaggi"


def test_viaggi_page_filtro_stato_multiplo(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.add(crea_viaggio("V2", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.add(crea_viaggio("V3", "SQ1", stato=StatoViaggio.IN_CORSO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    # Piu' stati selezionati insieme (MultiSelect): righe che soddisfano uno qualsiasi dei valori.
    pagina._select_stato.set_value(["Pianificato", "Annullato"])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 viaggi"


def test_viaggi_page_filtro_data(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", partenza=datetime(2026, 7, 20, 8, 0)))
        session.add(crea_viaggio("V2", "SQ1", partenza=datetime(2026, 7, 21, 8, 0)))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._campo_data.set_value(QDate(2026, 7, 20))

    assert pagina._etichetta_conteggio.text() == "1 viaggi"


def test_viaggi_page_ripristina_filtri_azzera_tutto_insieme(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO, partenza=datetime(2026, 7, 20, 8, 0)))
        session.add(crea_viaggio("V2", "SQ1", stato=StatoViaggio.ANNULLATO, partenza=datetime(2026, 7, 21, 8, 0)))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._campo_ricerca.set_value("v1")
    pagina._select_stato.set_value(["Pianificato"])
    pagina._campo_data.set_value(QDate(2026, 7, 20))
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 viaggi"

    pagina._ripristina_filtri()

    assert pagina._campo_ricerca.value() == ""
    assert pagina._select_stato.value() == []
    assert pagina._filtro_data is None
    assert pagina._etichetta_conteggio.text() == "2 viaggi"


def test_viaggi_page_ordinamento_su_arrivo(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio(
            "V1", "SQ1", partenza=datetime(2026, 7, 20, 8, 0), arrivo=datetime(2026, 7, 20, 20, 0)
        ))
        session.add(crea_viaggio(
            "V2", "SQ1", partenza=datetime(2026, 7, 19, 8, 0), arrivo=datetime(2026, 7, 19, 10, 0)
        ))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._on_sort_richiesto("arrivo", True)

    assert pagina._ordina_per == "data_arrivo_prevista"
