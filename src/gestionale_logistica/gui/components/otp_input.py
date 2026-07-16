"""Componente OtpInput: 6 caselle per il codice di conferma email (fonte: mockup Sketch,
artboard "Conferma OTP"). Chrome della singola casella riusa i token di TextField/Select
(bg/bordo/radius) da `form_field.py`; testo Inter 20px/Medium(500) #2E2E2E (misurato).

Le larghezze delle 6 caselle nel mockup sono leggermente incoerenti tra loro (37/37/30/30/30/30
px, probabile artefatto di auto-layout) - dimensione uniforme scelta in implementazione
(44x42px), non una misura pixel-precisa. Comportamento (avanzamento automatico alla digitazione,
backspace torna alla casella precedente, incolla distribuisce le cifre) non e' verificabile in
un mockup statico - comportamento standard atteso per un input OTP, analogo a "click sul
backdrop chiude" gia' documentato per Modal."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from gestionale_logistica.gui.components.form_field import FIELD_BG, FIELD_BORDER, FIELD_RADIUS

FONT_FAMILY = "Inter"
BOX_WIDTH = 44
BOX_HEIGHT = 42
GAP = 12
TEXT_COLOR = "#2E2E2E"
FOCUS_BORDER = "#2563C9"


class _OtpBox(QLineEdit):
    backspaceOnEmpty = Signal()
    pasted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMaxLength(1)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(BOX_WIDTH, BOX_HEIGHT)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(20)
        self.setFont(font)
        self._apply_style(FIELD_BORDER)
        self.textChanged.connect(self._strip_non_digit)

    def _apply_style(self, border_color: str) -> None:
        self.setStyleSheet(
            f"QLineEdit {{ background-color: {FIELD_BG}; border: 1px solid {border_color};"
            f" border-radius: {FIELD_RADIUS}px; color: {TEXT_COLOR}; }}"
        )

    def focusInEvent(self, event) -> None:
        self._apply_style(FOCUS_BORDER)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self._apply_style(FIELD_BORDER)
        super().focusOutEvent(event)

    def _strip_non_digit(self, text: str) -> None:
        if text and not text.isdigit():
            self.setText("")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Backspace and not self.text():
            self.backspaceOnEmpty.emit()
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:
        digits = "".join(ch for ch in source.text() if ch.isdigit())
        if len(digits) > 1:
            self.pasted.emit(digits)
        else:
            super().insertFromMimeData(source)


class OtpInput(QWidget):
    """N caselle per un codice numerico (default 6). API uniforme agli altri campi di form:
    `value()`/`set_value()`/`valueChanged`."""

    valueChanged = Signal(str)

    def __init__(self, length: int = 6, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._length = length
        self._boxes: list[_OtpBox] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for index in range(length):
            box = _OtpBox(self)
            box.textEdited.connect(lambda text, i=index: self._on_box_edited(i, text))
            box.backspaceOnEmpty.connect(lambda i=index: self._focus_previous(i))
            box.pasted.connect(lambda text, i=index: self._distribute(i, text))
            self._boxes.append(box)
            layout.addWidget(box)

    def value(self) -> str:
        return "".join(box.text() for box in self._boxes)

    def set_value(self, value: str) -> None:
        digits = [ch for ch in value if ch.isdigit()][: self._length]
        for index, box in enumerate(self._boxes):
            box.blockSignals(True)
            box.setText(digits[index] if index < len(digits) else "")
            box.blockSignals(False)
        self.valueChanged.emit(self.value())

    def clear(self) -> None:
        self.set_value("")
        if self._boxes:
            self._boxes[0].setFocus()

    def _on_box_edited(self, index: int, text: str) -> None:
        if text and index + 1 < self._length:
            self._boxes[index + 1].setFocus()
            self._boxes[index + 1].selectAll()
        self.valueChanged.emit(self.value())

    def _focus_previous(self, index: int) -> None:
        if index > 0:
            self._boxes[index - 1].setFocus()
            self._boxes[index - 1].selectAll()

    def _distribute(self, start_index: int, digits: str) -> None:
        last_filled = start_index - 1
        for offset, digit in enumerate(digits):
            i = start_index + offset
            if i >= self._length:
                break
            self._boxes[i].blockSignals(True)
            self._boxes[i].setText(digit)
            self._boxes[i].blockSignals(False)
            last_filled = i
        next_index = min(last_filled + 1, self._length - 1)
        self._boxes[next_index].setFocus()
        self._boxes[next_index].selectAll()
        self.valueChanged.emit(self.value())
