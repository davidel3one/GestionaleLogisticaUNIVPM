"""PlanKpiCard: card KPI "flat" della Summary Row (Pianificazione — Automatica).

Diversa dalla `KpiCard` della Dashboard: icona colorata senza chip circolare (nessuno sfondo
dietro l'icona nel mockup, misurato — `Icon Chip` contiene solo il grafico, nessuna forma di
riempimento) e colori di valore/icona indipendenti e parametrici, misurati per card:
"VIAGGI PROPOSTI"/"ORDINI ASSEGNATI" hanno valore Blu Scuro `#163A6B` e icona Azzurro `#3D9BE9`
(disaccoppiati, come nella `KpiCard` Dashboard); "ORDINI NON ASSEGNATI" rompe quella convenzione e
usa `#B45309` (ambra, segnale di attenzione) sia per valore sia per icona — misurato nel mockup,
non dedotto."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gestionale_logistica.gui.components.card import Card
from gestionale_logistica.gui.components.icons import load_lucide_icon

_LABEL_COLOR = "#5B6472"


def _kpi_font(pixel_size: int, weight: int = 500) -> QFont:
    font = QFont("Inter")
    font.setWeight(QFont.Weight(weight))
    font.setPixelSize(pixel_size)
    return font


class PlanKpiCard(Card):
    def __init__(
        self,
        value: str,
        label: str,
        icon_name: str,
        value_color: str,
        icon_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(padding_horizontal=20, padding_vertical=18, spacing=12, parent=parent)

        self._value_label = QLabel(value)
        self._value_label.setFont(_kpi_font(28))
        self._value_label.setStyleSheet(f"color: {value_color}; background: transparent;")
        self.content_layout.addWidget(self._value_label)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        icon_label = QLabel()
        icon_label.setPixmap(load_lucide_icon(icon_name, icon_color, 16).pixmap(16, 16))
        icon_label.setFixedSize(16, 16)
        icon_label.setStyleSheet("background: transparent;")
        header_row.addWidget(icon_label)

        label_widget = QLabel(label.upper())
        label_widget.setFont(_kpi_font(12))
        label_widget.setStyleSheet(f"color: {_LABEL_COLOR}; background: transparent;")
        header_row.addWidget(label_widget)
        header_row.addStretch(1)

        self.content_layout.addLayout(header_row)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)
