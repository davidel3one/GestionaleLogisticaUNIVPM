"""Campo di ricerca: icona `search` a sinistra dentro il campo + `QLineEdit` (fonte: mockup Sketch).

Sta in un file a parte (non in `form_field.py`) perché ha una struttura diversa dagli altri
field: **niente label sopra** e l'icona vive *dentro* il campo (un contenitore con la chrome +
icona + line edit senza bordo), mentre `TextField`/`Select`/... stilizzano direttamente il
widget nativo con la label sopra. La chrome (sfondo/bordo/radius/altezza/padding/testo) è però
identica a `TextField`: i token sono importati da `form_field.py`, non ridefiniti.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget

from gestionale_logistica.gui.components.form_field import (
    FIELD_BG,
    FIELD_BORDER,
    FIELD_HEIGHT,
    FIELD_PADDING_H,
    FIELD_RADIUS,
    FIELD_TEXT_COLOR,
    LABEL_COLOR,
    _field_font,
)
from gestionale_logistica.gui.components.icons import load_lucide_icon

SEARCH_ICON_COLOR = LABEL_COLOR  # #8A93A0, lo stesso grigio delle label dei field
SEARCH_ICON_SIZE = 16
SEARCH_ICON_GAP = 8


class SearchField(QWidget):
    """Campo di ricerca con icona a sinistra: stessa chrome di `TextField`, senza label."""

    searchChanged = Signal(str)

    def __init__(self, placeholder: str = "Cerca...", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._box = QFrame(self)
        self._box.setFixedHeight(FIELD_HEIGHT)
        self._box.setStyleSheet(
            f"""
            QFrame {{
                background-color: {FIELD_BG};
                border: 1px solid {FIELD_BORDER};
                border-radius: {FIELD_RADIUS}px;
            }}
            """
        )
        layout.addWidget(self._box)

        box_layout = QHBoxLayout(self._box)
        box_layout.setContentsMargins(FIELD_PADDING_H, 0, FIELD_PADDING_H, 0)
        box_layout.setSpacing(SEARCH_ICON_GAP)

        icon_label = QLabel(self._box)
        icon = load_lucide_icon("search", SEARCH_ICON_COLOR, SEARCH_ICON_SIZE)
        icon_label.setPixmap(icon.pixmap(QSize(SEARCH_ICON_SIZE, SEARCH_ICON_SIZE)))
        icon_label.setFixedSize(SEARCH_ICON_SIZE, SEARCH_ICON_SIZE)
        icon_label.setStyleSheet("border: none;")
        box_layout.addWidget(icon_label)

        self._input = QLineEdit(self._box)
        self._input.setPlaceholderText(placeholder)
        self._input.setFont(_field_font())
        # Stesso trattamento del placeholder di TextField: senza questo Qt lo schiarirebbe
        # automaticamente rispetto al testo digitato (ruolo QPalette::PlaceholderText).
        palette = self._input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(FIELD_TEXT_COLOR))
        self._input.setPalette(palette)
        self._input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: transparent;
                border: none;
                padding: 0px;
                color: {FIELD_TEXT_COLOR};
            }}
            """
        )
        box_layout.addWidget(self._input, 1)

        self._input.textChanged.connect(self.searchChanged)

    def value(self) -> str:
        return self._input.text()

    def set_value(self, value: str) -> None:
        self._input.setText(value)
