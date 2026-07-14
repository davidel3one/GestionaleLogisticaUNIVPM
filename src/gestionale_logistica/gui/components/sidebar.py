"""Componente Sidebar riusabile: navigazione laterale con logo, voci nav, utente e logout.

La sidebar espansa replica il mockup Sketch (`gui-design.sketch`); lo stato collassato a
rail (72px) e' una decisione esplicita dell'utente, non presente nel mockup — i dettagli e
gli scarti sono documentati in `.claude/knowledge/componenti-gui.md`, sezione "Sidebar".
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"

WIDTH_EXPANDED = 240
WIDTH_COLLAPSED = 72

BG_COLOR = "#FCFDFE"
DIVIDER_COLOR = "#E3EFFB"

LOGO_BADGE_BG = "#2563C9"
LOGO_BADGE_SIZE = 28
LOGO_BADGE_RADIUS = 8
APP_NAME_COLOR = "#163A6B"

NAV_HEIGHT = 50
NAV_ICON_SIZE = 18
NAV_PAD_LEFT = 20
NAV_LABEL_X = 50  # x della label -> spacing icona/label = 50 - 20 - 18 = 12
NAV_ACTIVE_BG = "#D6EAFB"
NAV_ACTIVE_COLOR = "#163A6B"
NAV_INACTIVE_COLOR = "#2E2E2E"
# Colore delle icone nav: nel mockup NON segue il colore del testo (misurato dal Sketch,
# stroke delle icone: attiva #2563C9 / inattiva #3D9BE9).
NAV_ICON_ACTIVE_COLOR = "#2563C9"
NAV_ICON_INACTIVE_COLOR = "#3D9BE9"
NAV_HOVER_BG = "#F7F9FC"  # hover voce inattiva: non nel mockup, scelta documentata

# Icone chevron (toggle) e log-out: colore non nel mockup, derivato/documentato.
CONTROL_COLOR = "#5B6472"

AVATAR_BG = "#2563C9"
AVATAR_SIZE = 32
USER_NAME_COLOR = "#2E2E2E"

TOGGLE_ICON_SIZE = 18
LOGOUT_ICON_SIZE = 16

# Centratura icona/tassello nella rail collassata: (72 - dimensione) / 2.
_COLLAPSED_ICON_MARGIN = (WIDTH_COLLAPSED - NAV_ICON_SIZE) // 2


@dataclass
class SidebarItem:
    """Descrittore di una voce di navigazione della sidebar."""

    id: str
    label: str
    icon_name: str


def _make_font(pixel_size: int, weight: int) -> QFont:
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(weight))
    font.setPixelSize(pixel_size)
    return font


def _clear_layout(layout: QBoxLayout) -> None:
    """Svuota un layout riutilizzabile: i widget vengono staccati (non distrutti), i
    sotto-layout eliminati. Chi possiede i widget mantiene i riferimenti come attributi."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
        else:
            sublayout = item.layout()
            if sublayout is not None:
                _clear_layout(sublayout)
                sublayout.deleteLater()


def _flat_icon_button(icon_name: str, icon_size: int, hit_size: int) -> QPushButton:
    """Bottone piatto a sola icona (toggle/logout): sfondo trasparente, cursore a mano."""
    button = QPushButton()
    button.setIcon(load_lucide_icon(icon_name, CONTROL_COLOR, icon_size))
    button.setIconSize(QSize(icon_size, icon_size))
    button.setFixedSize(hit_size, hit_size)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFlat(True)
    button.setStyleSheet(
        """
        QPushButton { background: transparent; border: none; }
        QPushButton:hover { background: #EFF4FA; border-radius: 6px; }
        """
    )
    return button


def _build_logo_badge() -> QLabel:
    badge = QLabel()
    badge.setFixedSize(LOGO_BADGE_SIZE, LOGO_BADGE_SIZE)
    badge.setStyleSheet(
        f"background-color: {LOGO_BADGE_BG}; border-radius: {LOGO_BADGE_RADIUS}px;"
    )
    badge.setPixmap(load_lucide_icon("route", "#FFFFFF", 16).pixmap(QSize(16, 16)))
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return badge


class _NavItem(QWidget):
    """Singola voce di navigazione cliccabile (riga h50)."""

    clicked = Signal(str)

    def __init__(self, item: SidebarItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item.id
        self.label_text = item.label
        self.icon_name = item.icon_name

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(NAV_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._active = False
        self._collapsed = False
        self._hovered = False
        # Cache dei pixmap per colore: _refresh scatta su ogni hover/leave, senza cache
        # ricaricherebbe/riparserebbe l'SVG da disco a ogni passaggio del mouse.
        self._icon_cache: dict[str, QPixmap] = {}

        self._icon = QLabel()
        self._icon.setFixedSize(NAV_ICON_SIZE, NAV_ICON_SIZE)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._text = QLabel(item.label)
        self._text.setFont(_make_font(14, 500))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NAV_PAD_LEFT, 0, 0, 0)
        layout.setSpacing(NAV_LABEL_X - NAV_PAD_LEFT - NAV_ICON_SIZE)
        layout.addWidget(self._icon)
        layout.addWidget(self._text)
        layout.addStretch(1)

        self._refresh()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._refresh()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._text.setVisible(not collapsed)
        # In collassato la label diventa un tooltip nativo Qt (vedi scelta documentata).
        self.setToolTip(self.label_text if collapsed else "")
        margin = _COLLAPSED_ICON_MARGIN if collapsed else NAV_PAD_LEFT
        right = _COLLAPSED_ICON_MARGIN if collapsed else 0
        self.layout().setContentsMargins(margin, 0, right, 0)
        self._refresh()

    def enterEvent(self, event: QEvent) -> None:
        self._hovered = True
        self._refresh()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        self._refresh()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_id)
        super().mousePressEvent(event)

    def _refresh(self) -> None:
        if self._active:
            bg, color, weight, icon_color = NAV_ACTIVE_BG, NAV_ACTIVE_COLOR, 600, NAV_ICON_ACTIVE_COLOR
        elif self._hovered:
            bg, color, weight, icon_color = NAV_HOVER_BG, NAV_INACTIVE_COLOR, 500, NAV_ICON_INACTIVE_COLOR
        else:
            bg, color, weight, icon_color = "transparent", NAV_INACTIVE_COLOR, 500, NAV_ICON_INACTIVE_COLOR

        self.setStyleSheet(f"background-color: {bg};")
        self._icon.setStyleSheet("background: transparent;")
        pixmap = self._icon_cache.get(icon_color)
        if pixmap is None:
            pixmap = load_lucide_icon(self.icon_name, icon_color, NAV_ICON_SIZE).pixmap(
                QSize(NAV_ICON_SIZE, NAV_ICON_SIZE)
            )
            self._icon_cache[icon_color] = pixmap
        self._icon.setPixmap(pixmap)
        self._text.setFont(_make_font(14, weight))
        self._text.setStyleSheet(f"color: {color}; background: transparent;")


class _LogoRow(QWidget):
    """Riga logo: tassello + nome app + toggle. Ricostruita al cambio di stato collassato."""

    toggleRequested = Signal()

    def __init__(self, app_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._badge = _build_logo_badge()
        self._app_name = QLabel(app_name)
        self._app_name.setFont(_make_font(17, 500))
        self._app_name.setStyleSheet(f"color: {APP_NAME_COLOR}; background: transparent;")
        self._toggle = _flat_icon_button("chevron-left", TOGGLE_ICON_SIZE, 28)
        self._toggle.clicked.connect(self.toggleRequested)

        self._layout = QVBoxLayout(self)
        self.set_collapsed(False)

    def set_collapsed(self, collapsed: bool) -> None:
        _clear_layout(self._layout)
        self._toggle.setIcon(
            load_lucide_icon(
                "chevron-right" if collapsed else "chevron-left",
                CONTROL_COLOR,
                TOGGLE_ICON_SIZE,
            )
        )
        if collapsed:
            self._app_name.hide()
            self._layout.setContentsMargins(0, 14, 0, 14)
            self._layout.setSpacing(8)
            self._layout.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignHCenter)
            self._layout.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            self._app_name.show()
            self._layout.setContentsMargins(0, 18, 0, 18)
            row = QHBoxLayout()
            row.setContentsMargins(20, 0, 20, 0)
            row.setSpacing(8)
            row.addWidget(self._badge)
            row.addWidget(self._app_name)
            row.addStretch(1)
            row.addWidget(self._toggle)
            self._layout.addLayout(row)


class _UserRow(QWidget):
    """Riga utente: avatar + nome + logout. Ricostruita al cambio di stato collassato."""

    logoutRequested = Signal()

    def __init__(self, user_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        initial = user_name[:1].upper() if user_name else "?"
        self._avatar = QLabel(initial)
        self._avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setFont(_make_font(14, 600))
        self._avatar.setStyleSheet(
            f"background-color: {AVATAR_BG}; border-radius: {AVATAR_SIZE // 2}px;"
            " color: #FFFFFF;"
        )

        self._name = QLabel(user_name)
        self._name.setFont(_make_font(14, 500))
        self._name.setStyleSheet(f"color: {USER_NAME_COLOR}; background: transparent;")

        self._logout = _flat_icon_button("log-out", LOGOUT_ICON_SIZE, 24)
        self._logout.clicked.connect(self.logoutRequested)

        self._layout = QVBoxLayout(self)
        self.set_collapsed(False)

    def set_collapsed(self, collapsed: bool) -> None:
        _clear_layout(self._layout)
        if collapsed:
            # Rail: solo l'avatar centrato; il logout resta raggiungibile riespandendo.
            self._name.hide()
            self._logout.hide()
            self._layout.setContentsMargins(0, 16, 0, 16)
            self._layout.addWidget(self._avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            self._name.show()
            self._logout.show()
            self._layout.setContentsMargins(0, 16, 0, 16)
            row = QHBoxLayout()
            row.setContentsMargins(20, 0, 20, 0)
            row.setSpacing(12)
            row.addWidget(self._avatar)
            row.addWidget(self._name)
            row.addStretch(1)
            row.addWidget(self._logout)
            self._layout.addLayout(row)


def _divider() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {DIVIDER_COLOR};")
    return line


class Sidebar(QWidget):
    """Barra di navigazione laterale: logo, voci nav, riga utente. Espandibile/collassabile.

    Componente puramente di navigazione: non gestisce il contenuto delle pagine (nessun
    `QStackedWidget` integrato) — chi lo usa si iscrive a `navigated` per cambiare pagina.
    Lo stato collassato e' ricordato nell'istanza, mai persistito su disco.
    """

    navigated = Signal(str)
    logoutRequested = Signal()
    collapsedChanged = Signal(bool)

    def __init__(
        self,
        items: list[SidebarItem],
        app_name: str = "LogiPlan",
        user_name: str = "Davide",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not items:
            raise ValueError("Sidebar richiede almeno una voce di navigazione.")

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"Sidebar {{ background-color: {BG_COLOR}; }}")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(WIDTH_EXPANDED)

        self._collapsed = False
        self._current_id: str | None = None

        self._logo_row = _LogoRow(app_name)
        self._logo_row.toggleRequested.connect(self.toggle_collapsed)

        self._user_row = _UserRow(user_name)
        self._user_row.logoutRequested.connect(self.logoutRequested)

        self._nav_items: list[_NavItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._logo_row)
        layout.addWidget(_divider())
        layout.addSpacing(8)
        for i, item in enumerate(items):
            nav = _NavItem(item)
            nav.clicked.connect(self._on_nav_clicked)
            self._nav_items.append(nav)
            layout.addWidget(nav)
            # Linea divisoria #E3EFFB tra una voce e la successiva (come nel mockup).
            if i < len(items) - 1:
                layout.addWidget(_divider())
        layout.addStretch(1)
        layout.addWidget(_divider())
        layout.addWidget(self._user_row)

        self.set_active(items[0].id)

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    @property
    def current_item(self) -> str | None:
        return self._current_id

    def set_active(self, item_id: str) -> None:
        """Evidenzia la voce `item_id` (solo aggiornamento visivo, nessun segnale)."""
        found = False
        for nav in self._nav_items:
            is_active = nav.item_id == item_id
            nav.set_active(is_active)
            found = found or is_active
        if found:
            self._current_id = item_id

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self.setFixedWidth(WIDTH_COLLAPSED if collapsed else WIDTH_EXPANDED)
        self._logo_row.set_collapsed(collapsed)
        for nav in self._nav_items:
            nav.set_collapsed(collapsed)
        self._user_row.set_collapsed(collapsed)
        self.collapsedChanged.emit(collapsed)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _on_nav_clicked(self, item_id: str) -> None:
        self.set_active(item_id)
        self.navigated.emit(item_id)
