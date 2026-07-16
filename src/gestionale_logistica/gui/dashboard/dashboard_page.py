"""Pagina Dashboard: KPI aggregati, pianificazione prossimi giorni, attività recente
(fonte: mockup Sketch, artboard "Dashboard")."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components import (
    MINIMAL_SCROLLBAR_QSS,
    Button,
    ButtonVariant,
    Card,
    EmptyState,
    IconChipVariant,
    ImportCsvModal,
    PageHeader,
    load_lucide_icon,
)
from gestionale_logistica.gui.components.toast import ToastManager
from gestionale_logistica.gui.dashboard.components import ActivityRow, KpiCard, PlanningDayCard
from gestionale_logistica.gui.dashboard.dashboard_data import (
    carica_attivita_recente,
    carica_kpi_dashboard,
    carica_pianificazione_prossimi_giorni,
)
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica

CONTENT_PADDING = 32
CONTENT_GAP = 24
DIVIDER_COLOR = "#EDEFF3"
HEADING_COLOR = "#2E2E2E"

# Altezza minima dell'area righe di "Attività recente": 5 righe visibili (52px + divider) come
# nel mockup (Activity Panel alto 373px = intestazione + 5 righe). Sotto questa soglia scrolla;
# sopra, si allarga per riempire lo spazio verticale disponibile (la pagina non usa più uno
# stretch finale "morto" che lascerebbe grigio vuoto in fondo a schermo intero).
ACTIVITY_LIST_MIN_HEIGHT = 296


def _section_heading(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(16)
    label.setFont(font)
    label.setStyleSheet(f"color: {HEADING_COLOR}; background: transparent;")
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {DIVIDER_COLOR}; border: none;")
    return line


class DashboardPage(QWidget):
    """Dati KPI/calendario/attività letti dal DB reale ad ogni `refresh()` (nessun requisito
    funzionale dedicato: RF7/RF9/RF13/RF15/RF16/data creazione Squadra sono le fonti reali
    piu' vicine, vedi `dashboard_data.py`)."""

    importaCsvRequested = Signal()
    nuovaPianificazioneRequested = Signal()

    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory

        outer = QVBoxLayout(self)
        outer.setContentsMargins(CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING)
        outer.setSpacing(CONTENT_GAP)

        importa_button = Button(
            ButtonVariant.SECONDARY, "Importa CSV", load_lucide_icon("upload", "#2E2E2E", 12)
        )
        nuova_button = Button(
            ButtonVariant.PRIMARY,
            "Nuova pianificazione",
            load_lucide_icon("calendar-plus", "#FFFFFF", 12),
        )
        importa_button.clicked.connect(self.importaCsvRequested)
        importa_button.clicked.connect(self._apri_import_csv)
        nuova_button.clicked.connect(self.nuovaPianificazioneRequested)
        outer.addWidget(PageHeader("Dashboard", [importa_button, nuova_button]))

        self._kpi_grid = QGridLayout()
        self._kpi_grid.setSpacing(28)
        for colonna in range(3):
            self._kpi_grid.setColumnStretch(colonna, 1)
        outer.addLayout(self._kpi_grid)

        self._calendar_card = Card(padding_horizontal=24, padding_vertical=24, spacing=16)
        self._calendar_card.add_widget(_section_heading("Pianificazione — prossimi giorni"))
        self._days_row = QHBoxLayout()
        self._days_row.setSpacing(10)
        self._calendar_card.content_layout.addLayout(self._days_row)
        outer.addWidget(self._calendar_card)

        self._activity_card = Card(padding_horizontal=24, padding_vertical=24, spacing=16)
        self._activity_card.add_widget(_section_heading("Attività recente"))

        self._activity_scroll = QScrollArea()
        self._activity_scroll.setWidgetResizable(True)
        self._activity_scroll.setMinimumHeight(ACTIVITY_LIST_MIN_HEIGHT)
        self._activity_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._activity_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._activity_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._activity_scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }} {MINIMAL_SCROLLBAR_QSS}"
        )

        self._activity_list_widget = QWidget()
        self._activity_list_widget.setStyleSheet("background: transparent;")
        self._activity_list_layout = QVBoxLayout(self._activity_list_widget)
        self._activity_list_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_list_layout.setSpacing(4)
        self._activity_scroll.setWidget(self._activity_list_widget)

        self._activity_card.add_widget(self._activity_scroll)
        outer.addWidget(self._activity_card, 1)

        self._toasts = ToastManager(self)

        self.refresh()

    def refresh(self) -> None:
        self._popola_kpi()
        self._popola_calendario()
        self._popola_attivita()

    def _apri_import_csv(self) -> None:
        # Riferimento tenuto su self: ImportCsvModal e' un QObject senza parent Qt esplicito,
        # una variabile locale verrebbe garbage-collected da Python prima che l'utente finisca
        # il flusso a 2 passi.
        self._import_modal = ImportCsvModal(self, GestoreLogistica(self._session_factory))
        self._import_modal.importCompleted.connect(self._on_import_completato)
        self._import_modal.show()

    def _on_import_completato(self, numero_ordini: int) -> None:
        self.refresh()
        etichetta = "ordine importato" if numero_ordini == 1 else "ordini importati"
        self._toasts.show_success(f"{numero_ordini} {etichetta} correttamente")

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _popola_kpi(self) -> None:
        self._clear_layout(self._kpi_grid)
        kpi = carica_kpi_dashboard(self._session_factory)

        carte = [
            KpiCard(str(kpi.ordini_ricevuti), "Ordini ricevuti", "package", IconChipVariant.LIGHT_BLUE),
            KpiCard(
                str(kpi.ordini_in_consegna),
                "Ordini in consegna",
                "package-search",
                IconChipVariant.LIGHT_BLUE,
            ),
            KpiCard(
                f"{kpi.dipendenti_disponibili} / {kpi.dipendenti_totali}",
                "Dipendenti disponibili",
                "users",
                IconChipVariant.BLUE,
            ),
            KpiCard(
                f"{kpi.camion_disponibili} / {kpi.camion_totali}",
                "Camion disponibili",
                "truck",
                IconChipVariant.BLUE,
            ),
            KpiCard(
                str(kpi.ordini_consegnati_oggi),
                "Ordini consegnati",
                "circle-check-big",
                IconChipVariant.GREEN,
                trend=kpi.trend_consegnati,
            ),
            KpiCard(
                str(kpi.ordini_falliti_oggi),
                "Ordini falliti",
                "triangle-alert",
                IconChipVariant.RED,
                trend=kpi.trend_falliti,
            ),
        ]
        for indice, carta in enumerate(carte):
            self._kpi_grid.addWidget(carta, indice // 3, indice % 3)

    def _popola_calendario(self) -> None:
        self._clear_layout(self._days_row)
        for giorno in carica_pianificazione_prossimi_giorni(self._session_factory):
            etichetta_viaggi = "1 viaggio" if giorno.numero_viaggi == 1 else f"{giorno.numero_viaggi} viaggi"
            self._days_row.addWidget(PlanningDayCard(giorno.label, etichetta_viaggi))

    def _popola_attivita(self) -> None:
        self._clear_layout(self._activity_list_layout)

        voci = carica_attivita_recente(self._session_factory)
        if not voci:
            self._activity_list_layout.addWidget(
                EmptyState("Nessuna attività", "Le attività recenti appariranno qui", "inbox")
            )
            return

        for indice, voce in enumerate(voci):
            if indice > 0:
                self._activity_list_layout.addWidget(_divider())
            self._activity_list_layout.addWidget(
                ActivityRow(voce.icon_name, voce.variant, voce.testo, voce.tempo_relativo)
            )
        self._activity_list_layout.addStretch(1)
