"""Tab "Assistita" di Pianificazione (RF12): da un viaggio in composizione, il motore di
ottimizzazione suggerisce gli ordini rimanenti più idonei per saturare il carico."""

from __future__ import annotations

from concurrent.futures import Future
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components import MINIMAL_SCROLLBAR_QSS, EmptyState
from gestionale_logistica.gui.pianificazione.components import (
    AvvioCard,
    CompositionCard,
    RigaOrdineSuggerito,
    SuggestionSection,
)
from gestionale_logistica.gui.pianificazione.pianificazione_data import (
    costruisci_righe_suggerimento,
    costruisci_stato_composizione,
    descrizione_composizioni_disponibili,
    elenca_composizioni_disponibili,
)
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.ottimizzazione.gestore_configurazione import GestoreConfigurazione
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import MotoreOttimizzazione, SuggerimentoOrdini


class AssistitaTab(QWidget):
    # Il risultato di suggerisci_ordini_async arriva su un thread in background (RNF3, il solve
    # CBC può richiedere tempo con molti ordini candidati): emesso come Signal (thread-safe in Qt
    # anche da un thread non-Qt) invece di toccare i widget da lì — stesso pattern di
    # AutomaticaTab._pianoCalcolato.
    _suggerimentoCalcolato = Signal(object, str)  # Future[SuggerimentoOrdini], viaggio_id
    viaggioChiuso = Signal()

    def __init__(self, session_factory: sessionmaker = SessionLocal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._gestore = GestoreLogistica(session_factory)
        self._motore = MotoreOttimizzazione(session_factory)
        self._gestore_config = GestoreConfigurazione(session_factory)
        self._viaggio_id: str | None = None
        self._righe_suggerimento: list[RigaOrdineSuggerito] = []

        self._suggerimentoCalcolato.connect(self._on_suggerimento_calcolato)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(28)

        self._avvio_card = AvvioCard()
        self._avvio_card.avviaRequested.connect(self._avvia_composizione)
        self._avvio_card.dataChanged.connect(self._on_data_changed)
        outer.addWidget(self._avvio_card)

        self._composizione_container = QVBoxLayout()
        self._composizione_container.setContentsMargins(0, 0, 0, 0)

        # La Composizione Card (ordini nel viaggio + tabella paginata dei suggerimenti) non ha
        # un'altezza superiore limitata: senza scroll, con molti ordini suggeriti il contenuto
        # sfonda il bordo inferiore della finestra e nasconde i pulsanti "Annulla/Applica" (bug
        # osservato con 148 ordini idonei). Stesso pattern già usato dal pannello "Attività
        # recente" della Dashboard (QScrollArea + MINIMAL_SCROLLBAR_QSS), qui applicato all'intera
        # area sotto "Avvia composizione viaggio" invece che a un singolo pannello.
        composizione_content = QWidget()
        composizione_content.setStyleSheet("background: transparent;")
        composizione_content.setLayout(self._composizione_container)

        composizione_scroll = QScrollArea()
        composizione_scroll.setWidgetResizable(True)
        composizione_scroll.setFrameShape(QFrame.Shape.NoFrame)
        composizione_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        composizione_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        composizione_scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }} {MINIMAL_SCROLLBAR_QSS}"
        )
        composizione_scroll.setWidget(composizione_content)
        outer.addWidget(composizione_scroll, 1)

        self._show_empty_state()

        self._refresh_composizioni_disponibili()

    def _on_data_changed(self, _giorno: date) -> None:
        self._refresh_composizioni_disponibili()

    def _refresh_composizioni_disponibili(self) -> None:
        giorno = self._avvio_card.data_selezionata()
        self._avvio_card.set_composizioni_disponibili(
            elenca_composizioni_disponibili(giorno, self._session_factory)
        )
        self._avvio_card.set_hint(descrizione_composizioni_disponibili(giorno, self._session_factory))

    # -- Composizione Card / stato vuoto ----------------------------------------------------

    def _clear_composizione_container(self) -> None:
        while self._composizione_container.count():
            item = self._composizione_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _show_empty_state(self) -> None:
        self._clear_composizione_container()
        self._composizione_container.addWidget(
            EmptyState(
                "Nessun viaggio in composizione",
                "Scegli una composizione squadra e premi «Avvia composizione» per iniziare",
                "route",
            )
        )

    def _show_composizione_card(self) -> None:
        self._clear_composizione_container()
        self._card = CompositionCard()
        self._card.set_manual_add_visible(False)
        self._card.annullaRequested.connect(self._annulla)
        self._card.chiudiViaggioRequested.connect(self._chiudi_viaggio)

        self._suggestion_section = SuggestionSection()
        self._suggestion_section.suggerisciRequested.connect(self._suggerisci_ordini)
        self._suggestion_section.aggiungiOrdineRequested.connect(self._aggiungi_ordine_suggerito)
        self._card.add_extra_section(self._suggestion_section)

        self._composizione_container.addWidget(self._card)
        self._refresh_composizione_card()

    def _refresh_composizione_card(self) -> None:
        if self._viaggio_id is None:
            return
        stato = costruisci_stato_composizione(self._viaggio_id, self._session_factory)
        if stato is None:
            return
        self._card.set_intestazione(
            stato.squadra_label,
            stato.camion_label,
            stato.partenza_label,
            stato.peso_occupato,
            stato.peso_massimo,
            stato.volume_occupato,
            stato.volume_massimo,
        )
        self._card.set_ordini(stato.righe_ordini)

    # -- Azioni --------------------------------------------------------------------------------

    def _avvia_composizione(self, composizione_id: str, giorno: date) -> None:
        configurazione = self._gestore_config.leggi()
        ora_partenza = datetime.combine(giorno, configurazione.ora_partenza_default)
        durata_viaggio = timedelta(hours=configurazione.ore_lavoro)
        esito = self._gestore.avvia_composizione_viaggio(composizione_id, ora_partenza, durata_viaggio)
        if not esito.ok:
            self._avvio_card.show_alert(esito.motivo or "Impossibile avviare la composizione")
            return

        self._avvio_card.hide_alert()
        self._viaggio_id = esito.viaggio_id
        self._righe_suggerimento = []
        self._show_composizione_card()
        self._refresh_composizioni_disponibili()

    def _suggerisci_ordini(self) -> None:
        if self._viaggio_id is None:
            return
        viaggio_id = self._viaggio_id
        self._suggestion_section.set_loading(True)
        future = self._motore.suggerisci_ordini_async(viaggio_id)
        future.add_done_callback(lambda f: self._suggerimentoCalcolato.emit(f, viaggio_id))

    def _on_suggerimento_calcolato(self, future: "Future[SuggerimentoOrdini]", viaggio_id: str) -> None:
        if viaggio_id != self._viaggio_id:
            # Il viaggio e' stato annullato/chiuso/cambiato mentre il calcolo era in corso: la
            # Composizione Card di allora (con questa _suggestion_section) e' gia' stata
            # deleteLater()-ata da _clear_composizione_container, non toccarla.
            return
        self._suggestion_section.set_loading(False)
        suggerimento = future.result()
        self._righe_suggerimento = costruisci_righe_suggerimento(suggerimento, self._session_factory)
        self._suggestion_section.set_suggerimento(
            self._righe_suggerimento,
            suggerimento.peso_utilizzato,
            suggerimento.peso_disponibile,
            suggerimento.volume_utilizzato,
            suggerimento.volume_disponibile,
        )

    def _aggiungi_ordine_suggerito(self, ordine_id: str) -> None:
        if self._viaggio_id is None:
            return
        esito = self._gestore.aggiungi_ordine_a_viaggio(self._viaggio_id, ordine_id)
        if not esito.ammesso:
            self._card.show_alert(esito.motivo or "Ordine non ammesso")
            return

        self._card.hide_alert()
        self._refresh_composizione_card()

        # L'ordine appena aggiunto esce dalla lista suggerimenti; le righe restanti restavano
        # dentro la capacità insieme a questo ordine (erano tutte parte dello stesso suggerimento),
        # quindi restano valide senza un nuovo solve — non emergono però eventuali ordini che ora
        # rientrerebbero nella capacità appena liberata (serve ripremere "Suggerisci ordini").
        self._righe_suggerimento = [r for r in self._righe_suggerimento if r.ordine_id != ordine_id]
        stato = costruisci_stato_composizione(self._viaggio_id, self._session_factory)
        if stato is None:
            return
        peso_dopo = stato.peso_occupato + sum(r.peso for r in self._righe_suggerimento)
        volume_dopo = stato.volume_occupato + sum(r.volume for r in self._righe_suggerimento)
        self._suggestion_section.set_suggerimento(
            self._righe_suggerimento, peso_dopo, stato.peso_massimo, volume_dopo, stato.volume_massimo
        )

    def _annulla(self) -> None:
        # Vedi la stessa nota in ManualeTab._annulla: nessun metodo di GestoreLogistica scarta un
        # viaggio IN_COMPOSIZIONE già avviato, "Annulla" azzera solo la vista corrente.
        self._viaggio_id = None
        self._righe_suggerimento = []
        self._show_empty_state()

    def _chiudi_viaggio(self) -> None:
        if self._viaggio_id is None:
            return
        esito = self._gestore.chiudi_composizione_viaggio(self._viaggio_id)
        if not esito.ok:
            self._card.show_alert(esito.motivo or "Impossibile chiudere il viaggio")
            return

        self._viaggio_id = None
        self._righe_suggerimento = []
        self._show_empty_state()
        self._refresh_composizioni_disponibili()
        self.viaggioChiuso.emit()
