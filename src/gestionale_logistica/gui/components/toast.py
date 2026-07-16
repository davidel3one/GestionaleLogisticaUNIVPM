"""Toast: notifica non bloccante impilabile in overlay.

Non e' un elemento del mockup Sketch (nessuna istanza "Toast"/"Notification" nel file,
verificato via MCP su tutte le pagine). Stile e palette riusano interamente token gia'
misurati altrove nel progetto (IconChip, DEFAULT_STATUS_BADGE_COLORS): sfondo tinta piena
+ testo/icona nello stesso colore accento, stesso principio di STATUS_BADGE/CATEGORIA_BADGE.
Layout (banner con icona a sinistra, titolo+messaggio, chiusura a destra, angoli arrotondati)
e comportamento (auto-dismiss + chiusura manuale, impilamento in alto a destra) confermati
esplicitamente dall'utente in assenza di mockup, come gia' fatto per Modal/Tooltip.
"""

from __future__ import annotations

import enum

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainterPath, QPaintEvent, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gestionale_logistica.gui.components.icon_chip import IconChip, IconChipVariant
from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"

WIDTH = 360
RADIUS = 14  # stesso token di CARD_RADIUS/Modal: famiglia "elemento flottante arrotondato"
PADDING_H = 16
PADDING_V = 14
CONTENT_GAP = 12

ICON_SIZE = 18
CLOSE_BUTTON_SIZE = 20
CLOSE_ICON_SIZE = 13

# Barra di countdown in basso: indica quanto manca all'auto-dismiss. Non nel mockup
# (il Toast non c'e' proprio) - richiesta esplicita dell'utente 2026-07-16.
PROGRESS_BAR_HEIGHT = 3
PROGRESS_EASING = QEasingCurve.Type.Linear  # lineare: e' un countdown, non una transizione

DEFAULT_DURATION_MS = 4500

STACK_GAP = 12
MARGIN_TOP = 24
MARGIN_RIGHT = 24


class ToastVariant(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# (nome icona Lucide, colore accento, colore sfondo) per variante - accento/sfondo riusati
# 1:1 da IconChipVariant (SUCCESS/ERROR/INFO) e dalla coppia ambra gia' misurata per
# STATUS_BADGE/CATEGORIA_BADGE (WARNING, vedi IconChipVariant.AMBER in icon_chip.py).
_VARIANT_STYLE: dict[ToastVariant, tuple[str, str, str]] = {
    ToastVariant.SUCCESS: ("circle-check-big", "#1E8E3E", "#DFF5E5"),
    ToastVariant.ERROR: ("circle-x", "#C0392B", "#FBE4E1"),
    ToastVariant.WARNING: ("triangle-alert", "#B45309", "#FEF3C7"),
    ToastVariant.INFO: ("info", "#3D9BE9", "#D6EAFB"),
}

_ICON_CHIP_VARIANT: dict[ToastVariant, IconChipVariant] = {
    ToastVariant.SUCCESS: IconChipVariant.GREEN,
    ToastVariant.ERROR: IconChipVariant.RED,
    ToastVariant.WARNING: IconChipVariant.AMBER,
    ToastVariant.INFO: IconChipVariant.LIGHT_BLUE,
}


class Toast(QFrame):
    """Singolo banner di notifica: IconChip + titolo (+ messaggio opzionale) + chiusura.

    Sfondo disegnato a mano in `paintEvent` (non QSS `border-radius`), stesso approccio
    di `_ModalCard`/`Tooltip`. Nessuna ombra: il riferimento visivo fornito dall'utente
    era un banner piatto, e un `QGraphicsDropShadowEffect` sopra la barra di countdown
    produceva un alone grigio visibile proprio agli angoli arrotondati in basso (dove
    l'offset verticale dell'ombra la porta a "uscire" dalla sagoma colorata) - rimossa.
    """

    closed = Signal(QFrame)  # emette se stesso, per farsi rimuovere da ToastManager

    def __init__(
        self,
        variant: ToastVariant,
        title: str,
        message: str = "",
        duration_ms: int = DEFAULT_DURATION_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        icon_name, accent_color, bg_color = _VARIANT_STYLE[variant]
        self._bg_color = QColor(bg_color)
        self._progress_color = QColor(accent_color)
        self._show_progress = duration_ms > 0
        self._progress = 1.0  # 1.0 = countdown appena partito, 0.0 = in scadenza

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(WIDTH)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(PADDING_H, PADDING_V, PADDING_H, PADDING_V)
        layout.setSpacing(CONTENT_GAP)

        icon_chip = IconChip(icon_name, _ICON_CHIP_VARIANT[variant], size=ICON_SIZE)
        layout.addWidget(icon_chip, alignment=Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(self._build_label(title, accent_color, 600, 13))
        if message:
            text_column.addWidget(self._build_label(message, accent_color, 500, 12))
        layout.addLayout(text_column, 1)

        layout.addWidget(
            self._build_close_button(accent_color), alignment=Qt.AlignmentFlag.AlignTop
        )

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self._dismiss)
            self._progress_anim = QPropertyAnimation(self, b"progress", self)
            self._progress_anim.setDuration(duration_ms)
            self._progress_anim.setStartValue(1.0)
            self._progress_anim.setEndValue(0.0)
            self._progress_anim.setEasingCurve(PROGRESS_EASING)
            self._progress_anim.start()

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = value
        self.update()

    progress = Property(float, _get_progress, _set_progress)

    def _build_label(self, text: str, color: str, weight: int, size: int) -> QLabel:
        label = QLabel(text)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(weight))
        font.setPixelSize(size)
        label.setFont(font)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {color}; background: transparent;")
        return label

    def _build_close_button(self, accent_color: str) -> QPushButton:
        # Bottone piatto trasparente, non Button.ICON_ONLY: quella variante disegna un box
        # grigio #F7F9FC fisso, fuori posto sopra lo sfondo colorato del toast (stesso motivo
        # gia' documentato per i pulsanti toggle/logout di Sidebar).
        button = QPushButton()
        button.setFixedSize(CLOSE_BUTTON_SIZE, CLOSE_BUTTON_SIZE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(load_lucide_icon("x", accent_color, CLOSE_ICON_SIZE))
        button.setIconSize(button.iconSize().scaled(CLOSE_ICON_SIZE, CLOSE_ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio))
        button.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: {CLOSE_BUTTON_SIZE // 2}px;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 0, 0, 25);
            }}
            """
        )
        button.clicked.connect(self._dismiss)
        return button

    def _dismiss(self) -> None:
        self.closed.emit(self)
        self.deleteLater()

    def paintEvent(self, event: QPaintEvent) -> None:
        rounded_path = QPainterPath()
        rounded_path.addRoundedRect(0, 0, self.width(), self.height(), RADIUS, RADIUS)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._bg_color)
        painter.drawPath(rounded_path)

        if self._show_progress:
            # Clip sulla forma arrotondata del toast: la barra rettangolare risulta
            # "tagliata" dagli stessi angoli del frame senza dover ricalcolare a mano
            # quali angoli arrotondare a seconda della larghezza residua.
            painter.setClipPath(rounded_path)
            bar_width = self.width() * self._progress
            bar_rect_y = self.height() - PROGRESS_BAR_HEIGHT
            painter.fillRect(0, bar_rect_y, round(bar_width), PROGRESS_BAR_HEIGHT, self._progress_color)


class ToastManager(QWidget):
    """Overlay che impila i `Toast` in alto a destra di un widget parent, tenendosi
    sincronizzato con il suo ridimensionamento (stesso pattern di `Modal.show_over`/
    `eventFilter`, qui attaccato una volta sola invece che per singola apertura).

    Un'istanza per finestra/pagina che deve mostrare toast: `manager = ToastManager(parent)`,
    poi `manager.show_success(...)`/`show_error(...)`/`show_warning(...)`/`show_info(...)`
    da qualunque punto del codice che ha un riferimento al manager.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(STACK_GAP)
        self.setFixedWidth(WIDTH)

        parent.installEventFilter(self)
        # Senza questa chiamata l'altezza resta quella di default di un QWidget vuoto
        # (100x30, ridotta in larghezza da `setFixedWidth`): un rettangolo fantasma di
        # 360x30 in alto a destra della pagina, sopra ogni altro widget (`raise_()` sotto),
        # che intercetta hover/click di qualunque bottone si trovi in quella zona - tipicamente
        # proprio i bottoni di azione dell'header - finche' non viene mostrato il primo toast
        # (che triggera `adjustSize()` in `show_toast`).
        self.adjustSize()
        self._reposition()
        self.raise_()
        self.show()

    def show_toast(
        self,
        variant: ToastVariant,
        title: str,
        message: str = "",
        duration_ms: int = DEFAULT_DURATION_MS,
    ) -> Toast:
        toast = Toast(variant, title, message, duration_ms, parent=self)
        toast.closed.connect(self._on_toast_closed)
        self._layout.addWidget(toast)
        toast.show()
        self.adjustSize()
        self.raise_()
        return toast

    def show_success(self, title: str, message: str = "", duration_ms: int = DEFAULT_DURATION_MS) -> Toast:
        return self.show_toast(ToastVariant.SUCCESS, title, message, duration_ms)

    def show_error(self, title: str, message: str = "", duration_ms: int = DEFAULT_DURATION_MS) -> Toast:
        return self.show_toast(ToastVariant.ERROR, title, message, duration_ms)

    def show_warning(self, title: str, message: str = "", duration_ms: int = DEFAULT_DURATION_MS) -> Toast:
        return self.show_toast(ToastVariant.WARNING, title, message, duration_ms)

    def show_info(self, title: str, message: str = "", duration_ms: int = DEFAULT_DURATION_MS) -> Toast:
        return self.show_toast(ToastVariant.INFO, title, message, duration_ms)

    def _on_toast_closed(self, toast: Toast) -> None:
        self._layout.removeWidget(toast)
        self.adjustSize()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(parent.width() - WIDTH - MARGIN_RIGHT, MARGIN_TOP)

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self._reposition()
        return super().eventFilter(watched, event)
