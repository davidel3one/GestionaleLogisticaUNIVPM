"""Tab "Assistita" di Pianificazione (RF12): da un viaggio in composizione, il motore di
ottimizzazione suggerisce gli ordini rimanenti più idonei per saturare il carico."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtWidgets import QVBoxLayout, QWidget
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components import EmptyState
from gestionale_logistica.gui.pianificazione.components import (
    AvvioCard,
    CompositionCard,
    SuggestionSection,
)
from gestionale_logistica.gui.pianificazione.pianificazione_data import (
    costruisci_righe_suggerimento,
    costruisci_stato_composizione,
    elenca_composizioni_disponibili,
)
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import MotoreOttimizzazione

DURATA_VIAGGIO_DEFAULT = timedelta(hours=8)
ORA_PARTENZA_DEFAULT = time(8, 0)
FOOTER_PRIMARY_LABEL = "Applica suggerimento e chiudi viaggio"


class AssistitaTab(QWidget):
    def __init__(self, session_factory: sessionmaker = SessionLocal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._gestore = GestoreLogistica(session_factory)
        self._motore = MotoreOttimizzazione(session_factory)
        self._viaggio_id: str | None = None
        self._ordini_suggeriti: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(28)

        self._avvio_card = AvvioCard()
        self._avvio_card.avviaRequested.connect(self._avvia_composizione)
        self._avvio_card.dataChanged.connect(self._on_data_changed)
        outer.addWidget(self._avvio_card)

        self._composizione_container = QVBoxLayout()
        self._composizione_container.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._composizione_container, 1)
        self._show_empty_state()

        self._refresh_composizioni_disponibili()

    def _on_data_changed(self, _giorno: date) -> None:
        self._refresh_composizioni_disponibili()

    def _refresh_composizioni_disponibili(self) -> None:
        giorno = self._avvio_card.data_selezionata()
        self._avvio_card.set_composizioni_disponibili(
            elenca_composizioni_disponibili(giorno, self._session_factory)
        )

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
        self._card.set_footer_primary_label(FOOTER_PRIMARY_LABEL)
        self._card.annullaRequested.connect(self._annulla)
        self._card.chiudiViaggioRequested.connect(self._applica_e_chiudi)

        self._suggestion_section = SuggestionSection()
        self._suggestion_section.suggerisciRequested.connect(self._suggerisci_ordini)
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
        ora_partenza = datetime.combine(giorno, ORA_PARTENZA_DEFAULT)
        esito = self._gestore.avvia_composizione_viaggio(
            composizione_id, ora_partenza, DURATA_VIAGGIO_DEFAULT
        )
        if not esito.ok:
            self._avvio_card.show_alert(esito.motivo or "Impossibile avviare la composizione")
            return

        self._avvio_card.hide_alert()
        self._viaggio_id = esito.viaggio_id
        self._ordini_suggeriti = []
        self._show_composizione_card()
        self._refresh_composizioni_disponibili()

    def _suggerisci_ordini(self) -> None:
        if self._viaggio_id is None:
            return
        suggerimento = self._motore.suggerisci_ordini(self._viaggio_id)
        self._ordini_suggeriti = suggerimento.ordini_suggeriti
        righe = costruisci_righe_suggerimento(suggerimento, self._session_factory)
        self._suggestion_section.set_suggerimento(
            righe,
            suggerimento.peso_utilizzato,
            suggerimento.peso_disponibile,
            suggerimento.volume_utilizzato,
            suggerimento.volume_disponibile,
        )

    def _annulla(self) -> None:
        # Vedi la stessa nota in ManualeTab._annulla: nessun metodo di GestoreLogistica scarta un
        # viaggio IN_COMPOSIZIONE già avviato, "Annulla" azzera solo la vista corrente.
        self._viaggio_id = None
        self._ordini_suggeriti = []
        self._show_empty_state()

    def _applica_e_chiudi(self) -> None:
        if self._viaggio_id is None:
            return
        for ordine_id in self._ordini_suggeriti:
            esito = self._gestore.aggiungi_ordine_a_viaggio(self._viaggio_id, ordine_id)
            if not esito.ammesso:
                self._card.show_alert(esito.motivo or "Ordine non ammesso")
                self._refresh_composizione_card()
                return

        esito_chiusura = self._gestore.chiudi_composizione_viaggio(self._viaggio_id)
        if not esito_chiusura.ok:
            self._card.show_alert(esito_chiusura.motivo or "Impossibile chiudere il viaggio")
            return

        self._viaggio_id = None
        self._ordini_suggeriti = []
        self._show_empty_state()
        self._refresh_composizioni_disponibili()
