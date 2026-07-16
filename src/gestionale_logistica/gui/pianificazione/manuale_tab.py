"""Tab "Manuale" di Pianificazione (RF10 avvio/chiusura composizione, RF11 aggiunta ordini con
validazione idoneità/capacità)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QVBoxLayout, QWidget
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components import EmptyState
from gestionale_logistica.gui.pianificazione.components import AvvioCard, CompositionCard
from gestionale_logistica.gui.pianificazione.pianificazione_data import (
    costruisci_stato_composizione,
    elenca_composizioni_disponibili,
    elenca_ordini_candidati,
)
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.ottimizzazione.gestore_configurazione import GestoreConfigurazione


class ManualeTab(QWidget):
    def __init__(self, session_factory: sessionmaker = SessionLocal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._gestore = GestoreLogistica(session_factory)
        self._gestore_config = GestoreConfigurazione(session_factory)
        self._viaggio_id: str | None = None

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
                # hide() subito: deleteLater() e' differita al prossimo giro di event loop, e un
                # widget rimosso dal layout con takeAt() resta visibile alla sua ultima geometria
                # finche' non viene nascosto o distrutto (takeAt() lo scollega dal layout, non lo
                # nasconde) - senza hide() si vede un frame con il vecchio widget ancora in vista.
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
        self._card.aggiungiOrdineRequested.connect(self._aggiungi_ordine)
        self._card.annullaRequested.connect(self._annulla)
        self._card.chiudiViaggioRequested.connect(self._chiudi_viaggio)
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
        assegnati = {riga.ordine_id for riga in stato.righe_ordini}
        candidati = [
            (oid, cliente)
            for oid, cliente in elenca_ordini_candidati(self._session_factory)
            if oid not in assegnati
        ]
        self._card.set_ordini_disponibili(candidati)

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
        self._show_composizione_card()
        self._refresh_composizioni_disponibili()

    def _aggiungi_ordine(self, ordine_id: str) -> None:
        if self._viaggio_id is None:
            return
        esito = self._gestore.aggiungi_ordine_a_viaggio(self._viaggio_id, ordine_id)
        if not esito.ammesso:
            self._card.show_alert(esito.motivo or "Ordine non ammesso")
            return
        self._card.hide_alert()
        self._refresh_composizione_card()

    def _annulla(self) -> None:
        # Nessun metodo di GestoreLogistica scarta un viaggio IN_COMPOSIZIONE già avviato: la riga
        # resta a DB (stato IN_COMPOSIZIONE, nessun ordine se non se n'è aggiunto nessuno). "Annulla"
        # qui azzera solo la vista corrente, non è una vera cancellazione (fuori scope: nessun RF
        # la richiede e GestoreLogistica non espone un'operazione di eliminazione).
        self._viaggio_id = None
        self._show_empty_state()

    def _chiudi_viaggio(self) -> None:
        if self._viaggio_id is None:
            return
        esito = self._gestore.chiudi_composizione_viaggio(self._viaggio_id)
        if not esito.ok:
            self._card.show_alert(esito.motivo or "Impossibile chiudere il viaggio")
            return
        self._viaggio_id = None
        self._show_empty_state()
        self._refresh_composizioni_disponibili()
