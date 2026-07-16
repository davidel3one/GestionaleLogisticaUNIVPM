"""DateFilterField: campo data compatto senza label sopra, per il Filter Bar di Pianificazione
— Automatica ("Data: 19/07/2026" + chevron). Diverso da `DatePicker` (che ha sempre una label
sopra): riusa la stessa chrome flat (`_DateEditBox`) di `form_field.py`, non la ridefinisce.

Pagina-specifico per ora (nessun'altra pagina con Filter Bar è ancora costruita per provarne il
riuso) — se una seconda pagina avrà bisogno dello stesso campo filtro senza label, va promosso a
`gui/components/`, seguendo lo stesso percorso già fatto per `KpiCard`→condivisione quando serve.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QWidget

from gestionale_logistica.gui.components.form_field import _DateEditBox

FIELD_WIDTH = 200
DISPLAY_FORMAT = "'Data: 'dd/MM/yyyy"


class DateFilterField(_DateEditBox):
    valueChanged = Signal(QDate)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.input.setDisplayFormat(DISPLAY_FORMAT)
        self.input.setDate(QDate.currentDate())
        self.setFixedWidth(FIELD_WIDTH)
        self.input.dateChanged.connect(self.valueChanged)

    def value(self) -> QDate:
        return self.input.date()

    def set_value(self, value: QDate) -> None:
        self.input.setDate(value)
