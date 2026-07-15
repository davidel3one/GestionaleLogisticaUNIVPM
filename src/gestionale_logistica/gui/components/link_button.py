"""Componente LinkButton: testo cliccabile in stile link (fonte: mockup Sketch, artboard
"Conferma OTP" — "Non hai ricevuto il codice? Invia di nuovo"). Valori misurati: Inter 12px/
Medium(500), colore #2563C9, nessuna icona.

Stato hover non definito nel mockup (disegnato solo a riposo): derivato scurendo il colore del
testo, stesso principio gia' usato in Button._darken."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget

from gestionale_logistica.gui.components.button import _darken

FONT_FAMILY = "Inter"
LINK_COLOR = "#2563C9"
LINK_HOVER_COLOR = _darken(LINK_COLOR, 0.85)


class LinkButton(QPushButton):
    """Bottone testuale senza sfondo/bordo, colore accento blu. Usa il segnale `clicked'
    gia' fornito da QPushButton, nessun segnale custom necessario."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(12)
        self.setFont(font)

        self._apply_style(LINK_COLOR)

    def _apply_style(self, color: str) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background-color: transparent; border: none; padding: 0px;"
            f" color: {color}; }}"
        )

    def enterEvent(self, event) -> None:
        self._apply_style(LINK_HOVER_COLOR)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_style(LINK_COLOR)
        super().leaveEvent(event)
