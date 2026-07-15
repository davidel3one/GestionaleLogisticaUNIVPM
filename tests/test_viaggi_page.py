"""Regressione GUI per ViaggiPage: stesso pattern headless di test_form_field.py."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLabel

from gestionale_logistica.database.enums import StatoOrdine, StatoViaggio
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
        km_percorsi=None, stato_viaggio=stato, composizione_id=composizione_id,
    )


def test_viaggi_page_vuota_non_crasha(app, session_factory):
    pagina = ViaggiPage(GestoreLogistica(session_factory))

    assert pagina._etichetta_conteggio.text() == "0 viaggi"
    assert pagina._tabella._rows_layout.count() == 0


def test_viaggi_page_popola_tabella(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    assert pagina._etichetta_conteggio.text() == "1 viaggi"
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "V1" in testi
    assert "Squadra SQ1" in testi
    assert "Pianificato" in testi


def test_viaggi_page_apri_modale_modifica_non_crasha(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    pagina._apri_modale_modifica({"id": "V1"})  # non deve sollevare eccezioni


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
        for label in righe_correnti.itemAt(indice).widget().findChildren(QLabel)
    ]
    assert "V-AAA" in testi
    assert "V-BBB" not in testi


def test_viaggi_page_annulla_riga_ricarica(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._annulla_riga({"id": "V1"})

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Annullato" in testi


def test_viaggi_page_annulla_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import viaggi as modulo_viaggi

    chiamate = []
    monkeypatch.setattr(
        modulo_viaggi.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.COMPLETATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._annulla_riga({"id": "V1"})

    assert len(chiamate) == 1


def test_viaggi_page_azione_annulla_nascosta_per_stati_terminali(app, session_factory):
    pagina = ViaggiPage(GestoreLogistica(session_factory))

    colonna_azioni = pagina._tabella._columns[-1]
    azione_annulla = colonna_azioni.actions[1]

    assert azione_annulla.predicate({"stato": "Pianificato"}) is True
    assert azione_annulla.predicate({"stato": "In corso"}) is True
    assert azione_annulla.predicate({"stato": "Completato"}) is False
    assert azione_annulla.predicate({"stato": "Annullato"}) is False


def test_viaggi_page_ripristina_riga_ricarica(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._ripristina_riga({"id": "V1"})

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "In composizione" in testi


def test_viaggi_page_ripristina_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import viaggi as modulo_viaggi

    chiamate = []
    monkeypatch.setattr(
        modulo_viaggi.QMessageBox, "warning", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))
    pagina._ripristina_riga({"id": "V1"})

    assert len(chiamate) == 1


def test_viaggi_page_azione_ripristino_solo_per_annullati(app, session_factory):
    pagina = ViaggiPage(GestoreLogistica(session_factory))

    colonna_azioni = pagina._tabella._columns[-1]
    azione_ripristino = colonna_azioni.actions[2]

    assert azione_ripristino.predicate({"stato": "Pianificato"}) is False
    assert azione_ripristino.predicate({"stato": "In corso"}) is False
    assert azione_ripristino.predicate({"stato": "Completato"}) is False
    assert azione_ripristino.predicate({"stato": "Annullato"}) is True


def test_viaggi_page_filtro_stato_si_puo_azzerare(app, session_factory):
    with session_factory() as session:
        crea_flotta(session)
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.add(crea_viaggio("V2", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.commit()

    pagina = ViaggiPage(GestoreLogistica(session_factory))

    pagina._select_stato.set_value("Pianificato")
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 viaggi"

    pagina._select_stato.set_value(None)
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
    pagina._select_stato.set_value("Pianificato")
    pagina._campo_data.set_value(QDate(2026, 7, 20))
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 viaggi"

    pagina._ripristina_filtri()

    assert pagina._campo_ricerca.value() == ""
    assert pagina._select_stato.value() is None
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
