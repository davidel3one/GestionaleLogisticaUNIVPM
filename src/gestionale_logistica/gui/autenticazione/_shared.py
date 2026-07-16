"""Helper di layout/testo condivisi dalle 3 view di autenticazione (Login, Registrazione,
Conferma OTP) - fattorizzati per non ripetere lo stesso QSS in ogni view. Fonte valori:
mockup Sketch, misurati via MCP (`run_code`) sulle 3 istanze "Auth Card"."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

FONT_FAMILY = "Inter"
TITLE_COLOR = "#2E2E2E"
SUBTITLE_COLOR = "#9AA1AA"
CAPTION_COLOR = "#5B6472"
ERROR_COLOR = "#C0392B"

CONTENT_WIDTH = 360


def title_label(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(15)
    label.setFont(font)
    label.setStyleSheet(f"color: {TITLE_COLOR};")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def hint_label(
    text: str,
    color: str = SUBTITLE_COLOR,
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
) -> QLabel:
    label = QLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(500))
    font.setPixelSize(12)
    label.setFont(font)
    label.setStyleSheet(f"color: {color};")
    label.setAlignment(alignment)
    label.setWordWrap(True)
    return label


def build_centered_layout(inner: QWidget) -> QVBoxLayout:
    """Centra `inner` (larghezza fissa) in orizzontale e verticale, come l'Auth Card nel
    mockup (sempre centrata nel frame, senza box/bordo/ombra visibili)."""
    row = QHBoxLayout()
    row.addStretch(1)
    row.addWidget(inner)
    row.addStretch(1)

    outer = QVBoxLayout()
    outer.addStretch(1)
    outer.addLayout(row)
    outer.addStretch(1)
    return outer
