"""Componente Modal riusabile, chrome generica overlay (fonte: mockup Sketch, gui-design.sketch)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gestionale_logistica.gui.components.button import Button, ButtonVariant
from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"

BACKDROP_COLOR = QColor(0, 0, 0, 77)  # #0000004D

CARD_RADIUS = 14
CARD_SHADOW_COLOR = QColor(0, 0, 0, 38)  # #00000026
CARD_SHADOW_OFFSET_Y = 12
CARD_SHADOW_BLUR = 40

TITLE_COLOR = "#2E2E2E"
SUBTITLE_COLOR = "#8A93A0"
DIVIDER_COLOR = "#EDEFF3"

HEADER_HEIGHT = 92
HEADER_TITLE_POS = (32, 28)
HEADER_SUBTITLE_POS = (32, 60)

CLOSE_BUTTON_SIZE = 32
CLOSE_BUTTON_Y = 24
CLOSE_BUTTON_MARGIN_NARROW = 24  # width < WIDE_WIDTH_THRESHOLD
CLOSE_BUTTON_MARGIN_WIDE = 32  # width >= WIDE_WIDTH_THRESHOLD
WIDE_WIDTH_THRESHOLD = 900

CONTENT_PADDING_TOP = 32
CONTENT_PADDING_SIDE = 32

FOOTER_GAP_ABOVE_BUTTONS = 16
FOOTER_BUTTON_SPACING = 8
FOOTER_PADDING_BOTTOM = 24


class _ModalCard(QFrame):
    """Pannello bianco centrato del Modal: chrome distinta da `Card` (nessun bordo)."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Assorbe i click dentro la card (e quelli propagati dai figli "neutri" di header/
        # content/footer): senza questo l'evento risalirebbe a Modal.mousePressEvent, che lo
        # scambierebbe per un click sul backdrop e chiuderebbe il modale. Solo il backdrop chiude.
        event.accept()


class Modal(QWidget):
    """Overlay modale in-finestra: backdrop + card centrata, chrome generica riusabile.

    Copre l'intero parent passato a `show_over` (non un QDialog separato, per garantire
    il dim-backdrop del mockup su tutte le piattaforme). Il chiamante riempie
    `content_layout` con il proprio contenuto (form, tabelle, badge, ecc.).
    """

    closed = Signal()

    def __init__(
        self,
        title: str,
        subtitle: str | None = None,
        width: int = 560,
        footer_buttons: list[Button] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tracked_parent: QWidget | None = None

        close_margin = (
            CLOSE_BUTTON_MARGIN_WIDE if width >= WIDE_WIDTH_THRESHOLD else CLOSE_BUTTON_MARGIN_NARROW
        )

        self._card = _ModalCard()
        self._card.setFixedWidth(width)
        self._card.setStyleSheet(
            f"""
            _ModalCard {{
                background-color: #FFFFFF;
                border: none;
                border-radius: {CARD_RADIUS}px;
            }}
            """
        )
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setColor(CARD_SHADOW_COLOR)
        shadow.setOffset(0, CARD_SHADOW_OFFSET_Y)
        shadow.setBlurRadius(CARD_SHADOW_BLUR)
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self._build_header(title, subtitle, width, close_margin))
        card_layout.addWidget(self._build_divider(width))
        card_layout.addWidget(self._build_content_container())
        if footer_buttons:
            card_layout.addWidget(self._build_divider(width))
            card_layout.addWidget(self._build_footer(footer_buttons, width))

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)

    def _build_header(self, title: str, subtitle: str | None, width: int, close_margin: int) -> QWidget:
        header = QWidget()
        header.setFixedSize(width, HEADER_HEIGHT)

        title_label = QLabel(title, header)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(600))
        font.setPixelSize(19)
        title_label.setFont(font)
        title_label.setStyleSheet(f"color: {TITLE_COLOR};")
        title_label.move(*HEADER_TITLE_POS)
        title_label.adjustSize()

        if subtitle:
            subtitle_label = QLabel(subtitle, header)
            font = QFont(FONT_FAMILY)
            font.setWeight(QFont.Weight(500))
            font.setPixelSize(13)
            subtitle_label.setFont(font)
            subtitle_label.setStyleSheet(f"color: {SUBTITLE_COLOR};")
            subtitle_label.move(*HEADER_SUBTITLE_POS)
            subtitle_label.adjustSize()

        close_button = Button(
            ButtonVariant.ICON_ONLY, icon=load_lucide_icon("x", "#5B6472", 15), parent=header
        )
        close_button.move(width - close_margin - CLOSE_BUTTON_SIZE, CLOSE_BUTTON_Y)
        close_button.clicked.connect(self.close)

        return header

    def _build_divider(self, width: int) -> QFrame:
        divider = QFrame()
        divider.setFixedSize(width, 1)
        divider.setStyleSheet(f"background-color: {DIVIDER_COLOR}; border: none;")
        return divider

    def _build_content_container(self) -> QWidget:
        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(
            CONTENT_PADDING_SIDE, CONTENT_PADDING_TOP, CONTENT_PADDING_SIDE, 0
        )
        return container

    def _build_footer(self, buttons: list[Button], width: int) -> QWidget:
        footer = QWidget()
        footer.setFixedWidth(width)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            CONTENT_PADDING_SIDE, FOOTER_GAP_ABOVE_BUTTONS, CONTENT_PADDING_SIDE, FOOTER_PADDING_BOTTOM
        )
        layout.setSpacing(FOOTER_BUTTON_SPACING)
        layout.addStretch(1)
        for button in buttons:
            layout.addWidget(button)
        return footer

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def show_over(self, parent_widget: QWidget) -> None:
        """Mostra il modale come overlay a tutta area su `parent_widget`."""
        self.setParent(parent_widget)
        self._tracked_parent = parent_widget
        parent_widget.installEventFilter(self)
        self.setGeometry(parent_widget.rect())
        self.raise_()
        self.show()
        self.setFocus()

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:
        if watched is self._tracked_parent and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKDROP_COLOR)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Click sul backdrop (non sulla card, che intercetta l'evento prima) chiude il
        # modale: comportamento standard atteso, non specificato nel mockup statico.
        if event.button() == Qt.MouseButton.LeftButton:
            self.close()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # ESC per chiudere: comportamento standard atteso, non specificato nel mockup statico.
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._tracked_parent is not None:
            self._tracked_parent.removeEventFilter(self)
        self.closed.emit()
        super().closeEvent(event)
