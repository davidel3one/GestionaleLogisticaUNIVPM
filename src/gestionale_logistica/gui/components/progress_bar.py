"""ProgressBar: barra di riempimento track+fill, disegnata con `QPainter` (fonte: mockup Sketch,
verificata su più istanze — "CAPACITÀ" della Proposed Trips Table di Pianificazione — Automatica,
e le barre Peso/Volume della Composizione Card di Pianificazione — Manuale/Assistita: stessi
colori/dimensioni in entrambi i contesti).

Nato dentro `table.py` (colonna `CAPACITY_BAR`) e promosso qui quando è servito un secondo
contesto identico, stesso percorso già seguito per `KpiCard`→condivisione quando serve."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

TRACK_COLOR = "#EAEAEA"
FILL_COLOR = "#3D9BE9"
DEFAULT_WIDTH = 70
DEFAULT_HEIGHT = 6


class ProgressBar(QWidget):
    def __init__(
        self,
        percent: float,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fill_color: str = FILL_COLOR,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._percent = max(0.0, min(100.0, percent))
        self._fill_color = fill_color
        self.setFixedSize(width, height)

    def set_percent(self, percent: float, fill_color: str | None = None) -> None:
        self._percent = max(0.0, min(100.0, percent))
        if fill_color is not None:
            self._fill_color = fill_color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self.height() / 2
        painter.setBrush(QColor(TRACK_COLOR))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), radius, radius)
        fill_width = self.width() * self._percent / 100
        if fill_width > 0:
            painter.setBrush(QColor(self._fill_color))
            painter.drawRoundedRect(QRectF(0, 0, fill_width, self.height()), radius, radius)
        painter.end()
