"""Regressione GUI per RegistraEsitoModal: stesso pattern headless di test_ordini_page.py."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from gestionale_logistica.database.enums import CategoriaConsegna, StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Camion,
    CausaleFallimento,
    ComposizioneSquadra,
    Dipendente,
    EsitoConsegna,
    Ordine,
    Squadra,
    Viaggio,
)
from gestionale_logistica.gui.pages.ordini._registra_esito_modal import RegistraEsitoModal
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _crea_flotta_e_viaggio_in_corso(session, viaggio_id="V1", squadra_id="SQ1"):
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


def _crea_ordine_in_transito(session, ordine_id="ORD-1", viaggio_id="V1"):
    ordine = Ordine(
        id=ordine_id, indirizzo="Via Roma 12", comune="Ancona", provincia="AN", lat=None, lon=None,
        cliente="Mario Rossi", peso=45.0, volume_cargo=0.3,
        categoria_consegna=CategoriaConsegna.BORDO_STRADA,
        stato_ordine=StatoOrdine.PIANIFICATO, data_importazione=datetime.now(),
        data_consegna=None, viaggio_id=viaggio_id,
    )
    session.add(ordine)
    return ordine


def _riga(ordine_id="ORD-1"):
    return {"id": ordine_id, "cliente": "Mario Rossi", "indirizzo": "Via Roma 12, Ancona", "peso_volume": "45 kg · 0.3 m³"}


def test_modal_salva_disabilitato_finche_non_si_sceglie_esito(app, session_factory):
    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        _crea_ordine_in_transito(session)
        session.commit()

    modal = RegistraEsitoModal(_riga(), GestoreRendicontazione(session_factory))

    assert modal._btn_salva.isEnabled() is False


def test_modal_completato_abilita_salva_subito(app, session_factory):
    modal = RegistraEsitoModal(_riga(), GestoreRendicontazione(session_factory))

    modal._toggle._seleziona(StatoEsito.COMPLETATO)

    assert modal._btn_salva.isEnabled() is True
    assert modal._select_causale.isVisible() is False


def test_modal_fallito_richiede_causale_e_almeno_una_prova(app, session_factory):
    modal = RegistraEsitoModal(_riga(), GestoreRendicontazione(session_factory))
    modal.show()  # isVisible() riflette la gerarchia reale solo su un widget mostrato

    modal._toggle._seleziona(StatoEsito.FALLITO)
    assert modal._btn_salva.isEnabled() is False
    assert modal._select_causale.isVisible() is True
    assert modal._dropzone.isVisible() is True

    modal._select_causale.set_value("Cliente assente")
    assert modal._btn_salva.isEnabled() is False  # causale c'e', manca ancora la prova

    modal._dropzone.fileSelected.emit(Path("foto_portone.jpg"))
    assert modal._btn_salva.isEnabled() is True


def test_modal_rimuovi_prova_nuova_disabilita_salva_se_era_l_unica(app, session_factory):
    modal = RegistraEsitoModal(_riga(), GestoreRendicontazione(session_factory))
    modal.show()
    modal._toggle._seleziona(StatoEsito.FALLITO)
    modal._select_causale.set_value("Cliente assente")
    modal._dropzone.fileSelected.emit(Path("foto_portone.jpg"))
    assert modal._btn_salva.isEnabled() is True

    modal._rimuovi_prova_nuova("foto_portone.jpg")

    assert modal._percorsi_prova_nuovi == []
    assert modal._btn_salva.isEnabled() is False
    assert modal._lista_prove_widget.isVisible() is False


def test_modal_salva_completato_chiama_registra_esito(app, session_factory):
    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        _crea_ordine_in_transito(session)
        session.commit()

    chiamate = []
    modal = RegistraEsitoModal(_riga(), GestoreRendicontazione(session_factory))
    modal.esitoRegistrato.connect(lambda: chiamate.append(True))
    modal._toggle._seleziona(StatoEsito.COMPLETATO)

    modal._on_salva()

    assert chiamate == [True]
    with session_factory() as session:
        assert session.get(Ordine, "ORD-1").stato_ordine == StatoOrdine.COMPLETATO


def test_modal_salva_fallito_con_causale_e_prova_carica_allegato(app, session_factory, tmp_path):
    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        _crea_ordine_in_transito(session)
        session.add(CausaleFallimento(codice="CLIENTE_ASSENTE", descrizione="Cliente assente"))
        session.commit()

    cartella_allegati = tmp_path / "allegati"
    gestore = GestoreRendicontazione(session_factory, cartella_allegati=cartella_allegati)
    modal = RegistraEsitoModal(_riga(), gestore)
    modal.show()
    modal._toggle._seleziona(StatoEsito.FALLITO)
    modal._select_causale.set_value("Cliente assente")

    prova_1 = tmp_path / "foto_portone.jpg"
    prova_1.write_bytes(b"contenuto finto 1")
    modal._dropzone.fileSelected.emit(prova_1)
    prova_2 = tmp_path / "foto_citofono.jpg"
    prova_2.write_bytes(b"contenuto finto 2")
    modal._dropzone.fileSelected.emit(prova_2)
    assert modal._lista_prove_widget.isVisible() is True
    assert modal._numero_prove_totali() == 2

    modal._on_salva()

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-1")
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO
        assert ordine.viaggio_id is None
        assert len(list(cartella_allegati.rglob("*_foto_portone.jpg"))) == 1
        assert len(list(cartella_allegati.rglob("*_foto_citofono.jpg"))) == 1


def test_modal_salva_rifiutato_mostra_avviso(app, session_factory, monkeypatch):
    from gestionale_logistica.gui.pages.ordini import _registra_esito_modal as modulo

    # Nessun viaggio in DB: registra_esito rifiuta con "ordine non trovato".
    chiamate = []
    monkeypatch.setattr(
        modulo.ToastManager, "show_error", lambda *args: chiamate.append(args) or None
    )

    modal = RegistraEsitoModal(_riga("INESISTENTE"), GestoreRendicontazione(session_factory))
    modal._toggle._seleziona(StatoEsito.COMPLETATO)

    modal._on_salva()

    assert len(chiamate) == 1


def test_modal_modifica_precompila_esito_causale_e_allegati_esistenti(app, session_factory, tmp_path):
    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        _crea_ordine_in_transito(session)
        session.add(CausaleFallimento(codice="CLIENTE_ASSENTE", descrizione="Cliente assente"))
        session.commit()
    gestore = GestoreRendicontazione(session_factory, cartella_allegati=tmp_path / "allegati")
    risultato = gestore.registra_esito("ORD-1", StatoEsito.FALLITO, causale_codice="CLIENTE_ASSENTE")
    sorgente = tmp_path / "foto_portone.jpg"
    sorgente.write_bytes(b"contenuto")
    gestore.carica_prova_documentale(risultato.esito_id, "foto_portone.jpg", str(sorgente), "image/jpeg")

    riga = _riga() | {"esito": "Fallito", "causale_codice": "CLIENTE_ASSENTE"}
    modal = RegistraEsitoModal(riga, gestore, esito_id=risultato.esito_id)
    modal.show()

    assert modal._toggle.value() == StatoEsito.FALLITO
    assert modal._select_causale.value() == "Cliente assente"
    assert [a.nome_file for a in modal._allegati_esistenti] == ["foto_portone.jpg"]
    assert modal._lista_prove_widget.isVisible() is True
    # Occhio (esito gia' Fallito): solo causale + anteprima allegati, sola lettura - niente
    # toggle, niente dropzone, niente bottone "Salva" nel footer, "Chiudi" al posto di "Annulla".
    assert modal._toggle.isVisible() is False
    assert modal._etichetta_esito.isVisible() is False
    assert modal._select_causale.isVisible() is True
    assert modal._select_causale.isEnabled() is False
    assert modal._nota_ripianificazione.isVisible() is False
    assert modal._dropzone.isVisible() is False
    assert modal._btn_salva.parent() is None  # mai aggiunto al footer in questa modalita'
    assert modal._btn_annulla.findChild(QLabel).text() == "Chiudi"

    # Anche selezionando programmaticamente un file (es. drag&drop diretto sul widget nascosto),
    # non deve comparire tra le prove: la dropzone e' invisibile ma tecnicamente ancora un
    # QWidget funzionante, verifichiamo che il flusso resti "sola lettura" a livello di dati.
    modal._dropzone.fileSelected.emit(Path("non_dovrebbe_comparire.jpg"))
    assert modal._percorsi_prova_nuovi == []


def test_modal_modifica_completato_mostra_il_toggle(app, session_factory):
    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        _crea_ordine_in_transito(session)
        session.commit()
    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("ORD-1", StatoEsito.COMPLETATO)

    riga = _riga() | {"esito": "Completato", "causale_codice": None}
    modal = RegistraEsitoModal(riga, gestore, esito_id=risultato.esito_id)
    modal.show()

    # Matita (esito Completato, puo' ancora essere corretto a Fallito): toggle visibile.
    assert modal._toggle.isVisible() is True
    assert modal._etichetta_esito.isVisible() is True


def test_modal_modifica_salva_chiama_modifica_esito_non_registra_esito(app, session_factory):
    with session_factory() as session:
        _crea_flotta_e_viaggio_in_corso(session)
        _crea_ordine_in_transito(session)
        session.add(CausaleFallimento(codice="CLIENTE_ASSENTE", descrizione="Cliente assente"))
        session.commit()
    gestore = GestoreRendicontazione(session_factory)
    risultato = gestore.registra_esito("ORD-1", StatoEsito.COMPLETATO)

    riga = _riga() | {"esito": "Completato", "causale_codice": None}
    modal = RegistraEsitoModal(riga, gestore, esito_id=risultato.esito_id)
    modal.show()
    # Corregge Completato -> Fallito: se il modale chiamasse registra_esito invece di
    # modifica_esito verrebbe rifiutato (l'ordine ha gia' un EsitoConsegna per V1, controllo
    # di idempotenza di registra_esito) - la sola riuscita basta a provare che sta chiamando
    # il metodo giusto.
    modal._toggle._seleziona(StatoEsito.FALLITO)
    modal._select_causale.set_value("Cliente assente")

    modal._on_salva()

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-1")
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO
        assert ordine.viaggio_id is None
        esito = session.get(EsitoConsegna, risultato.esito_id)
        assert esito.stato_esito == StatoEsito.FALLITO
        assert esito.causale_id == "CLIENTE_ASSENTE"
