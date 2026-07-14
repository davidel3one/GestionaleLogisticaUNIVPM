"""Loader per le icone Lucide vendorizzate in `gui/assets/icons/` (fonte: mockup Sketch)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class _LucideIconEngine(QIconEngine):
    """Motore icona che ridisegna l'SVG on-demand invece di cachare un raster fisso.

    Qt chiama `paint()`/`pixmap()`/`scaledPixmap()` alla risoluzione e al
    `devicePixelRatio` effettivamente richiesti nel momento del rendering: così
    l'icona resta nitida sia su display standard sia su HiDPI/Retina, e a qualunque
    dimensione venga richiesta (non solo quella di default passata a `load_lucide_icon`).
    """

    def __init__(self, svg_bytes: QByteArray) -> None:
        super().__init__()
        self._svg_bytes = QByteArray(svg_bytes)  # copia difensiva per clone()
        self._renderer = QSvgRenderer(self._svg_bytes)

    def paint(
        self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State
    ) -> None:
        self._renderer.render(painter, QRectF(rect))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float
    ) -> QPixmap:
        device_size = size * scale
        pixmap = QPixmap(device_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self._renderer.render(painter, QRectF(0, 0, device_size.width(), device_size.height()))
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def clone(self) -> QIconEngine:
        return _LucideIconEngine(self._svg_bytes)


def load_lucide_icon(name: str, color: str, size: int = 24) -> QIcon:
    """Carica l'icona Lucide `name` da `gui/assets/icons/`, ricolorata, come icona vettoriale.

    Le icone Lucide usano `stroke="currentColor"` per essere ricolorabili: sostituiamo
    quel placeholder con `color` (es. "#2E2E2E") prima di renderizzare l'SVG.

    L'icona resta vettoriale fino al momento del rendering effettivo (vedi
    `_LucideIconEngine`): `size` è solo la dimensione di default suggerita, non un
    raster pre-calcolato una volta sola.
    """
    svg_path = _ICONS_DIR / f"{name}.svg"
    if not svg_path.is_file():
        raise ValueError(f"Icona Lucide '{name}' non trovata in {_ICONS_DIR}")

    svg_data = svg_path.read_text(encoding="utf-8").replace("currentColor", color)

    return QIcon(_LucideIconEngine(QByteArray(svg_data.encode("utf-8"))))
