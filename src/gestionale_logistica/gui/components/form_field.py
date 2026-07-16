"""Campi di input di un form: TextField, Select, BooleanToggle, DatePicker, MultiSelect
(fonte: mockup Sketch, gui-design.sketch).

Chrome condivisa da TextField e Select verificata sullo stato chiuso nel mockup: la lista
opzioni del Select aperto e gli stati hover/pressed dei pill del toggle non sono disegnati
in nessun frame — vedi le note "non verificato nel mockup" sotto ogni classe interessata.
DatePicker e MultiSelect erano fuori scope nella prima iterazione (nessun frame del mockup
li disegna aperti); la forma con cui sono implementati ora è una decisione esplicita
dell'utente, non un'assunzione — vedi le rispettive docstring.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"

LABEL_COLOR = "#8A93A0"
LABEL_GAP = 4

FIELD_BG = "#FFFFFF"
FIELD_BORDER = "#E5EAF0"
FIELD_RADIUS = 9
FIELD_HEIGHT = 34
FIELD_PADDING_H = 12
FIELD_TEXT_COLOR = "#5B6472"

CHEVRON_SIZE = 14
SELECT_GAP = 8
# Riuso del grigio chiaro già usato per lo sfondo dei bottoni SECONDARY (button.py),
# invece di introdurre un nuovo token per lo stato hover/selezionato del popup.
POPUP_HOVER_BG = "#F7F9FC"

TOGGLE_PILL_WIDTH = 56
TOGGLE_PILL_HEIGHT = 34
TOGGLE_GAP = 8
TOGGLE_RADIUS = 17
# Invertito su richiesta esplicita dell'utente (2026-07-15): il grigio rappresenta lo stato
# selezionato, non il contrario come misurato inizialmente dal mockup.
TOGGLE_SELECTED_BG = "#EAEAEA"
TOGGLE_SELECTED_BORDER = "#E5EAF0"
TOGGLE_UNSELECTED_BG = "#FFFFFF"


def _field_font() -> QFont:
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(500))
    font.setPixelSize(13)
    return font


def _build_label(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(11)
    label.setFont(font)
    label.setStyleSheet(f"color: {LABEL_COLOR};")
    return label


def _build_popup_chrome(parent: QWidget) -> QMenu:
    """`QMenu` vuoto con la chrome condivisa dai popup Select/MultiSelect (non nel mockup).

    Fattorizzato per non duplicare lo stesso QSS in entrambi i componenti: chi lo chiama
    riempie il menu con `QAction` semplici (Select) o `QWidgetAction`+`QCheckBox` (MultiSelect).
    """
    menu = QMenu(parent)
    menu.setFont(_field_font())
    menu.setStyleSheet(
        f"""
        QMenu {{
            background-color: {FIELD_BG};
            border: 1px solid {FIELD_BORDER};
            border-radius: {FIELD_RADIUS}px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 8px 12px;
            border-radius: 6px;
            color: {FIELD_TEXT_COLOR};
        }}
        QMenu::item:selected {{
            background-color: {POPUP_HOVER_BG};
        }}
        """
    )
    return menu


class TextField(QWidget):
    """Campo di testo con label sopra: `QLineEdit` con la chrome del mockup."""

    valueChanged = Signal(str)

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        password: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LABEL_GAP)
        layout.addWidget(_build_label(label))

        self._input = QLineEdit(self)
        self._input.setPlaceholderText(placeholder)
        self._input.setFixedHeight(FIELD_HEIGHT)
        self._input.setFont(_field_font())
        if password:
            self._input.setEchoMode(QLineEdit.EchoMode.Password)

        # Il mockup non differenzia il colore del testo digitato da quello del placeholder:
        # senza questo, Qt schiarirebbe automaticamente il placeholder rispetto al testo
        # (il ruolo QPalette::PlaceholderText non è coperto dalla proprietà "color" del QSS).
        palette = self._input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(FIELD_TEXT_COLOR))
        self._input.setPalette(palette)
        self._input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {FIELD_BG};
                border: 1px solid {FIELD_BORDER};
                border-radius: {FIELD_RADIUS}px;
                padding: 0 {FIELD_PADDING_H}px;
                color: {FIELD_TEXT_COLOR};
            }}
            """
        )
        layout.addWidget(self._input)

        self._input.textChanged.connect(self.valueChanged)

    def value(self) -> str:
        return self._input.text()

    def set_value(self, value: str) -> None:
        self._input.setText(value)


class _SelectBox(QPushButton):
    """Chrome del campo Select (stato chiuso): testo a sinistra + chevron a destra."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(FIELD_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(FIELD_PADDING_H, 0, FIELD_PADDING_H, 0)
        layout.setSpacing(SELECT_GAP)

        self.text_label = QLabel(self)
        self.text_label.setFont(_field_font())
        self.text_label.setStyleSheet(f"color: {FIELD_TEXT_COLOR};")
        layout.addWidget(self.text_label, 1)

        icon_label = QLabel(self)
        icon = load_lucide_icon("chevron-down", FIELD_TEXT_COLOR, CHEVRON_SIZE)
        icon_label.setPixmap(icon.pixmap(QSize(CHEVRON_SIZE, CHEVRON_SIZE)))
        icon_label.setFixedSize(CHEVRON_SIZE, CHEVRON_SIZE)
        layout.addWidget(icon_label)

        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {FIELD_BG};
                border: 1px solid {FIELD_BORDER};
                border-radius: {FIELD_RADIUS}px;
                text-align: left;
                padding: 0px;
            }}
            """
        )

    def sizeHint(self) -> QSize:
        # QPushButton calcola da solo un sizeHint basato su text()/icon() (entrambi vuoti qui,
        # il contenuto vero vive nel layout interno) - senza questo override risulta troppo
        # piccolo e comprime testo/icona sotto la larghezza reale, stesso motivo per cui Button
        # ha lo stesso override (vedi button.py).
        return self.layout().sizeHint()


class Select(QWidget):
    """Campo a scelta singola con label sopra: chrome chiusa dal mockup, popup non verificato nel mockup.

    Il mockup mostra solo lo stato chiuso del Select: nessun frame disegna la lista opzioni
    aperta. Il popup qui sotto (`QMenu`) riusa gli stessi token del resto della libreria
    (sfondo bianco, bordo `#E5EAF0`, radius 9px, hover `#F7F9FC`) per coerenza visiva, non
    perché misurato — scelta di implementazione, analoga a come `Modal` documenta
    "click sul backdrop chiude" come comportamento standard non nel mockup statico.
    """

    valueChanged = Signal(str)

    def __init__(
        self,
        label: str,
        options: list[str],
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._options = list(options)
        self._placeholder = placeholder
        self._value: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LABEL_GAP)
        layout.addWidget(_build_label(label))

        self._box = _SelectBox(self)
        self._box.text_label.setText(placeholder)
        self._box.clicked.connect(self._open_popup)
        layout.addWidget(self._box)

    def _build_menu(self) -> QMenu:
        menu = _build_popup_chrome(self)
        for option in self._options:
            action = menu.addAction(option)
            action.triggered.connect(lambda checked=False, opt=option: self.set_value(opt))
        return menu

    def _open_popup(self) -> None:
        menu = self._build_menu()
        menu.exec(self._box.mapToGlobal(QPoint(0, self._box.height())))

    def value(self) -> str | None:
        return self._value

    def set_value(self, value: str | None) -> None:
        self._value = value
        self._box.text_label.setText(value if value is not None else self._placeholder)
        self.valueChanged.emit(value or "")


class _TogglePill(QPushButton):
    """Singola pillola del toggle booleano, 56x34px, capsula (radius = altezza/2)."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(TOGGLE_PILL_WIDTH, TOGGLE_PILL_HEIGHT)
        self.setFont(_field_font())
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        background = TOGGLE_SELECTED_BG if selected else TOGGLE_UNSELECTED_BG
        border = f"1px solid {TOGGLE_SELECTED_BORDER}" if selected else "none"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {background};
                border: {border};
                border-radius: {TOGGLE_RADIUS}px;
                color: {FIELD_TEXT_COLOR};
            }}
            """
        )


class BooleanToggle(QWidget):
    """Toggle booleano Sì/No con label sopra: due pillole affiancate, etichette fisse."""

    valueChanged = Signal(bool)

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LABEL_GAP)
        layout.addWidget(_build_label(label))

        pills_row = QHBoxLayout()
        pills_row.setContentsMargins(0, 0, 0, 0)
        pills_row.setSpacing(TOGGLE_GAP)

        self._yes_pill = _TogglePill("Sì", self)
        self._no_pill = _TogglePill("No", self)
        self._yes_pill.clicked.connect(lambda: self.set_value(True))
        self._no_pill.clicked.connect(lambda: self.set_value(False))
        pills_row.addWidget(self._yes_pill)
        pills_row.addWidget(self._no_pill)
        pills_row.addStretch(1)

        layout.addLayout(pills_row)
        self._refresh()

    def _refresh(self) -> None:
        self._yes_pill.set_selected(self._value)
        self._no_pill.set_selected(not self._value)

    def value(self) -> bool:
        return self._value

    def set_value(self, value: bool) -> None:
        self._value = bool(value)
        self._refresh()
        self.valueChanged.emit(self._value)


DATE_FORMAT = "dd/MM/yyyy"


class DatePicker(QWidget):
    """Campo data con label sopra: `QDateEdit` nativo Qt, solo il chrome chiuso ristilizzato.

    Decisione esplicita dell'utente (non un'assunzione): il calendario a comparsa
    (`calendarPopup=True`) resta quello standard di Qt/OS, non ridisegnato — nessuno stile
    del sistema di design applicato al popup del calendario stesso, solo al campo chiuso.
    """

    valueChanged = Signal(QDate)

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LABEL_GAP)
        layout.addWidget(_build_label(label))

        self._input = QDateEdit(self)
        self._input.setCalendarPopup(True)
        self._input.setDisplayFormat(DATE_FORMAT)
        self._input.setDate(QDate.currentDate())
        self._input.setFixedHeight(FIELD_HEIGHT)
        self._input.setFont(_field_font())
        self._input.setStyleSheet(
            f"""
            QDateEdit {{
                background-color: {FIELD_BG};
                border: 1px solid {FIELD_BORDER};
                border-radius: {FIELD_RADIUS}px;
                padding: 0 {FIELD_PADDING_H}px;
                color: {FIELD_TEXT_COLOR};
            }}
            """
        )
        layout.addWidget(self._input)

        self._input.dateChanged.connect(self.valueChanged)

    def value(self) -> QDate:
        return self._input.date()

    def set_value(self, value: QDate) -> None:
        self._input.setDate(value)


class MultiSelect(QWidget):
    """Campo a scelta multipla con label sopra: stessa chrome chiusa di `Select`, popup con checkbox.

    Nessun frame del mockup disegna un multiselect aperto. Pattern (testo riassuntivo nel
    campo chiuso + popup con `QCheckBox` per opzione) deciso esplicitamente dall'utente,
    non un'assunzione di questa implementazione. Il popup riusa `_build_popup_chrome`,
    la stessa chrome già scritta per `Select` (nessuna logica di popup duplicata).
    """

    valueChanged = Signal(list)

    def __init__(
        self,
        label: str,
        options: list[str],
        placeholder: str = "Seleziona...",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._options = list(options)
        self._placeholder = placeholder
        self._values: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LABEL_GAP)
        layout.addWidget(_build_label(label))

        self._box = _SelectBox(self)
        self._box.clicked.connect(self._open_popup)
        layout.addWidget(self._box)
        self._refresh_summary()

    def _build_menu(self) -> QMenu:
        menu = _build_popup_chrome(self)
        for option in self._options:
            checkbox = QCheckBox(option, menu)
            checkbox.setFont(_field_font())
            checkbox.setChecked(option in self._values)
            checkbox.setStyleSheet(
                f"""
                QCheckBox {{
                    padding: 8px 12px;
                    border-radius: 6px;
                    color: {FIELD_TEXT_COLOR};
                }}
                QCheckBox:hover {{
                    background-color: {POPUP_HOVER_BG};
                }}
                """
            )
            checkbox.toggled.connect(lambda checked, opt=option: self._toggle(opt, checked))
            action = QWidgetAction(menu)
            action.setDefaultWidget(checkbox)
            menu.addAction(action)
        return menu

    def _open_popup(self) -> None:
        menu = self._build_menu()
        menu.exec(self._box.mapToGlobal(QPoint(0, self._box.height())))

    def _toggle(self, option: str, checked: bool) -> None:
        if checked and option not in self._values:
            self._values.append(option)
        elif not checked and option in self._values:
            self._values.remove(option)
        self._refresh_summary()
        self.valueChanged.emit(list(self._values))

    def _refresh_summary(self) -> None:
        count = len(self._values)
        if count == 0:
            text = self._placeholder
        elif count == 1:
            text = self._values[0]
        else:
            text = f"{count} selezionati"
        self._box.text_label.setText(text)

    def value(self) -> list[str]:
        return list(self._values)

    def set_value(self, values: list[str]) -> None:
        self._values = [v for v in values if v in self._options]
        self._refresh_summary()
        self.valueChanged.emit(list(self._values))


class EditableSelect(QWidget):
    """Campo con label sopra: sceglie tra `options` o digita un valore nuovo non in elenco.

    Non nel mockup (es. "Negozio partner" del modale Importa CSV, che non mostra questo campo):
    decisione esplicita dell'utente di poter sia scegliere un valore già visto sia crearne uno
    al volo. `QComboBox` nativo Qt (editabile) invece del popup custom di `Select`/`QMenu`, che
    non supporta l'editing testuale - solo il chrome del campo chiuso replica gli stessi token
    (`FIELD_BG`/`FIELD_BORDER`/`FIELD_RADIUS`/`FIELD_HEIGHT`) del resto della libreria; la
    freccia del drop-down resta quella nativa Qt, non il `chevron-down` vettoriale degli altri
    campi (avrebbe richiesto un asset statico su disco per il QSS `image: url()`, fuori scope
    per un campo che il mockup non disegna nemmeno)."""

    valueChanged = Signal(str)

    def __init__(
        self,
        label: str,
        options: list[str],
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LABEL_GAP)
        layout.addWidget(_build_label(label))

        self._combo = QComboBox(self)
        self._combo.setEditable(True)
        self._combo.addItems(options)
        self._combo.setCurrentIndex(-1)
        if placeholder:
            self._combo.lineEdit().setPlaceholderText(placeholder)
        self._combo.setFixedHeight(FIELD_HEIGHT)
        self._combo.setFont(_field_font())
        self._combo.lineEdit().setStyleSheet(
            f"background: transparent; border: none; padding: 0; color: {FIELD_TEXT_COLOR};"
        )
        self._combo.setStyleSheet(
            f"""
            QComboBox {{
                background-color: {FIELD_BG};
                border: 1px solid {FIELD_BORDER};
                border-radius: {FIELD_RADIUS}px;
                padding: 0 {FIELD_PADDING_H}px;
                color: {FIELD_TEXT_COLOR};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {FIELD_BG};
                border: 1px solid {FIELD_BORDER};
                border-radius: {FIELD_RADIUS}px;
                selection-background-color: {POPUP_HOVER_BG};
                color: {FIELD_TEXT_COLOR};
                padding: 4px;
            }}
            """
        )
        layout.addWidget(self._combo)

        self._combo.currentTextChanged.connect(self.valueChanged)

    def value(self) -> str:
        return self._combo.currentText().strip()

    def set_value(self, value: str) -> None:
        index = self._combo.findText(value)
        if index >= 0:
            self._combo.setCurrentIndex(index)
        else:
            self._combo.setEditText(value)
