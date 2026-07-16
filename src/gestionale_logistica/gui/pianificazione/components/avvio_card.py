"""AvvioCard: card "Avvia composizione viaggio", condivisa da Pianificazione — Manuale (RF10) e
Assistita (RF12) — stesso layout misurato su entrambi i mockup Sketch: selezione composizione
squadra disponibile, data, bottone "Avvia composizione"."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gestionale_logistica.gui.components import Button, ButtonVariant, Card, DateFilterField, Select

TITLE_COLOR = "#2E2E2E"
ALERT_COLOR = "#C0392B"


def _card_title(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(15)
    label.setFont(font)
    label.setStyleSheet(f"color: {TITLE_COLOR}; background: transparent;")
    return label


class AvvioCard(Card):
    avviaRequested = Signal(str, object)  # composizione_id, date
    dataChanged = Signal(object)  # date

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(padding_horizontal=24, padding_vertical=20, spacing=16, parent=parent)
        self._composizione_id_by_display: dict[str, str] = {}

        self.add_widget(_card_title("Avvia composizione viaggio"))

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(12)

        self._select_composizione = Select(placeholder="Seleziona composizione")
        self._select_composizione.setFixedWidth(220)
        filter_row.addWidget(self._select_composizione)

        self._date_field = DateFilterField()
        self._date_field.valueChanged.connect(lambda qdate: self.dataChanged.emit(qdate.toPython()))
        filter_row.addWidget(self._date_field)

        self._avvia_button = Button(ButtonVariant.PRIMARY, "Avvia composizione")
        self._avvia_button.clicked.connect(self._on_avvia_clicked)
        filter_row.addWidget(self._avvia_button)

        filter_row.addStretch(1)
        self.content_layout.addLayout(filter_row)

        self._alert_label = QLabel()
        alert_font = QFont("Inter")
        alert_font.setWeight(QFont.Weight(500))
        alert_font.setPixelSize(12)
        self._alert_label.setFont(alert_font)
        self._alert_label.setStyleSheet(f"color: {ALERT_COLOR}; background: transparent;")
        self._alert_label.hide()
        self.add_widget(self._alert_label)

    def _on_avvia_clicked(self) -> None:
        display = self._select_composizione.value()
        composizione_id = self._composizione_id_by_display.get(display) if display else None
        if composizione_id is not None:
            self.avviaRequested.emit(composizione_id, self._date_field.value().toPython())

    def data_selezionata(self) -> date:
        return self._date_field.value().toPython()

    def set_composizioni_disponibili(self, composizioni: list[tuple[str, str]]) -> None:
        """`composizioni`: lista di (composizione_id, "Composizione: #N")."""
        self._composizione_id_by_display = {display: cid for cid, display in composizioni}
        self._select_composizione.set_options(list(self._composizione_id_by_display.keys()))

    def show_alert(self, messaggio: str) -> None:
        self._alert_label.setText(f"⚠  {messaggio}")
        self._alert_label.show()

    def hide_alert(self) -> None:
        self._alert_label.hide()
