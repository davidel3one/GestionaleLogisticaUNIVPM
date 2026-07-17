"""PlanningDayCard: card di un giorno nel widget "Pianificazione — prossimi giorni" della
Dashboard (fonte: mockup Sketch, artboard Dashboard, "Day / ...")."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

_BG = "#F7F9FC"
_RADIUS = 10
_DAY_LABEL_COLOR = "#5B6472"
_BADGE_BG = "#D6EAFB"
_BADGE_TEXT_COLOR = "#2563C9"
_BADGE_RADIUS = 7
_BADGE_HEIGHT = 14


def _day_card_font(pixel_size: int) -> QFont:
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(pixel_size)
    return font


class PlanningDayCard(QFrame):
    """Card di un giorno: etichetta (es. "Lun 13") + badge pillola col conteggio viaggi."""

    def __init__(self, day_label: str, count_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setStyleSheet(
            f"""
            PlanningDayCard {{
                background-color: {_BG};
                border-radius: {_RADIUS}px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(10)

        day = QLabel(day_label)
        day.setFont(_day_card_font(12))
        day.setStyleSheet(f"color: {_DAY_LABEL_COLOR}; background: transparent;")
        layout.addWidget(day)

        badge = QLabel(count_label)
        badge.setFont(_day_card_font(11))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(_BADGE_HEIGHT)
        badge.setStyleSheet(
            f"""
            QLabel {{
                background-color: {_BADGE_BG};
                color: {_BADGE_TEXT_COLOR};
                border-radius: {_BADGE_RADIUS}px;
                padding: 0 6px;
            }}
            """
        )
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
