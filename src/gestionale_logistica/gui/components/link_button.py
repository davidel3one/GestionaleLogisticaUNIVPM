"""Componente LinkButton: testo + icona in stile link, usato per "Ripristina filtri" nelle
Filter Card di ogni pagina lista (fonte: mockup Sketch, presente identico in piu' artboard con
stesso colore/font: Ordini, Ordini — Esiti, Viaggi, Dipendenti, Camion, Squadre).

Stato hover non definito nel mockup (disegnato solo a riposo): derivato scurendo il colore del
testo, stesso principio gia' usato da Button._darken per lo stesso motivo.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from gestionale_logistica.gui.components.button import _darken
from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"
LINK_COLOR = "#2563C9"
LINK_HOVER_COLOR_FACTOR = 0.85
ICON_SIZE = 13
GAP = 6


class LinkButton(QPushButton):
    """Bottone testuale senza sfondo/bordo: icona + testo, colore accento blu. Usa il segnale
    `clicked` gia' fornito da QPushButton, nessun segnale custom necessario."""

    def __init__(self, text: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        icon_label = QLabel(self)
        icon_label.setPixmap(load_lucide_icon(icon_name, LINK_COLOR, ICON_SIZE).pixmap(ICON_SIZE, ICON_SIZE))
        icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)
        layout.addWidget(icon_label)

        self._text_label = QLabel(text, self)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(13)
        self._text_label.setFont(font)
        layout.addWidget(self._text_label)

        self.setStyleSheet("QPushButton { background-color: transparent; border: none; padding: 0px; }")
        self._set_text_color(LINK_COLOR)

    def _set_text_color(self, color: str) -> None:
        self._text_label.setStyleSheet(f"color: {color};")

    def enterEvent(self, event) -> None:
        self._set_text_color(_darken(LINK_COLOR, LINK_HOVER_COLOR_FACTOR))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_text_color(LINK_COLOR)
        super().leaveEvent(event)

    def sizeHint(self):
        return self.layout().sizeHint()
