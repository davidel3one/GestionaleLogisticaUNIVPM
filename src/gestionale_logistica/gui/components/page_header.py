"""Intestazione di pagina: titolo a sinistra + slot azioni a destra (fonte: mockup Sketch).

Barra trasparente (nessun bordo/sfondo) posta in cima al contenuto di una pagina, sopra
lo sfondo `#EAEAEA` dell'AppShell. Le azioni sono widget arbitrari passati dal chiamante
(tipicamente un `Button`), così `PageHeader` non conosce le azioni specifiche di ogni pagina.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

FONT_FAMILY = "Inter"

TITLE_COLOR = "#2E2E2E"
TITLE_SIZE = 24
TITLE_WEIGHT = 600

ACTIONS_GAP = 10


class PageHeader(QWidget):
    """Titolo pagina a sinistra + azioni allineate a destra, su barra trasparente."""

    def __init__(
        self,
        title: str,
        actions: list[QWidget] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ACTIONS_GAP)

        self._title_label = QLabel(title, self)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(TITLE_WEIGHT))
        font.setPixelSize(TITLE_SIZE)
        self._title_label.setFont(font)
        self._title_label.setStyleSheet(f"color: {TITLE_COLOR};")
        layout.addWidget(self._title_label)

        layout.addStretch(1)

        for action in actions or []:
            layout.addWidget(action)

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)
