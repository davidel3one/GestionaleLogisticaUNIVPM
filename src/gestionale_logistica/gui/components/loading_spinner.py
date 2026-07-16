"""LoadingSpinner: cerchio indeterminato animato (QPainter + QTimer), per operazioni asincrone di
cui non è nota una percentuale di avanzamento (es. calcolo piano RF13, che gira in background fino
a RNF4=3min — vedi `automatica_tab.py`). Non modellato nel mockup Sketch: nessun artboard statico
cattura uno stato di caricamento, quindi i colori sono derivati dalla Palette invece che misurati
su un'istanza — stessa coppia track/accent già usata da `ProgressBar` (`#EAEAEA`/blu), qui col Blu
primario `#2563C9` (colore di `Button` PRIMARY) invece dell'Azzurro, per leggere come "azione
primaria in corso" coerentemente col bottone che l'ha avviata."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

TRACK_COLOR = "#EAEAEA"
ARC_COLOR = "#2563C9"
DEFAULT_SIZE = 24
LINE_WIDTH = 3
ARC_SPAN_DEGREES = 90
TICK_MS = 16
DEGREES_PER_TICK = 6


class LoadingSpinner(QWidget):
    def __init__(self, size: int = DEFAULT_SIZE, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, event) -> None:  # noqa: ARG002
        self._timer.start(TICK_MS)

    def hideEvent(self, event) -> None:  # noqa: ARG002
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle - DEGREES_PER_TICK) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(LINE_WIDTH / 2, LINE_WIDTH / 2, self.width() - LINE_WIDTH, self.height() - LINE_WIDTH)

        track_pen = QPen(QColor(TRACK_COLOR), LINE_WIDTH)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        arc_pen = QPen(QColor(ARC_COLOR), LINE_WIDTH)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(rect, self._angle * 16, ARC_SPAN_DEGREES * 16)
        painter.end()
