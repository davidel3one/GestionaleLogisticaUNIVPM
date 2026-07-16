"""SuggestionSection: blocco "Suggerimento automatico" (RF12) della Composizione Card di
Pianificazione — Assistita, inserito via `CompositionCard.add_extra_section()`.

Il mockup Sketch modella questo blocco come righe di testo semplici, ma con solo 2 righe di
esempio: non copre lo scenario reale (fino a centinaia di ordini idonei), che con una QLabel per
riga spingeva i pulsanti "Annulla / Applica suggerimento" fuori dalla finestra. Deviazione dal
mockup concordata con l'utente (2026-07-16): `Table` con colonne + paginazione, stesso componente
già usato dalla Proposed Trips Table di Pianificazione — Automatica."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    ColumnDef,
    ColumnType,
    RowAction,
    Table,
    Tooltip,
)

TITLE_COLOR = "#2E2E2E"
HINT_COLOR = "#9AA1AA"

PAGE_SIZE = 20

# Stessi colori di CompositionCard._BADGE_COLORS (composition_card.py, misurati sul mockup):
# costante di stile duplicata per file, non condivisa (stesso pattern di DIVIDER_COLOR, vedi
# componenti-gui.md).
BADGE_COLORS = {
    "Standard": ("#EAEAEA", "#2E2E2E"),
    "Big": ("#FEF3C7", "#B45309"),
    "Certificazione Gas": ("#FEF3C7", "#B45309"),
}

TABLE_COLUMNS = [
    ColumnDef(key="ordine_id", label="Ordine", width=90),
    ColumnDef(key="cliente", label="Cliente", stretch=2),
    ColumnDef(key="peso", label="Peso", width=90),
    ColumnDef(key="volume", label="Volume", width=90),
    ColumnDef(
        key="categoria_label",
        label="Categoria",
        column_type=ColumnType.STATUS_BADGE,
        status_colors=BADGE_COLORS,
        width=140,
    ),
]

# width=40, stessa geometria della colonna "dettaglio" della Proposed Trips Table
# (automatica_tab.py) per coerenza fra le due Table di Pianificazione.
_ACTION_COLUMN_WIDTH = 40


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(15)
    label.setFont(font)
    label.setStyleSheet(f"color: {TITLE_COLOR}; background: transparent;")
    return label


@dataclass
class RigaOrdineSuggerito:
    ordine_id: str
    cliente: str
    peso: float
    volume: float
    categoria_label: str


class SuggestionSection(QWidget):
    suggerisciRequested = Signal()
    aggiungiOrdineRequested = Signal(str)  # ordine_id della riga suggerita da aggiungere al viaggio

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(_heading("Suggerimento automatico"))
        title_row.addWidget(
            Tooltip(
                "A differenza dell'automatica, propone ordini solo per QUESTO viaggio già avviato."
            )
        )
        title_row.addStretch(1)
        layout.addLayout(title_row)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self._suggerisci_button = Button(ButtonVariant.PRIMARY, "Suggerisci ordini")
        self._suggerisci_button.clicked.connect(self.suggerisciRequested)
        button_row.addWidget(self._suggerisci_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._righe: list[RigaOrdineSuggerito] = []
        self._current_page = 1

        colonne = [
            *TABLE_COLUMNS,
            ColumnDef(
                key="azioni",
                label="",
                column_type=ColumnType.ACTIONS,
                width=_ACTION_COLUMN_WIDTH,
                actions=[RowAction("circle-plus", self._on_aggiungi_clicked, tooltip="Aggiungi al viaggio")],
            ),
        ]
        self._table = Table(colonne)
        self._table.pageChanged.connect(self._on_page_changed)
        self._table.hide()
        layout.addWidget(self._table)

        self._summary_label = QLabel()
        summary_font = QFont("Inter")
        summary_font.setWeight(QFont.Weight(500))
        summary_font.setPixelSize(12)
        self._summary_label.setFont(summary_font)
        self._summary_label.setStyleSheet(f"color: {HINT_COLOR}; background: transparent;")
        self._summary_label.hide()
        layout.addWidget(self._summary_label)

    def set_suggerimento(
        self,
        righe: list[RigaOrdineSuggerito],
        peso_dopo: float,
        peso_massimo: float,
        volume_dopo: float,
        volume_massimo: float,
    ) -> None:
        self._righe = righe
        self._current_page = 1
        self._render_page()

        if righe:
            self._summary_label.setText(
                f"{len(righe)} {'ordine suggerito' if len(righe) == 1 else 'ordini suggeriti'} — "
                f"capacità dopo l'aggiunta: Peso {peso_dopo:g}/{peso_massimo:g} kg · "
                f"Volume {volume_dopo:g}/{volume_massimo:g} m³"
            )
            self._summary_label.show()
        else:
            self._summary_label.setText("Nessun ordine idoneo da suggerire per questo viaggio")
            self._summary_label.show()

    def clear(self) -> None:
        self._righe = []
        self._current_page = 1
        self._render_page()
        self._summary_label.hide()

    def set_loading(self, loading: bool) -> None:
        """RNF3: il calcolo (solve CBC) gira in background — disabilita il bottone e mostra un
        testo di stato mentre è in corso, per non lasciare l'utente senza feedback."""
        self._suggerisci_button.setEnabled(not loading)
        self._suggerisci_button.set_text("Calcolo in corso…" if loading else "Suggerisci ordini")

    def _on_aggiungi_clicked(self, row: dict) -> None:
        self.aggiungiOrdineRequested.emit(row["ordine_id"])

    def _on_page_changed(self, page: int) -> None:
        self._current_page = page
        self._render_page()

    def _render_page(self) -> None:
        self._table.setVisible(bool(self._righe))
        inizio = (self._current_page - 1) * PAGE_SIZE
        pagina = self._righe[inizio : inizio + PAGE_SIZE]
        self._table.set_rows(
            [
                {
                    "ordine_id": riga.ordine_id,
                    "cliente": riga.cliente,
                    "peso": f"{riga.peso:g} kg",
                    "volume": f"{riga.volume:g} m³",
                    "categoria_label": riga.categoria_label,
                }
                for riga in pagina
            ]
        )
        self._table.set_pagination(self._current_page, len(self._righe), PAGE_SIZE)
