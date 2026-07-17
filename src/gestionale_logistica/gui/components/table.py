"""Componente Table riusabile: tabella dati con colonne configurabili (fonte: mockup Sketch, gui-design.sketch).

La tabella non ordina né pagina i dati da sola: emette segnali (`sortRequested`,
`pageChanged`) e chi la usa esegue una nuova query e ripassa righe/paginazione
aggiornate con `set_rows`/`set_pagination`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QEvent, QEventLoop, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gestionale_logistica.gui.components.icons import load_lucide_icon
from gestionale_logistica.gui.components.progress_bar import ProgressBar
from gestionale_logistica.gui.components.scroll_style import MINIMAL_SCROLLBAR_QSS
from gestionale_logistica.gui.components.tooltip import Popover

TOOLTIP_GAP = 6

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
CAPACITY_BAR_TRACK_COLOR = "#EAEAEA"
CAPACITY_BAR_WIDTH = 70
CAPACITY_BAR_HEIGHT = 6
# Soglie misurate sul mockup ("Proposed Trips Table"): 30/45/68% -> blu, 82% -> ambra, 91% -> rosso.
# Il mockup non mostra i valori esatti di soglia (solo questi 5 campioni): 80/90 sono i numeri
# tondi più plausibili tra 68→82 e 82→91 - dichiarato, non misurato pixel-per-pixel.
CAPACITY_BAR_COLOR_NORMAL = "#3D9BE9"
CAPACITY_BAR_COLOR_WARNING = "#B45309"
CAPACITY_BAR_COLOR_CRITICAL = "#C0392B"
CAPACITY_BAR_WARNING_THRESHOLD = 80
CAPACITY_BAR_CRITICAL_THRESHOLD = 90


def _capacity_bar_color(percent: float) -> str:
    if percent >= CAPACITY_BAR_CRITICAL_THRESHOLD:
        return CAPACITY_BAR_COLOR_CRITICAL
    if percent >= CAPACITY_BAR_WARNING_THRESHOLD:
        return CAPACITY_BAR_COLOR_WARNING
    return CAPACITY_BAR_COLOR_NORMAL

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
    CAPACITY_BAR = "capacity_bar"
    ACTIONS = "actions"


class TextEmphasis(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass
class RowAction:
    """Una singola azione della colonna `actions`: icona Lucide + callback(riga), oppure (se
    `is_switch=True`) uno switch on/off al posto dell'icona - stesso `callback(riga)` invocato
    ad ogni toggle, senza distinguere la direzione: e' compito del chiamante decidere cosa fare
    guardando lo stato corrente della riga (stesso principio gia' usato dalle azioni "matita" che
    invertono stato senza un parametro esplicito)."""

    icon_name: str = ""
    callback: Callable[[dict], None] | None = None
    color: str = TEXT_SECONDARY_COLOR
    tooltip: str | None = None
    predicate: Callable[[dict], bool] | None = None
    """Se impostato, l'azione compare solo per le righe per cui predicate(riga) e' True
    (es. un'icona "ripristina" visibile solo per righe con stato "Cessato"/"Dismesso", o
    "Annulla viaggio" nascosta per righe gia' Completato/Annullato)."""
    is_switch: bool = False
    switch_value: Callable[[dict], bool] | None = None
    """Richiesto se `is_switch=True`: legge lo stato corrente (on/off) dalla riga."""


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
    on_click: Callable[[dict], None] | None = None
    """Solo per ColumnType.LINK: se impostato, il valore diventa cliccabile (cursore a mano) e
    invoca on_click(row) al click - altrimenti resta solo visivo (stile link, nessuna interazione)."""


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
            # hide() subito: deleteLater() e' differita al prossimo giro di event loop, e un
            # widget rimosso dal layout con takeAt() resta visibile alla sua ultima geometria
            # finche' non viene nascosto o distrutto - senza hide() le vecchie righe restano
            # a schermo, sovrapposte alle nuove appena aggiunte nello stesso layout (stesso bug
            # gia' risolto in ManualeTab._clear_composizione_container).
            widget.hide()
            widget.deleteLater()


def _add_column_widget(layout: QHBoxLayout, widget: QWidget, column: ColumnDef) -> None:
    """Aggiunge `widget` a `layout` con la geometria di `column`.

    Usata sia per l'header sia per le righe dati: stessi width/stretch per
    colonna garantiscono che le colonne restino allineate tra header e righe.
    """
    if column.width is not None:
        widget.setFixedWidth(column.width)
        layout.addWidget(widget, 0, _CELL_ALIGNMENT)
    elif isinstance(widget, _ElidingLabel):
        # Nessun alignment qui (a differenza del ramo sotto): con un alignment esplicito Qt
        # non ridimensiona mai il widget alla larghezza reale della cella, lo lascia alla sua
        # sizeHint - per una label che deve troncarsi con l'ellissi questo significa non sapere
        # mai quanto spazio ha davvero (l'ellissi o non scatta mai, o scatta solo per caso a
        # schermo intero). L'allineamento verticale lo fa la label stessa via setAlignment.
        layout.addWidget(widget, column.stretch)
    else:
        layout.addWidget(widget, column.stretch, _CELL_ALIGNMENT)


def _build_divider() -> QFrame:
    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background-color: {DIVIDER_COLOR}; border: none;")
    return divider


def _build_text_label(text: str, emphasis: TextEmphasis) -> QLabel:
    # _ElidingLabel (non una QLabel semplice): tronca con ellissi e mostra il testo completo in
    # un Popover al passaggio del mouse, stesso trattamento gia' usato dalla colonna LINK (es.
    # "ID" in Viaggi) - richiesto esplicitamente anche per colonne TEXT come "Indirizzo" in
    # Ordini, che su schermi stretti sconfinavano invece di troncarsi.
    label = _ElidingLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(500))
    font.setPixelSize(13)
    label.setFont(font)
    color = TEXT_PRIMARY_COLOR if emphasis == TextEmphasis.PRIMARY else TEXT_SECONDARY_COLOR
    label.setStyleSheet(f"color: {color};")
    return label


class _ElidingLabel(QLabel):
    """QLabel che tronca il testo con ellissi quando supera la larghezza assegnata dalla cella
    (invece di sconfinare nella colonna successiva) - ricalcolato ad ogni resize perche' la
    larghezza reale della cella si conosce solo a layout fatto (colonne a `stretch`, non a
    `width` fisso: la stessa Table resa piu' stretta rifa' l'ellissi da sola).

    Il testo completo compare al passaggio del mouse in un `Popover` (stesso componente
    riusato da `Tooltip`, non il tooltip nativo del sistema operativo) solo quando il testo
    e' davvero troncato - altrimenti l'hover non mostra nulla."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(_CELL_ALIGNMENT)
        self._full_text = text
        self._truncated = False
        self._popover: Popover | None = None

    def sizeHint(self) -> QSize:
        # Larghezza 0: altrimenti Qt userebbe la larghezza del testo COMPLETO (non ancora
        # troncato) come sizeHint, e il layout a `stretch` non riuscirebbe mai a restringere
        # la cella sotto quella soglia in una finestra piccola/non massimizzata - la colonna
        # avrebbe continuato a sconfinare esattamente come prima di questo fix.
        return QSize(0, super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def resizeEvent(self, event) -> None:  # noqa: N802 (override Qt)
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width()
        )
        self.blockSignals(True)
        super().setText(elided)
        self.blockSignals(False)
        self._truncated = elided != self._full_text

    def enterEvent(self, event: QEvent) -> None:
        if self._truncated:
            self._popover = Popover(self._full_text)
            self._popover.adjustSize()
            point = QPoint(0, self.height() + TOOLTIP_GAP)
            self._popover.move(self.mapToGlobal(point))
            self._popover.show()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if self._popover is not None:
            self._popover.hide()
            self._popover.deleteLater()
            self._popover = None
        super().leaveEvent(event)


class _ClickableLabel(_ElidingLabel):
    """QLabel che tronca con ellissi (vedi `_ElidingLabel`) ed emette `clicked` al click
    sinistro - usata per le colonne LINK con `on_click`."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _build_link_label(text: str, clickable: bool = False) -> QLabel:
    label = _ClickableLabel(text) if clickable else _ElidingLabel(text)
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(13)
    label.setFont(font)
    label.setStyleSheet(f"color: {LINK_COLOR};")
    if clickable:
        label.setCursor(Qt.CursorShape.PointingHandCursor)
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


SWITCH_WIDTH = 36
SWITCH_HEIGHT = 20
SWITCH_PADDING = 2
SWITCH_KNOB_SIZE = SWITCH_HEIGHT - 2 * SWITCH_PADDING
SWITCH_ON_COLOR = QColor("#2563C9")
SWITCH_OFF_COLOR = QColor("#D6DEE8")
SWITCH_KNOB_COLOR = QColor("#FFFFFF")


class _Switch(QAbstractButton):
    """Switch on/off compatto per la colonna Azioni (non nel mockup - introdotto su richiesta
    esplicita dell'utente al posto della matita su Camion). Nessun supporto QSS per un cursore
    circolare che scorre dentro una pillola, quindi disegnato a mano in `paintEvent` - stesso
    principio gia' usato per `Modal`/`Tooltip` (angoli arrotondati non ottenibili in modo
    affidabile via QSS + QGraphicsEffect)."""

    def __init__(self, checked: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(SWITCH_WIDTH, SWITCH_HEIGHT)

    def paintEvent(self, event) -> None:  # noqa: ARG002 (firma richiesta da Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(SWITCH_ON_COLOR if self.isChecked() else SWITCH_OFF_COLOR)
        painter.drawRoundedRect(self.rect(), SWITCH_HEIGHT / 2, SWITCH_HEIGHT / 2)
        knob_x = (
            self.width() - SWITCH_PADDING - SWITCH_KNOB_SIZE if self.isChecked() else SWITCH_PADDING
        )
        painter.setBrush(SWITCH_KNOB_COLOR)
        painter.drawEllipse(knob_x, SWITCH_PADDING, SWITCH_KNOB_SIZE, SWITCH_KNOB_SIZE)


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


def _build_capacity_bar_cell(value) -> QWidget:
    percent = float(value) if value is not None else 0.0
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    label = QLabel(f"{round(percent)}%")
    font = QFont(FONT_FAMILY)
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(11)
    label.setFont(font)
    label.setStyleSheet(f"color: {HEADER_TEXT_COLOR}; background: transparent;")
    layout.addWidget(label)
    layout.addWidget(
        ProgressBar(
            percent,
            width=CAPACITY_BAR_WIDTH,
            height=CAPACITY_BAR_HEIGHT,
            fill_color=_capacity_bar_color(percent),
        )
    )
    return container


def _build_actions_cell(actions: list[RowAction], row: dict) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for action in actions:
        if action.predicate is not None and not action.predicate(row):
            continue
        if action.is_switch:
            switch = _Switch(bool(action.switch_value(row)) if action.switch_value else False, container)
            switch.toggled.connect(lambda checked=False, cb=action.callback, r=row: cb(r))
            if action.tooltip:
                switch.setToolTip(action.tooltip)
            layout.addWidget(switch)
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
        label = _build_link_label("" if value is None else str(value), clickable=column.on_click is not None)
        if column.on_click is not None:
            label.clicked.connect(lambda cb=column.on_click, r=row: cb(r))
        return label

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

    if column.column_type == ColumnType.CAPACITY_BAR:
        return _build_capacity_bar_cell(row.get(column.key))

    if column.column_type == ColumnType.ACTIONS:
        return _build_actions_cell(column.actions, row)

    raise ValueError(f"Tipo colonna non supportato: {column.column_type}")


class _RowsScrollArea(QScrollArea):
    """QScrollArea che riporta come sizeHint l'altezza reale del contenuto (somma delle righe),
    non il default generico di QScrollArea (~288px fissi, cfr. Qt) che sottostimerebbe la Table
    ogni volta che nessuno le impone un vincolo di altezza (es. dentro un Modal senza stretch) -
    senza questo fix la Table si "accorciava" da sola in quei casi, tagliando l'ultima riga sotto
    il footer. Quando invece un genitore le assegna meno spazio del sizeHint (stretch di pagina,
    o un maxHeight esplicito) la QScrollArea scorre comunque normalmente: sizeHint è solo la
    dimensione desiderata, non un vincolo."""

    def sizeHint(self) -> QSize:
        content = self.widget()
        if content is None:
            return super().sizeHint()
        frame = 2 * self.frameWidth()
        return QSize(content.sizeHint().width() + frame, content.sizeHint().height() + frame)


class Table(QFrame):
    """Tabella dati riusabile: colonne configurabili, ordinamento/paginazione server-side.

    La Table non ordina né pagina da sola: `sortRequested`/`pageChanged` notificano
    l'intenzione dell'utente, chi la usa esegue una nuova query e ripassa righe
    aggiornate con `set_rows`/`set_pagination`.
    """

    sortRequested = Signal(str, bool)  # colonna, ascending
    pageChanged = Signal(int)  # pagina 1-based richiesta

    def __init__(
        self, columns: list[ColumnDef], show_footer: bool = True, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        if not columns:
            raise ValueError("Table richiede almeno una colonna.")

        self._columns = columns
        self._sort_column: str | None = None
        self._sort_ascending = True
        self._current_page = 1
        self._total_items = 0
        self._page_size = 1
        self._show_footer = show_footer

        self._apply_style()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        outer_layout.addWidget(self._build_header())
        outer_layout.addWidget(_build_divider())

        self._rows_container = QWidget(self)
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)

        # Righe in una QScrollArea interna (stesso stile MINIMAL_SCROLLBAR_QSS gia' usato per
        # "Attivita' recente" della Dashboard e per le mini-tabelle nei modali) cosi' che sia la
        # Table stessa a scorrere in verticale quando il numero di righe eccede lo spazio
        # disponibile - header e footer (paginazione) restano sempre visibili, fuori dall'area
        # che scorre. Stretch 1 nell'outer_layout: quando la pagina che la ospita le da' piu'
        # spazio del minimo (vedi `layout.addWidget(self._tabella, 1)` nelle pagine), e' l'area
        # scorrevole a occupare lo spazio in piu', non le righe a stirarsi.
        self._rows_scroll = _RowsScrollArea(self)
        self._rows_scroll.setWidgetResizable(True)
        self._rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._rows_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._rows_scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }} {MINIMAL_SCROLLBAR_QSS}"
        )
        self._rows_scroll.viewport().setStyleSheet("background: transparent;")
        self._rows_scroll.setWidget(self._rows_container)
        outer_layout.addWidget(self._rows_scroll, 1)

        if self._show_footer:
            outer_layout.addWidget(self._build_footer())

    def set_rows(self, rows: list[dict]) -> None:
        # Fix (2026-07-16): le celle senza `width` fisso (colonne a `stretch`) prendono la loro
        # larghezza reale solo quando Qt elabora l'evento di layout accodato alla reparent/resize -
        # se la Table e' gia' visibile (es. ricreata da zero e appena inserita nel layout della
        # pagina) quell'evento resta in coda per un giro di event loop: nel frattempo quelle celle
        # vengono dipinte alla larghezza di default di un widget appena creato (~640px in questo
        # ambiente), poi "saltano" alla larghezza corretta - il bug delle colonne stretchate che
        # si normalizzano dopo la comparsa. setUpdatesEnabled(False) sopprime il repaint di quel
        # frame intermedio sbagliato, e un giro esplicito di processEvents() forza subito il
        # ricalcolo del layout prima di riabilitare il repaint - verificato: senza, le larghezze
        # restano sbagliate anche dopo layout().activate()/invalidate() espliciti, si sistemano
        # solo al giro di event loop successivo. Nota: subito dopo un `addWidget` in un layout
        # gia' visibile, `isVisible()` e' ancora False (Qt non propaga il flag "visibile"
        # sincronamente) anche se la table e' gia' agganciata a una finestra a schermo - il
        # controllo giusto e' "ha un genitore reale in una finestra mostrata", non `isVisible()`.
        needs_fix = self.parentWidget() is not None and self.window().isVisible()
        if needs_fix:
            self.setUpdatesEnabled(False)

        _clear_layout(self._rows_layout)
        for index, row in enumerate(rows):
            if index > 0:
                self._rows_layout.addWidget(_build_divider())
            self._rows_layout.addWidget(self._build_row_widget(row))
        # Fix (2026-07-15): senza uno stretch finale, quando Table e' piu' alta del contenuto
        # (poche righe, spazio residuo nel QVBoxLayout della pagina) il layout distribuiva lo
        # spazio in eccesso tra le righe (a dimensione fissa) invece di lasciarlo sotto l'ultima -
        # risultato: righe con un vuoto enorme tra loro invece che compatte in cima alla tabella.
        self._rows_layout.addStretch(1)

        if needs_fix:
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            self.setUpdatesEnabled(True)

    def set_pagination(self, current_page: int, total_items: int, page_size: int) -> None:
        self._current_page = current_page
        self._total_items = total_items
        self._page_size = page_size
        if self._show_footer:
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
