"""Componente TabBar riusabile, selettore di tab a underline (fonte: mockup Sketch, gui-design.sketch)."""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPaintEvent, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

FONT_FAMILY = "Inter"

TEXT_COLOR_ACTIVE = "#163A6B"
TEXT_COLOR_INACTIVE = "#2E2E2E"
TEXT_COLOR_HOVER = "#22344D"  # via di mezzo tra inattivo e attivo: stato hover non nel mockup
TEXT_COLOR_DISABLED = "#B0B6BF"  # non nel mockup: nessun frame mostra una tab disabilitata
UNDERLINE_COLOR = "#2563C9"
BASELINE_COLOR = "#EAEAEA"

BAR_HEIGHT = 45
TOP_MARGIN = 8
TAB_GAP = 32
UNDERLINE_GAP = 15
UNDERLINE_HEIGHT = 3
BASELINE_HEIGHT = 1

UNDERLINE_ANIMATION_MS = 200
UNDERLINE_ANIMATION_EASING = QEasingCurve.Type.OutCubic


class _TabLabel(QLabel):
    """Etichetta cliccabile di una singola tab."""

    clicked = Signal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(14)
        self.setFont(font)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active = False
        self._hovered = False
        self._disabled = False
        self._update_color()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._update_color()

    def set_disabled_tab(self, disabled: bool) -> None:
        """Non e' `QWidget.setDisabled` - qui la tab resta visibile/leggibile (solo colore
        attenuato) e semplicemente ignora i click, invece di sparire dal flusso del layout."""
        self._disabled = disabled
        self.setCursor(Qt.CursorShape.ArrowCursor if disabled else Qt.CursorShape.PointingHandCursor)
        self._update_color()

    def enterEvent(self, event: QEvent) -> None:
        self._hovered = True
        self._update_color()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        self._update_color()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._disabled:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _update_color(self) -> None:
        if self._disabled:
            color = TEXT_COLOR_DISABLED
        elif self._active:
            color = TEXT_COLOR_ACTIVE
        elif self._hovered:
            color = TEXT_COLOR_HOVER
        else:
            color = TEXT_COLOR_INACTIVE
        self.setStyleSheet(f"color: {color};")


class TabBar(QWidget):
    """Barra di tab orizzontale con indicatore ad underline sulla tab attiva.

    Componente puramente selettore: non gestisce il contenuto delle pagine.
    Chi lo usa si iscrive a `currentChanged` per aggiornare il contenuto associato.
    """

    currentChanged = Signal(int)

    def __init__(
        self,
        labels: list[str],
        disabled: set[int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not labels:
            raise ValueError("TabBar richiede almeno un'etichetta.")

        self.setFixedHeight(BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, TOP_MARGIN, 0, 0)
        layout.setSpacing(TAB_GAP)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        disabled = disabled or set()
        self._current_index = 0
        self._tabs: list[_TabLabel] = []
        for index, text in enumerate(labels):
            tab = _TabLabel(text, self)
            if index in disabled:
                tab.set_disabled_tab(True)
            tab.clicked.connect(lambda index=index: self.set_current_index(index))
            layout.addWidget(tab)
            self._tabs.append(tab)

        self._tabs[0].set_active(True)

        # Stato animabile dell'underline: sincronizzato senza animazione al primo
        # paintEvent (geometria dei tab non ancora valida prima di allora), poi
        # spostato con QPropertyAnimation a ogni cambio di tab attiva.
        self._underline_x = 0.0
        self._underline_width = 0.0
        self._underline_synced = False

        self._underline_x_anim = QPropertyAnimation(self, b"underlineX", self)
        self._underline_x_anim.setDuration(UNDERLINE_ANIMATION_MS)
        self._underline_x_anim.setEasingCurve(UNDERLINE_ANIMATION_EASING)

        self._underline_width_anim = QPropertyAnimation(self, b"underlineWidth", self)
        self._underline_width_anim.setDuration(UNDERLINE_ANIMATION_MS)
        self._underline_width_anim.setEasingCurve(UNDERLINE_ANIMATION_EASING)

    @property
    def current_index(self) -> int:
        return self._current_index

    def _get_underline_x(self) -> float:
        return self._underline_x

    def _set_underline_x(self, value: float) -> None:
        self._underline_x = value
        self.update()

    underlineX = Property(float, _get_underline_x, _set_underline_x)

    def _get_underline_width(self) -> float:
        return self._underline_width

    def _set_underline_width(self, value: float) -> None:
        self._underline_width = value
        self.update()

    underlineWidth = Property(float, _get_underline_width, _set_underline_width)

    def set_current_index(self, index: int) -> None:
        if not 0 <= index < len(self._tabs):
            raise ValueError(f"Indice tab non valido: {index}")
        if index == self._current_index:
            return
        self._tabs[self._current_index].set_active(False)
        self._current_index = index
        self._tabs[index].set_active(True)
        self._animate_underline_to(self._tabs[index])
        self.currentChanged.emit(index)

    def _animate_underline_to(self, tab: _TabLabel) -> None:
        self._underline_x_anim.stop()
        self._underline_width_anim.stop()
        self._underline_x_anim.setStartValue(self._underline_x)
        self._underline_x_anim.setEndValue(float(tab.x()))
        self._underline_width_anim.setStartValue(self._underline_width)
        self._underline_width_anim.setEndValue(float(tab.width()))
        self._underline_x_anim.start()
        self._underline_width_anim.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._underline_synced:
            # Primo render: geometria dei tab ora finalmente valida, posiziona
            # l'underline senza animarla (nessuno scorrimento da 0 all'avvio).
            active_tab = self._tabs[self._current_index]
            self._underline_x = float(active_tab.x())
            self._underline_width = float(active_tab.width())
            self._underline_synced = True

        painter = QPainter(self)

        active_tab = self._tabs[self._current_index]
        underline_y = active_tab.y() + active_tab.height() + UNDERLINE_GAP
        underline_rect = QRect(
            round(self._underline_x), underline_y, round(self._underline_width), UNDERLINE_HEIGHT
        )
        painter.fillRect(underline_rect, QColor(UNDERLINE_COLOR))

        baseline_rect = QRect(0, self.height() - BASELINE_HEIGHT, self.width(), BASELINE_HEIGHT)
        painter.fillRect(baseline_rect, QColor(BASELINE_COLOR))
