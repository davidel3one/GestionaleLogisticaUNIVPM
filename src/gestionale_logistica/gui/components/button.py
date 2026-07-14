"""Componente Button riusabile, 5 varianti (fonte: mockup Sketch, gui-design.sketch)."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

FONT_FAMILY = "Inter"

HOVER_DARKEN = 0.90
PRESSED_DARKEN = 0.85
DISABLED_OPACITY = 0.45


class ButtonVariant(str, Enum):
    PRIMARY = "primary"
    PRIMARY_LARGE = "primary-large"
    SECONDARY = "secondary"
    SECONDARY_HEADER_ADD = "secondary-header-add"
    ICON_ONLY = "icon-only"


def _darken(hex_color: str, factor: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


class Button(QPushButton):
    """Bottone riusabile con 5 varianti visive definite dal mockup Sketch."""

    def __init__(
        self,
        variant: ButtonVariant,
        text: str = "",
        icon: QIcon | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._variant = ButtonVariant(variant)

        if self._variant == ButtonVariant.ICON_ONLY and icon is None:
            raise ValueError("La variante 'icon-only' richiede un'icona.")
        if self._variant == ButtonVariant.SECONDARY_HEADER_ADD and icon is None:
            raise ValueError("La variante 'secondary-header-add' richiede un'icona.")

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(text, icon)

    def _build(self, text: str, icon: QIcon | None) -> None:
        variant = self._variant
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if variant == ButtonVariant.ICON_ONLY:
            self.setFixedSize(32, 32)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._icon_label(icon, 15))
            self._apply_style(background="#F7F9FC", border=None, radius=8)
            return

        if variant == ButtonVariant.PRIMARY_LARGE:
            self.setFixedHeight(44)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._text_label(text, "#FFFFFF", 500, 14))
            self._apply_style(background="#2563C9", border=None, radius=10)
            return

        if variant == ButtonVariant.PRIMARY:
            layout.setContentsMargins(10, 6, 10, 6)
            layout.setSpacing(5)
            text_color, radius = "#FFFFFF", 7
            background, border = "#2563C9", None
            icon_size, weight, size = 12, 600, 12
        elif variant == ButtonVariant.SECONDARY:
            layout.setContentsMargins(10, 6, 10, 6)
            layout.setSpacing(5)
            text_color, radius = "#2E2E2E", 7
            background, border = "#F7F9FC", "#E5EAF0"
            icon_size, weight, size = 12, 600, 12
        else:  # SECONDARY_HEADER_ADD
            layout.setContentsMargins(14, 8, 14, 8)
            layout.setSpacing(8)
            text_color, radius = "#2E2E2E", 8
            background, border = "#F7F9FC", "#E5EAF0"
            icon_size, weight, size = 15, 600, 13

        if icon is not None:
            layout.addWidget(self._icon_label(icon, icon_size))
        layout.addWidget(self._text_label(text, text_color, weight, size))
        self._apply_style(background=background, border=border, radius=radius)

    def _icon_label(self, icon: QIcon, size: int) -> QLabel:
        label = QLabel(self)
        label.setPixmap(icon.pixmap(QSize(size, size)))
        label.setFixedSize(size, size)
        return label

    def _text_label(self, text: str, color: str, weight: int, size: int) -> QLabel:
        label = QLabel(text, self)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(weight))
        font.setPixelSize(size)
        label.setFont(font)
        label.setStyleSheet(f"color: {color};")
        return label

    def _apply_style(self, background: str, border: str | None, radius: int) -> None:
        border_css = f"1px solid {border}" if border else "none"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {background};
                border: {border_css};
                border-radius: {radius}px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {_darken(background, HOVER_DARKEN)};
            }}
            QPushButton:pressed {{
                background-color: {_darken(background, PRESSED_DARKEN)};
            }}
            """
        )

    def sizeHint(self) -> QSize:
        return self.layout().sizeHint()

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        if enabled:
            self.setGraphicsEffect(None)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(DISABLED_OPACITY)
            self.setGraphicsEffect(effect)
            self.setCursor(Qt.CursorShape.ArrowCursor)
