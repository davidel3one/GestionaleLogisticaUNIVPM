"""KpiCard: card KPI della Dashboard (fonte: mockup Sketch, artboard Dashboard, "KPI Card / ...")."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gestionale_logistica.gui.components.card import Card
from gestionale_logistica.gui.components.icon_chip import VARIANT_COLORS, IconChip, IconChipVariant

_VALUE_COLOR = "#163A6B"
_LABEL_COLOR = "#5B6472"


def _kpi_font(pixel_size: int, weight: int = 500) -> QFont:
    font = QFont("Inter")
    font.setWeight(QFont.Weight(weight))
    font.setPixelSize(pixel_size)
    return font


class KpiCard(Card):
    """KPI Card: valore in evidenza (+ trend opzionale) sopra, icona colorata + etichetta sotto.

    Il testo del trend riusa il colore icona della `variant`: nel mockup ogni card colorata
    (verde per i consegnati, rosso per i falliti) ha il proprio trend nello stesso colore
    dell'icona, non un colore fisso positivo/negativo indipendente dalla card.
    """

    def __init__(
        self,
        value: str,
        label: str,
        icon_name: str,
        variant: IconChipVariant,
        trend: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(padding_horizontal=20, padding_vertical=18, spacing=12, parent=parent)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        value_label = QLabel(value)
        value_label.setFont(_kpi_font(28))
        value_label.setStyleSheet(f"color: {_VALUE_COLOR}; background: transparent;")
        top_row.addWidget(value_label)
        top_row.addStretch(1)

        if trend:
            trend_label = QLabel(trend)
            trend_label.setFont(_kpi_font(12))
            trend_label.setStyleSheet(f"color: {VARIANT_COLORS[variant][0]}; background: transparent;")
            top_row.addWidget(trend_label)

        self.content_layout.addLayout(top_row)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)
        header_row.addWidget(IconChip(icon_name, variant, size=16))

        label_widget = QLabel(label.upper())
        label_widget.setFont(_kpi_font(12))
        label_widget.setStyleSheet(f"color: {_LABEL_COLOR}; background: transparent;")
        header_row.addWidget(label_widget)
        header_row.addStretch(1)

        self.content_layout.addLayout(header_row)
