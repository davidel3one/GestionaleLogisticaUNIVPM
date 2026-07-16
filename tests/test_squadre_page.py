"""Regressione GUI per SquadrePage: stesso pattern headless di test_form_field.py."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Squadra, Viaggio
from gestionale_logistica.gui.pages import SquadrePage
from gestionale_logistica.risorse.gestore_squadre import STATO_ATTIVA, STATO_NON_ATTIVA, GestoreSquadre


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def crea_flotta(session, comp_id="1"):
    session.add(Squadra(id=comp_id, flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
    session.add(Dipendente(
        id=f"D{comp_id}-1", nome="Mario", cognome="Rossi", codice_fiscale=f"CF-{comp_id}-1",
        data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
        flg_attivo=True, flg_certificazione_gas=False,
    ))
    session.add(Dipendente(
        id=f"D{comp_id}-2", nome="Luca", cognome="Bianchi", codice_fiscale=f"CF-{comp_id}-2",
        data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
        flg_attivo=True, flg_certificazione_gas=False,
    ))
    session.add(Camion(
        id=f"CAM-{comp_id}", targa=f"AB{comp_id}23CD", tipo_mezzo="Furgone", peso_massimo=1000.0,
        volume_massimo=10.0, flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1),
        data_dismissione=None, flg_attivo=True,
    ))
    session.add(ComposizioneSquadra(
        id_composizione=comp_id, squadra_id=comp_id, camion_id=f"CAM-{comp_id}",
        dipendente_1_id=f"D{comp_id}-1", dipendente_2_id=f"D{comp_id}-2",
        data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
    ))


def test_squadre_page_vuota_non_crasha(app, session_factory):
    pagina = SquadrePage(GestoreSquadre(session_factory))

    assert pagina._etichetta_conteggio.text() == "0 squadre"
    assert pagina._tabella._rows_layout.count() == 1  # solo lo stretch finale, nessuna riga


def test_squadre_page_popola_tabella(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))

    assert pagina._etichetta_conteggio.text() == "1 squadre"
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "#1" in testi
    assert "Mario Rossi, Luca Bianchi" in testi
    assert "AB123CD" in testi
    assert "Attiva" in testi


def test_squadre_page_apri_modale_aggiungi_non_crasha(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))
    pagina._apri_modale_aggiungi()  # non deve sollevare eccezioni


def test_squadre_page_apri_modale_dettaglio_con_viaggi_non_crasha(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="1",
        ))
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))
    pagina._apri_modale_dettaglio({"id": "1"})


def test_squadre_page_apri_modale_dettaglio_vuoto_non_crasha(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))
    pagina._apri_modale_dettaglio({"id": "1"})  # nessun viaggio: ramo EmptyState


def test_squadre_page_crea_squadra_completa_dal_modale(app, session_factory):
    with session_factory() as session:
        session.add(Camion(
            id="CAM1", targa="AB123CD", tipo_mezzo="Furgone", peso_massimo=1000.0,
            volume_massimo=10.0, flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1),
            data_dismissione=None, flg_attivo=True,
        ))
        session.add(Dipendente(
            id="D1", nome="Mario", cognome="Rossi", codice_fiscale="CF-1",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=True, flg_certificazione_gas=False,
        ))
        session.add(Dipendente(
            id="D2", nome="Luca", cognome="Bianchi", codice_fiscale="CF-2",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=True, flg_certificazione_gas=False,
        ))
        session.commit()

    gestore = GestoreSquadre(session_factory)
    pagina = SquadrePage(gestore)

    opzioni_camion = pagina._opzioni_camion()
    opzioni_dipendenti = pagina._opzioni_dipendenti()
    camion_id = opzioni_camion["AB123CD"]
    dip_1_id = next(v for k, v in opzioni_dipendenti.items() if k.startswith("Mario Rossi"))
    dip_2_id = next(v for k, v in opzioni_dipendenti.items() if k.startswith("Luca Bianchi"))

    nuovo_id = pagina._prossimo_id_squadra()
    risultato_squadra = gestore.crea_squadra(nuovo_id, data_creazione=datetime.now())
    assert risultato_squadra.ok
    risultato_composizione = gestore.apri_composizione(
        id_composizione=nuovo_id, squadra_id=nuovo_id,
        camion_id=camion_id, dipendente_1_id=dip_1_id, dipendente_2_id=dip_2_id,
    )
    assert risultato_composizione.ok

    pagina._reload()
    assert pagina._etichetta_conteggio.text() == "1 squadre"


def test_squadre_page_modifica_riga_disattiva_ricarica(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))
    pagina._modifica_riga({"id": "1", "stato": STATO_ATTIVA})

    # Soft-delete: la riga sparisce dalla vista di default (non un badge "Non attiva" in tabella).
    assert pagina._etichetta_conteggio.text() == "0 squadre"
    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    assert "Non attiva" not in testi


def test_squadre_page_modifica_riga_riattiva(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    pagina = SquadrePage(gestore)
    pagina._modifica_riga({"id": "1", "stato": STATO_ATTIVA})
    pagina._modifica_riga({"id": "1", "stato": STATO_NON_ATTIVA})

    with session_factory() as session:
        assert session.get(Squadra, "1").flg_attiva is True

    assert pagina._etichetta_conteggio.text() == "1 squadre"


def test_squadre_page_elimina_riga_soft_delete(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    pagina = SquadrePage(gestore)
    pagina._elimina_riga({"id": "1", "stato": STATO_ATTIVA})

    with session_factory() as session:
        assert session.get(Squadra, "1").flg_attiva is False

    # Soft-delete: la riga sparisce dalla vista di default ma resta filtrabile.
    assert pagina._etichetta_conteggio.text() == "0 squadre"
    pagina._select_stato.set_value([STATO_NON_ATTIVA])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 squadre"


def test_squadre_page_modifica_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import squadre as modulo_squadre

    chiamate = []
    monkeypatch.setattr(
        modulo_squadre.ToastManager, "show_error", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        crea_flotta(session, "1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="1",
        ))
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))
    pagina._modifica_riga({"id": "1", "stato": STATO_ATTIVA})

    assert len(chiamate) == 1


def test_squadre_page_elimina_riga_rifiutata_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages import squadre as modulo_squadre

    chiamate = []
    monkeypatch.setattr(
        modulo_squadre.ToastManager, "show_error", lambda *args: chiamate.append(args) or None
    )

    with session_factory() as session:
        crea_flotta(session, "1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 10, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 10, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="1",
        ))
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))
    pagina._elimina_riga({"id": "1", "stato": STATO_ATTIVA})

    assert len(chiamate) == 1
    with session_factory() as session:
        assert session.get(Squadra, "1").flg_attiva is True


def test_squadre_page_numerazione_senza_buchi_dopo_eliminazione(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        crea_flotta(session, "2")
        crea_flotta(session, "3")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.elimina_squadra("2")
    pagina = SquadrePage(gestore)

    testi = [label.text() for label in pagina._tabella.findChildren(QLabel)]
    # Restano solo le squadre "1" e "3" (id reali), ma la colonna Squadra le mostra numerate
    # in sequenza senza buchi: #1 e #2, non #1 e #3.
    assert "#1" in testi
    assert "#2" in testi
    assert "#3" not in testi


def test_squadre_page_ricerca_filtra_e_ricarica(app, session_factory):
    with session_factory() as session:
        crea_flotta(session, "1")
        crea_flotta(session, "2")
        session.commit()

    pagina = SquadrePage(GestoreSquadre(session_factory))
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
    assert "AB223CD" not in testi


def test_squadre_page_filtro_stato_si_puo_azzerare(app, session_factory):
    from gestionale_logistica.risorse.gestore_squadre import STATO_ATTIVA

    with session_factory() as session:
        crea_flotta(session, "1")
        crea_flotta(session, "2")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.elimina_squadra("2")
    pagina = SquadrePage(gestore)

    pagina._select_stato.set_value([STATO_ATTIVA])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 squadre"

    # Azzerare il filtro torna a "Tutte", che pero' esclude comunque le Non attiva (squadra "2"):
    # resta visibile solo la squadra "1".
    pagina._select_stato.set_value([])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 squadre"


def test_squadre_page_filtro_stato_multiplo(app, session_factory):
    from gestionale_logistica.risorse.gestore_squadre import STATO_ATTIVA, STATO_NON_ATTIVA

    with session_factory() as session:
        crea_flotta(session, "1")
        crea_flotta(session, "2")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.elimina_squadra("2")
    pagina = SquadrePage(gestore)

    # Selezionando Attiva + Non attiva insieme (MultiSelect) tornano visibili entrambe le squadre,
    # a differenza del filtro vuoto che nasconde le Non attiva di default.
    pagina._select_stato.set_value([STATO_ATTIVA, STATO_NON_ATTIVA])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "2 squadre"


def test_squadre_page_ripristina_filtri_azzera_tutto_insieme(app, session_factory):
    from gestionale_logistica.risorse.gestore_squadre import STATO_ATTIVA

    with session_factory() as session:
        crea_flotta(session, "1")
        crea_flotta(session, "2")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.elimina_squadra("2")
    pagina = SquadrePage(gestore)

    pagina._campo_ricerca.set_value("ab123")
    pagina._select_stato.set_value([STATO_ATTIVA])
    pagina._on_filtro_cambiato()
    assert pagina._etichetta_conteggio.text() == "1 squadre"

    pagina._ripristina_filtri()

    assert pagina._campo_ricerca.value() == ""
    assert pagina._select_stato.value() == []
    # "Tutte" dopo il reset esclude comunque la squadra "2" (Non attiva): resta solo la "1".
    assert pagina._etichetta_conteggio.text() == "1 squadre"
