"""Tab "Automatica" di Pianificazione (RF13): calcolo del piano giornaliero massivo dal motore di
ottimizzazione (RNF3, in background per non bloccare la GUI fino ai 3 minuti di RNF4), anteprima
in una Proposed Trips Table, applicazione (persistenza) del piano scelto."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    Card,
    ColumnDef,
    ColumnType,
    EmptyState,
    IconChipVariant,
    LoadingSpinner,
    RowAction,
    Table,
    Tooltip,
)
from gestionale_logistica.gui.components.icon_chip import VARIANT_COLORS
from gestionale_logistica.gui.pianificazione.components import (
    DateFilterField,
    DettaglioViaggioPropostoModal,
    PlanKpiCard,
)
from gestionale_logistica.gui.pianificazione.pianificazione_data import (
    conta_composizioni_disponibili,
    costruisci_dettaglio_viaggio_proposto,
    costruisci_righe_piano,
)
from gestionale_logistica.ottimizzazione.gestore_configurazione import GestoreConfigurazione
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import MotoreOttimizzazione, PianoGiornaliero

TITLE_COLOR = "#2E2E2E"
HINT_COLOR = "#9AA1AA"
AMBER = "#B45309"
NAVY = "#163A6B"
AZZURRO = VARIANT_COLORS[IconChipVariant.LIGHT_BLUE][0]

# Colonne fisse della Proposed Trips Table, condivise da tutte le istanze: la sola colonna
# "dettaglio" ha una callback per-istanza (apre il modale con lo stato della tab), quindi la lista
# completa è assemblata da AutomaticaTab._table_columns() invece di essere un costante di modulo.
_BASE_TABLE_COLUMNS = [
    ColumnDef(key="squadra", label="Squadra", column_type=ColumnType.LINK, width=100),
    ColumnDef(key="numero_ordini", label="N. ordini", stretch=2),
    ColumnDef(key="partenza", label="Partenza", sortable=True, stretch=1),
    ColumnDef(key="arrivo", label="Arrivo", sortable=True, stretch=1),
    ColumnDef(key="stato", label="Stato", column_type=ColumnType.STATUS_BADGE, width=140),
    ColumnDef(key="capacita", label="Capacità", column_type=ColumnType.CAPACITY_BAR, width=90),
]


def _card_title(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(15)
    label.setFont(font)
    label.setStyleSheet(f"color: {TITLE_COLOR}; background: transparent;")
    return label


def _hint_label() -> QLabel:
    label = QLabel()
    font = QFont("Inter")
    font.setWeight(QFont.Weight(500))
    font.setPixelSize(12)
    label.setFont(font)
    label.setStyleSheet(f"color: {HINT_COLOR}; background: transparent;")
    return label


class AutomaticaTab(QWidget):
    # Il risultato di calcola_piano_async arriva su un thread in background (RNF3): emesso come
    # Signal (thread-safe in Qt anche da un thread non-Qt) invece di toccare i widget da lì.
    _pianoCalcolato = Signal(object, object)  # (Future[PianoGiornaliero], ora_partenza)
    pianoApplicato = Signal(int)  # numero di viaggi appena persistiti

    def __init__(self, session_factory: sessionmaker = SessionLocal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._motore = MotoreOttimizzazione(session_factory)
        self._gestore_config = GestoreConfigurazione(session_factory)
        self._piano: PianoGiornaliero | None = None
        self._ora_partenza: datetime | None = None
        self._durata_viaggio: timedelta | None = None
        self._numero_viaggi_proposti = 0

        self._pianoCalcolato.connect(self._on_piano_calcolato)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(28)

        outer.addWidget(self._build_config_card())
        outer.addLayout(self._build_summary_row())

        self._results_container = QVBoxLayout()
        self._results_container.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._results_container, 1)
        self._show_empty_state()

        outer.addLayout(self._build_footer_actions())

        self._refresh_hint()

    # -- Config Card ---------------------------------------------------------------------

    def _build_config_card(self) -> Card:
        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(_card_title("Configura pianificazione automatica"))
        title_row.addWidget(
            Tooltip(
                "Assegna automaticamente tutti gli ordini in attesa alle composizioni squadra "
                "disponibili nella data selezionata, rispettando capacità e vincoli di durata del tour."
            )
        )
        title_row.addStretch(1)
        card.content_layout.addLayout(title_row)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(12)

        self._date_field = DateFilterField()
        self._date_field.valueChanged.connect(lambda _: self._refresh_hint())
        filter_row.addWidget(self._date_field)

        self._calcola_button = Button(ButtonVariant.PRIMARY, "Calcola piano")
        self._calcola_button.clicked.connect(self._calcola_piano)
        filter_row.addWidget(self._calcola_button)

        filter_row.addStretch(1)

        self._hint = _hint_label()
        filter_row.addWidget(self._hint)

        card.content_layout.addLayout(filter_row)
        return card

    def _refresh_hint(self) -> None:
        giorno = self._date_field.value().toPython()
        numero = conta_composizioni_disponibili(giorno, self._session_factory)
        composizioni_label = "composizione attiva" if numero == 1 else "composizioni attive"
        self._hint.setText(f"{numero} {composizioni_label} disponibili per il {giorno.strftime('%d/%m/%Y')}")

    # -- Summary Row -----------------------------------------------------------------------

    def _build_summary_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(28)

        self._kpi_viaggi = PlanKpiCard("0", "Viaggi proposti", "package", NAVY, AZZURRO)
        self._kpi_ordini_assegnati = PlanKpiCard("0", "Ordini assegnati", "package-check", NAVY, AZZURRO)
        self._kpi_ordini_non_assegnati = PlanKpiCard("0", "Ordini non assegnati", "users", AMBER, AMBER)

        row.addWidget(self._kpi_viaggi, 1)
        row.addWidget(self._kpi_ordini_assegnati, 1)
        row.addWidget(self._kpi_ordini_non_assegnati, 1)
        return row

    # -- Proposed Trips Table / empty state -------------------------------------------------

    def _clear_results(self) -> None:
        while self._results_container.count():
            item = self._results_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # hide() subito: takeAt() scollega il widget dal layout ma non lo nasconde, e
                # deleteLater() e' differita al prossimo giro di event loop - senza hide() resta
                # visibile alla sua ultima geometria per un frame.
                widget.hide()
                widget.deleteLater()

    def _show_empty_state(self) -> None:
        self._clear_results()
        self._results_container.addWidget(
            EmptyState(
                "Nessun piano calcolato",
                "Scegli una data e premi «Calcola piano» per generare i viaggi proposti",
                "calendar-clock",
            )
        )

    def _show_loading_state(self) -> None:
        """Non nel mockup Sketch (nessun artboard modella uno stato di caricamento): stessa
        struttura centrata di EmptyState (icona/indicatore + testo), con LoadingSpinner al posto
        dell'icona statica — coerenza di stile richiesta dalla regola GUI #7 in assenza di mockup."""
        self._clear_results()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addStretch(1)
        layout.addWidget(LoadingSpinner(32), alignment=Qt.AlignmentFlag.AlignHCenter)
        label = QLabel("Calcolo del piano in corso…")
        label.setStyleSheet("color: #8A93A0; background: transparent;")
        font = QFont("Inter")
        font.setWeight(QFont.Weight(600))
        font.setPixelSize(14)
        label.setFont(font)
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self._results_container.addWidget(container)

    def _table_columns(self) -> list[ColumnDef]:
        return [
            *_BASE_TABLE_COLUMNS,
            ColumnDef(
                key="dettaglio",
                label="",
                column_type=ColumnType.ACTIONS,
                width=40,
                actions=[RowAction("chevron-right", self._apri_dettaglio_viaggio)],
            ),
        ]

    def _show_table(self, righe) -> None:
        self._clear_results()
        table = Table(self._table_columns(), show_footer=False)
        table.set_rows(
            [
                {
                    "squadra": riga.squadra_label,
                    "numero_ordini": "1 ordine" if riga.numero_ordini == 1 else f"{riga.numero_ordini} ordini",
                    "partenza": riga.partenza_label,
                    "arrivo": riga.arrivo_label,
                    "stato": "Proposto",
                    "capacita": riga.capacita_percentuale,
                    # Extra rispetto alle colonne dichiarate: la Table lo ignora nel render, ma
                    # RowAction lo riceve nel dict `row` — serve ad _apri_dettaglio_viaggio.
                    "composizione_id": riga.composizione_id,
                }
                for riga in righe
            ]
        )
        self._results_container.addWidget(table)

    def _apri_dettaglio_viaggio(self, row: dict) -> None:
        if self._piano is None or self._ora_partenza is None or self._durata_viaggio is None:
            return
        dettaglio = costruisci_dettaglio_viaggio_proposto(
            self._piano,
            row["composizione_id"],
            self._ora_partenza,
            self._durata_viaggio,
            self._session_factory,
        )
        if dettaglio is None:
            return
        self._dettaglio_modal = DettaglioViaggioPropostoModal(dettaglio, self)
        self._dettaglio_modal.show_over(self)

    # -- Footer Actions ----------------------------------------------------------------------

    def _build_footer_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch(1)

        self._annulla_button = Button(ButtonVariant.SECONDARY, "Annulla")
        self._annulla_button.clicked.connect(self._annulla)
        self._annulla_button.setEnabled(False)
        row.addWidget(self._annulla_button)

        self._applica_button = Button(ButtonVariant.PRIMARY, "Applica piano")
        self._applica_button.clicked.connect(self._applica_piano)
        self._applica_button.setEnabled(False)
        row.addWidget(self._applica_button)
        return row

    # -- Azioni --------------------------------------------------------------------------------

    def _calcola_piano(self) -> None:
        configurazione = self._gestore_config.leggi()
        giorno = self._date_field.value().toPython()
        ora_partenza = datetime.combine(giorno, configurazione.ora_partenza_default)
        self._durata_viaggio = timedelta(hours=configurazione.ore_lavoro)

        self._calcola_button.setEnabled(False)
        self._calcola_button.setText("Calcolo in corso…")
        self._annulla_button.setEnabled(False)
        self._applica_button.setEnabled(False)
        self._show_loading_state()

        future = self._motore.calcola_piano_async(
            ora_partenza,
            durata_viaggio=self._durata_viaggio,
            tempi_installazione_minuti=configurazione.tempi_installazione_minuti,
        )
        future.add_done_callback(lambda f: self._pianoCalcolato.emit(f, ora_partenza))

    def _on_piano_calcolato(self, future, ora_partenza: datetime) -> None:
        self._calcola_button.setEnabled(True)
        self._calcola_button.setText("Calcola piano")

        piano: PianoGiornaliero = future.result()
        self._piano = piano
        self._ora_partenza = ora_partenza

        righe = costruisci_righe_piano(
            piano, ora_partenza, self._durata_viaggio, self._session_factory
        )
        ordini_assegnati = sum(riga.numero_ordini for riga in righe)
        self._numero_viaggi_proposti = len(righe)

        self._kpi_viaggi.set_value(str(len(righe)))
        self._kpi_ordini_assegnati.set_value(str(ordini_assegnati))
        self._kpi_ordini_non_assegnati.set_value(str(len(piano.ordini_non_assegnati)))

        if righe:
            self._show_table(righe)
        else:
            self._show_empty_state()

        ha_piano = bool(piano.assegnazioni)
        self._annulla_button.setEnabled(ha_piano)
        self._applica_button.setEnabled(ha_piano)

    def _annulla(self) -> None:
        self._piano = None
        self._ora_partenza = None
        self._durata_viaggio = None
        self._show_empty_state()
        self._annulla_button.setEnabled(False)
        self._applica_button.setEnabled(False)
        self._kpi_viaggi.set_value("0")
        self._kpi_ordini_assegnati.set_value("0")
        self._kpi_ordini_non_assegnati.set_value("0")

    def _applica_piano(self) -> None:
        if self._piano is None or self._ora_partenza is None or self._durata_viaggio is None:
            return
        numero_viaggi = self._numero_viaggi_proposti
        self._motore.applica_piano(self._piano, self._ora_partenza, self._durata_viaggio)
        self._annulla()
        self._refresh_hint()
        self.pianoApplicato.emit(numero_viaggi)
