"""DateFilterField: campo data compatto senza label sopra, per righe Filtri ("Data: 19/07/2026" +
chevron). Diverso da `DatePicker` (che ha sempre una label sopra): riusa la stessa chrome flat
(`_DateEditBox`) di `form_field.py`, non la ridefinisce.

Nato pagina-specifico dentro `gui/pianificazione/components/` per il Filter Bar di Pianificazione —
Automatica; promosso qui (2026-07-16) non appena una seconda occasione di riuso identica si è
presentata (righe Filtri di Ordini/Dipendenti/Camion/Squadre/Viaggi, stesso bug di allineamento
verificato dal pdf di riferimento: il campo Data lì aveva sempre una label sopra, disallineato
rispetto a Cerca/Stato/Tipo che non ne hanno una), stesso percorso già fatto per `ProgressBar`.
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
