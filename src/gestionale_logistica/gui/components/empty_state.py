"""Stato vuoto: icona + titolo (+ sottotitolo) centrati (fonte: mockup Sketch).

Placeholder mostrato al posto di una lista/tabella quando non ci sono dati da visualizzare.
Contenuto centrato orizzontalmente e verticalmente nell'area disponibile.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"

ICON_COLOR = "#B7BEC7"
ICON_SIZE = 40

TITLE_COLOR = "#8A93A0"
TITLE_SIZE = 14
TITLE_WEIGHT = 600

SUBTITLE_COLOR = "#B7BEC7"
SUBTITLE_SIZE = 12
SUBTITLE_WEIGHT = 500

ICON_TITLE_GAP = 16
TITLE_SUBTITLE_GAP = 8


def build_centered_label(text: str, color: str, size: int, weight: int, parent: QWidget) -> QLabel:
    """Label centrata usata sia da `EmptyState` sia da `LoadingState` (stessa struttura, spinner
    al posto dell'icona statica) - fattorizzata qui per non duplicare i token di stile."""
    label = QLabel(text, parent)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(weight))
    font.setPixelSize(size)
    label.setFont(font)
    label.setStyleSheet(f"color: {color};")
    return label


class EmptyState(QWidget):
    """Icona 40×40 + titolo (+ sottotitolo opzionale), centrati H e V."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        icon_name: str = "inbox",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        icon_label = QLabel(self)
        icon = load_lucide_icon(icon_name, ICON_COLOR, ICON_SIZE)
        icon_label.setPixmap(icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)))
        icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(ICON_TITLE_GAP)
        layout.addWidget(
            build_centered_label(title, TITLE_COLOR, TITLE_SIZE, TITLE_WEIGHT, self),
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        if subtitle:
            layout.addSpacing(TITLE_SUBTITLE_GAP)
            layout.addWidget(
                build_centered_label(subtitle, SUBTITLE_COLOR, SUBTITLE_SIZE, SUBTITLE_WEIGHT, self),
                alignment=Qt.AlignmentFlag.AlignHCenter,
            )

        layout.addStretch(1)
