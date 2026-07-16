"""Spinner di caricamento: icona Lucide "loader-circle" in rotazione continua.

Non presente nel mockup Sketch (che non modella stati di caricamento asincrono): colore e
dimensione di default riprendono i token gia' usati altrove per icone/accenti primari
(#2563C9, stesso Blu del bottone PRIMARY) invece di introdurne di nuovi, per restare
coerenti con lo stile esistente (regola 7 delle convenzioni GUI del progetto)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"

DEFAULT_COLOR = "#2563C9"
DEFAULT_SIZE = 20
_TICK_INTERVAL_MS = 16
_DEGREES_PER_TICK = 6


class Spinner(QWidget):
    """Icona quadrata che ruota di continuo mentre e' visibile (parte/si ferma da sola con
    show/hide, cosi' non consuma il timer quando non e' a schermo)."""

    def __init__(
        self, size: int = DEFAULT_SIZE, color: str = DEFAULT_COLOR, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

        svg_path = _ICONS_DIR / "loader-circle.svg"
        svg_data = svg_path.read_text(encoding="utf-8").replace("currentColor", color)
        self._renderer = QSvgRenderer(svg_data.encode("utf-8"))

        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, event) -> None:  # noqa: ARG002
        self._timer.start(_TICK_INTERVAL_MS)

    def hideEvent(self, event) -> None:  # noqa: ARG002
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + _DEGREES_PER_TICK) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.width() / 2, self.height() / 2
        painter.translate(*center)
        painter.rotate(self._angle)
        painter.translate(-center[0], -center[1])
        self._renderer.render(painter, QRectF(0, 0, self.width(), self.height()))
        painter.end()
