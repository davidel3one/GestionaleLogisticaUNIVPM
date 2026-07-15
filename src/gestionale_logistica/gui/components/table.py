"""Componente Table riusabile: tabella dati con colonne configurabili (fonte: mockup Sketch, gui-design.sketch).

La tabella non ordina né pagina i dati da sola: emette segnali (`sortRequested`,
`pageChanged`) e chi la usa esegue una nuova query e ripassa righe/paginazione
aggiornate con `set_rows`/`set_pagination`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"

HEADER_TEXT_COLOR = "#8A93A0"
DIVIDER_COLOR = "#EDEFF3"
TEXT_PRIMARY_COLOR = "#2E2E2E"
TEXT_SECONDARY_COLOR = "#5B6472"
LINK_COLOR = "#2563C9"
PAGER_ACTIVE_BG = "#2563C9"
PAGER_ACTIVE_TEXT = "#FFFFFF"
PAGER_INACTIVE_TEXT = "#5B6472"
PAGER_HOVER_BG = "#F7F9FC"  # affordance hover, non presente nel mockup statico
NEUTRAL_BADGE_COLORS = ("#EAEAEA", "#5B6472")

DEFAULT_STATUS_BADGE_COLORS: dict[str, tuple[str, str]] = {
    "Consegnato": ("#DFF5E5", "#1E8E3E"),
    "Attivo": ("#DFF5E5", "#1E8E3E"),
    "Fallito": ("#FBE4E1", "#C0392B"),
    "In consegna": ("#FEF3C7", "#B45309"),
    "Da pianificare": NEUTRAL_BADGE_COLORS,
    "Pianificato": ("#D6EAFB", "#2563C9"),
    "Proposto": ("#D6EAFB", "#2563C9"),
}

HEADER_HEIGHT = 40
ROW_HEIGHT = 52
FOOTER_HEIGHT = 48
ROW_PADDING_X = 24
COLUMN_GAP = 16
DISABLED_OPACITY = 0.45

_CELL_ALIGNMENT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


class ColumnType(str, Enum):
    TEXT = "text"
    LINK = "link"
    STATUS_BADGE = "status_badge"
    BOOLEAN_BADGE = "boolean_badge"
    ACTIONS = "actions"


class TextEmphasis(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass
class RowAction:
    """Una singola azione della colonna `actions`: icona Lucide + callback(riga)."""

    icon_name: str
    callback: Callable[[dict], None]
    color: str = TEXT_SECONDARY_COLOR
    tooltip: str | None = None
    predicate: Callable[[dict], bool] | None = None
    """Se impostato, l'azione compare solo per le righe per cui predicate(riga) e' True
    (es. un'icona "ripristina" visibile solo per righe con stato "Dismesso")."""


@dataclass
class ColumnDef:
    """Definizione di una colonna della Table."""

    key: str
    label: str
    column_type: ColumnType = ColumnType.TEXT
    sortable: bool = False
    emphasis: TextEmphasis = TextEmphasis.PRIMARY
    status_colors: dict[str, tuple[str, str]] | None = None
    true_label: str = "Sì"
    false_label: str = "No"
    actions: list[RowAction] = field(default_factory=list)
    width: int | None = None
    stretch: int = 1


def _visible_pages(current_page: int, total_pages: int) -> list[int | None]:
    """Calcola i numeri pagina da mostrare nel pager, con `None` come ellissi.

    Mostra sempre prima/ultima pagina, la pagina corrente e le sue dirette vicine;
    tronca il resto con un'ellissi (nessun limite esplicito nel mockup per un
    numero grande di pagine totali).
    """
    if total_pages <= 7:
        return list(range(1, total_pages + 1))

    keep = {1, total_pages, current_page}
    for neighbor in (current_page - 1, current_page + 1):
        if 1 <= neighbor <= total_pages:
            keep.add(neighbor)

    ordered = sorted(keep)
    result: list[int | None] = []
    previous: int | None = None
    for page in ordered:
        if previous is not None and page - previous > 1:
            result.append(None)
        result.append(page)
        previous = page
    return result


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _add_column_widget(layout: QHBoxLayout, widget: QWidget, column: ColumnDef) -> None:
    """Aggiunge `widget` a `layout` con la geometria di `column`.

    Usata sia per l'header sia per le righe dati: stessi width/stretch per
    colonna garantiscono che le colonne restino allineate tra header e righe.
    """
    if column.width is not None:
        widget.setFixedWidth(column.width)
        layout.addWidget(widget, 0, _CELL_ALIGNMENT)
    else:
        layout.addWidget(widget, column.stretch, _CELL_ALIGNMENT)


def _build_divider() -> QFrame:
    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background-color: {DIVIDER_COLOR}; border: none;")
    return divider


def _build_text_label(text: str, emphasis: TextEmphasis) -> QLabel:
    label = QLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(500))
    font.setPixelSize(13)
    label.setFont(font)
    color = TEXT_PRIMARY_COLOR if emphasis == TextEmphasis.PRIMARY else TEXT_SECONDARY_COLOR
    label.setStyleSheet(f"color: {color};")
    return label


def _build_link_label(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(13)
    label.setFont(font)
    label.setStyleSheet(f"color: {LINK_COLOR};")
    return label


def _build_badge(text: str, bg: str, color: str) -> QLabel:
    label = QLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(12)
    label.setFont(font)
    label.setStyleSheet(
        f"background-color: {bg}; color: {color}; border-radius: 7px; padding: 4px 12px;"
    )
    return label


class _IconButton(QPushButton):
    """Bottone icon-only 28x28 senza chrome visibile, usato per azioni riga e frecce pager."""

    def __init__(self, icon: QIcon, tooltip: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setIcon(icon)
        self.setIconSize(QSize(14, 14))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
            }
            """
        )

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


class _PagerButton(QPushButton):
    """Pulsante numero di pagina 28x28, pieno se attivo."""

    def __init__(self, page: int, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(str(page), parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(600))
        font.setPixelSize(13)
        self.setFont(font)
        if active:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {PAGER_ACTIVE_BG};
                    color: {PAGER_ACTIVE_TEXT};
                    border: none;
                    border-radius: 7px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    color: {PAGER_INACTIVE_TEXT};
                    border: none;
                    border-radius: 7px;
                }}
                QPushButton:hover {{
                    background-color: {PAGER_HOVER_BG};
                }}
                """
            )


def _build_ellipsis() -> QLabel:
    label = QLabel("…")
    label.setFixedSize(28, 28)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(13)
    label.setFont(font)
    label.setStyleSheet(f"color: {PAGER_INACTIVE_TEXT};")
    return label


class _HeaderCell(QWidget):
    """Cella header: etichetta maiuscola + icona di ordinamento opzionale, cliccabile se ordinabile."""

    clicked = Signal()

    def __init__(self, label: str, sortable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sortable = sortable

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        text_label = QLabel(label.upper(), self)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(600))
        font.setPixelSize(11)
        text_label.setFont(font)
        text_label.setStyleSheet(f"color: {HEADER_TEXT_COLOR};")
        layout.addWidget(text_label)

        if sortable:
            icon_label = QLabel(self)
            icon_label.setPixmap(
                load_lucide_icon("chevrons-up-down", HEADER_TEXT_COLOR, 11).pixmap(QSize(11, 11))
            )
            layout.addWidget(icon_label)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._sortable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _build_actions_cell(actions: list[RowAction], row: dict) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for action in actions:
        if action.predicate is not None and not action.predicate(row):
            continue
        icon = load_lucide_icon(action.icon_name, action.color, 14)
        button = _IconButton(icon, action.tooltip, container)
        button.clicked.connect(lambda checked=False, cb=action.callback, r=row: cb(r))
        layout.addWidget(button)
    return container


def _build_cell(column: ColumnDef, row: dict) -> QWidget:
    if column.column_type == ColumnType.TEXT:
        value = row.get(column.key, "")
        return _build_text_label("" if value is None else str(value), column.emphasis)

    if column.column_type == ColumnType.LINK:
        value = row.get(column.key, "")
        return _build_link_label("" if value is None else str(value))

    if column.column_type == ColumnType.STATUS_BADGE:
        value = row.get(column.key)
        colors = {**DEFAULT_STATUS_BADGE_COLORS, **(column.status_colors or {})}
        bg, color = colors.get(str(value), NEUTRAL_BADGE_COLORS)
        return _build_badge("" if value is None else str(value), bg, color)

    if column.column_type == ColumnType.BOOLEAN_BADGE:
        if row.get(column.key):
            bg, color = NEUTRAL_BADGE_COLORS
            return _build_badge(column.true_label, bg, color)
        return _build_text_label(column.false_label, TextEmphasis.SECONDARY)

    if column.column_type == ColumnType.ACTIONS:
        return _build_actions_cell(column.actions, row)

    raise ValueError(f"Tipo colonna non supportato: {column.column_type}")


class Table(QFrame):
    """Tabella dati riusabile: colonne configurabili, ordinamento/paginazione server-side.

    La Table non ordina né pagina da sola: `sortRequested`/`pageChanged` notificano
    l'intenzione dell'utente, chi la usa esegue una nuova query e ripassa righe
    aggiornate con `set_rows`/`set_pagination`.
    """

    sortRequested = Signal(str, bool)  # colonna, ascending
    pageChanged = Signal(int)  # pagina 1-based richiesta

    def __init__(self, columns: list[ColumnDef], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not columns:
            raise ValueError("Table richiede almeno una colonna.")

        self._columns = columns
        self._sort_column: str | None = None
        self._sort_ascending = True
        self._current_page = 1
        self._total_items = 0
        self._page_size = 1

        self._apply_style()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        outer_layout.addWidget(self._build_header())
        outer_layout.addWidget(_build_divider())

        self._rows_container = QWidget(self)
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        outer_layout.addWidget(self._rows_container)

        outer_layout.addWidget(self._build_footer())

    def set_rows(self, rows: list[dict]) -> None:
        _clear_layout(self._rows_layout)
        for index, row in enumerate(rows):
            if index > 0:
                self._rows_layout.addWidget(_build_divider())
            self._rows_layout.addWidget(self._build_row_widget(row))

    def set_pagination(self, current_page: int, total_items: int, page_size: int) -> None:
        self._current_page = current_page
        self._total_items = total_items
        self._page_size = page_size
        self._rebuild_footer()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            Table {
                background-color: #FFFFFF;
                border: none;
                border-radius: 14px;
            }
            """
        )

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        header.setFixedHeight(HEADER_HEIGHT)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(ROW_PADDING_X, 0, ROW_PADDING_X, 0)
        layout.setSpacing(COLUMN_GAP)
        for column in self._columns:
            cell = _HeaderCell(column.label, column.sortable, header)
            if column.sortable:
                cell.clicked.connect(lambda key=column.key: self._handle_sort_click(key))
            _add_column_widget(layout, cell, column)
        return header

    def _build_row_widget(self, row: dict) -> QWidget:
        row_widget = QWidget(self._rows_container)
        row_widget.setFixedHeight(ROW_HEIGHT)
        layout = QHBoxLayout(row_widget)
        layout.setContentsMargins(ROW_PADDING_X, 0, ROW_PADDING_X, 0)
        layout.setSpacing(COLUMN_GAP)
        for column in self._columns:
            cell = _build_cell(column, row)
            _add_column_widget(layout, cell, column)
        return row_widget

    def _handle_sort_click(self, key: str) -> None:
        if self._sort_column == key:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = key
            self._sort_ascending = True
        self.sortRequested.emit(key, self._sort_ascending)

    def _build_footer(self) -> QWidget:
        footer = QWidget(self)
        footer.setFixedHeight(FOOTER_HEIGHT)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(ROW_PADDING_X, 0, ROW_PADDING_X, 0)
        layout.setSpacing(0)

        self._range_label = QLabel(footer)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(13)
        self._range_label.setFont(font)
        self._range_label.setStyleSheet(f"color: {TEXT_SECONDARY_COLOR};")
        layout.addWidget(self._range_label, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        pager_widget = QWidget(footer)
        self._pager_layout = QHBoxLayout(pager_widget)
        self._pager_layout.setContentsMargins(0, 0, 0, 0)
        self._pager_layout.setSpacing(4)
        layout.addWidget(pager_widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._rebuild_footer()
        return footer

    def _rebuild_footer(self) -> None:
        self._range_label.setText(self._range_text())
        _clear_layout(self._pager_layout)

        total_pages = self._total_pages()

        prev_button = _IconButton(load_lucide_icon("chevron-left", PAGER_INACTIVE_TEXT, 14))
        prev_button.setEnabled(self._current_page > 1)
        prev_button.clicked.connect(lambda: self.pageChanged.emit(self._current_page - 1))
        self._pager_layout.addWidget(prev_button)

        for page in _visible_pages(self._current_page, total_pages):
            if page is None:
                self._pager_layout.addWidget(_build_ellipsis())
                continue
            page_button = _PagerButton(page, active=(page == self._current_page))
            page_button.clicked.connect(lambda checked=False, p=page: self.pageChanged.emit(p))
            self._pager_layout.addWidget(page_button)

        next_button = _IconButton(load_lucide_icon("chevron-right", PAGER_INACTIVE_TEXT, 14))
        next_button.setEnabled(self._current_page < total_pages)
        next_button.clicked.connect(lambda: self.pageChanged.emit(self._current_page + 1))
        self._pager_layout.addWidget(next_button)

    def _total_pages(self) -> int:
        if self._page_size <= 0 or self._total_items <= 0:
            return 1
        return max(1, -(-self._total_items // self._page_size))

    def _range_text(self) -> str:
        if self._total_items <= 0:
            return "0 / 0 righe"
        first = (self._current_page - 1) * self._page_size + 1
        last = min(self._current_page * self._page_size, self._total_items)
        return f"{first}-{last} / {self._total_items} righe"
