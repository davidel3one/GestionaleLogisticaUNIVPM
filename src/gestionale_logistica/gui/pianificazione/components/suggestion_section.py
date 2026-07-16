"""SuggestionSection: blocco "Suggerimento automatico" (RF12) della Composizione Card di
Pianificazione — Assistita, inserito via `CompositionCard.add_extra_section()`."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gestionale_logistica.gui.components import Button, ButtonVariant

TITLE_COLOR = "#2E2E2E"
HINT_COLOR = "#9AA1AA"
SUGGESTED_COLOR = "#163A6B"


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(_heading("Suggerimento automatico"))

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self._suggerisci_button = Button(ButtonVariant.PRIMARY, "Suggerisci ordini")
        self._suggerisci_button.clicked.connect(self.suggerisciRequested)
        button_row.addWidget(self._suggerisci_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._righe_layout = QVBoxLayout()
        self._righe_layout.setContentsMargins(0, 0, 0, 0)
        self._righe_layout.setSpacing(8)
        layout.addLayout(self._righe_layout)

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
        self.clear()
        for riga in righe:
            label = QLabel(
                f"✓  {riga.ordine_id}  ·  {riga.cliente}  ·  {riga.peso:g} kg · "
                f"{riga.volume:g} m³  ·  {riga.categoria_label}"
            )
            font = QFont("Inter")
            font.setWeight(QFont.Weight(500))
            font.setPixelSize(12)
            label.setFont(font)
            label.setStyleSheet(f"color: {SUGGESTED_COLOR}; background: transparent;")
            self._righe_layout.addWidget(label)

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
        while self._righe_layout.count():
            item = self._righe_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._summary_label.hide()
