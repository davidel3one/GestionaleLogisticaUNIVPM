"""ActivityRow: riga del pannello "Attività recente" della Dashboard (fonte: mockup Sketch,
artboard Dashboard, "Activity Row")."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gestionale_logistica.gui.components.icon_chip import IconChip, IconChipVariant

_TEXT_COLOR = "#2E2E2E"
_TIMESTAMP_COLOR = "#8A93A0"
_ROW_HEIGHT = 52


def _row_font(pixel_size: int) -> QFont:
    font = QFont("Inter")
    font.setWeight(QFont.Weight(500))
    font.setPixelSize(pixel_size)
    return font


class ActivityRow(QWidget):
    """Riga: icona colorata + testo evento (troncato con ellissi se non ci sta) + timestamp
    relativo a destra. Il troncamento con ellissi non è verificabile nel mockup statico (mostra
    un solo esempio già lungo): è il comportamento standard atteso per una riga a larghezza fissa."""

    def __init__(
        self,
        icon_name: str,
        variant: IconChipVariant,
        text: str,
        timestamp: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(_ROW_HEIGHT)
        self._full_text = text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 10, 0, 10)
        layout.setSpacing(12)

        layout.addWidget(IconChip(icon_name, variant, size=16))

        self._text_label = QLabel(text, self)
        self._text_label.setFont(_row_font(13))
        self._text_label.setStyleSheet(f"color: {_TEXT_COLOR}; background: transparent;")
        layout.addWidget(self._text_label, 1)

        timestamp_label = QLabel(timestamp, self)
        timestamp_label.setFont(_row_font(12))
        timestamp_label.setStyleSheet(f"color: {_TIMESTAMP_COLOR}; background: transparent;")
        timestamp_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(timestamp_label)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        metrics = QFontMetrics(self._text_label.font())
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self._text_label.width()
        )
        self._text_label.setText(elided)
