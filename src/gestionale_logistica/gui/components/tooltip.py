"""Componente Tooltip riusabile: icona info + popover on-hover (fonte: mockup Sketch, gui-design.sketch, istanze "Info Popover").

Widget autonomo (icona + comportamento inclusi): si affianca a una label/campo con
`layout.addWidget(Tooltip("spiegazione"))`, non richiede un widget "trigger" esterno da
decorare — è il pattern più semplice da usare nei form (es. spiegazioni RNF accanto a un
`TextField`), coerente con come gli altri componenti di questo pacchetto sono già
autosufficienti (`Button`, `Card`, ecc.).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPaintEvent, QPainter
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QWidget

from gestionale_logistica.gui.components.icons import load_lucide_icon

FONT_FAMILY = "Inter"

ICON_SIZE = 18
# Colore icona non specificato nel mockup (misurate solo forma/dimensione) — riuso del
# grigio già usato per le label dei campi (LABEL_COLOR in form_field.py), tono informativo
# attenuato invece di introdurre un colore nuovo non misurato.
ICON_COLOR = "#8A93A0"

POPOVER_BG = QColor("#EAEAEA")
POPOVER_TEXT_COLOR = "#2E2E2E"
POPOVER_RADIUS = 10
POPOVER_PADDING_H = 16
POPOVER_PADDING_V = 12
POPOVER_MIN_HEIGHT = 40
# Non misurato nel mockup: i 560px del box lì sono un artefatto di allineamento del canvas
# Sketch (il testo reale occupa 331px), non una larghezza intenzionale. Questo cap esiste
# solo per far andare a capo spiegazioni molto lunghe invece di crescere all'infinito in
# orizzontale — valore scelto, non misurato.
POPOVER_MAX_WIDTH = 320
POPOVER_SHADOW_COLOR = QColor(0, 0, 0, 38)  # #00000026
POPOVER_SHADOW_OFFSET_Y = 8
POPOVER_SHADOW_BLUR = 24

POPOVER_GAP = 10


class Popover(QLabel):
    """Popover flottante, fuori dal layout dell'applicazione (finestra top-level frameless).

    Struttura a singolo widget (non un contenitore con figlio): lo sfondo arrotondato è
    dipinto a mano in `paintEvent` invece che via QSS `background-color`/`border-radius`.
    Su questa stessa finestra, `WA_TranslucentBackground` insieme a uno sfondo QSS e al
    `QGraphicsDropShadowEffect` non dipingeva lo sfondo in modo affidabile (verificato: il
    corpo restava trasparente, il testo sembrava fluttuare su un alone rumoroso). Dipingere
    il rounded-rect direttamente con `QPainter` evita quell'interazione, mantenendo la
    struttura a widget singolo invariata.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumHeight(POPOVER_MIN_HEIGHT)

        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(12)
        self.setFont(font)

        # Word wrap attivato SOLO se il testo non ci sta su una riga sola entro
        # POPOVER_MAX_WIDTH. Con wordWrap sempre attivo, il sizeHint di una QLabel
        # word-wrap usa un'euristica interna di Qt che sceglie una wrap-width "stretta"
        # per avvicinare l'aspect ratio al golden ratio, e quella scelta resta impressa
        # nel layout del testo indipendentemente da un resize/setFixedWidth successivo:
        # per questo un ID corto come "V-STORICO-20260715-03" veniva comunque spezzato
        # dopo il primo "-" anche forzando la larghezza del widget. Disabilitare il
        # word wrap quando non serve evita del tutto quel percorso euristico.
        content_width = QFontMetrics(font).horizontalAdvance(text) + 2 * POPOVER_PADDING_H
        if content_width <= POPOVER_MAX_WIDTH:
            self.setWordWrap(False)
            self.setFixedWidth(content_width)
        else:
            self.setWordWrap(True)
            self.setFixedWidth(POPOVER_MAX_WIDTH)

        self.setStyleSheet(
            f"""
            QLabel {{
                background: transparent;
                color: {POPOVER_TEXT_COLOR};
                padding: {POPOVER_PADDING_V}px {POPOVER_PADDING_H}px;
            }}
            """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setColor(POPOVER_SHADOW_COLOR)
        shadow.setOffset(0, POPOVER_SHADOW_OFFSET_Y)
        shadow.setBlurRadius(POPOVER_SHADOW_BLUR)
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(POPOVER_BG)
        painter.drawRoundedRect(self.rect(), POPOVER_RADIUS, POPOVER_RADIUS)
        painter.end()
        super().paintEvent(event)


class Tooltip(QLabel):
    """Icona info 18x18 che mostra un popover al passaggio del mouse.

    Comportamento (non verificabile in un mockup statico, standard atteso): hover mostra
    il popover, uscita del mouse lo nasconde — stessa logica già usata per "click sul
    backdrop chiude" in `Modal`.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(ICON_SIZE, ICON_SIZE)

        icon = load_lucide_icon("info", ICON_COLOR, ICON_SIZE)
        self.setPixmap(icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)))

        self._popover = Popover(text)

    def show_popover(self) -> None:
        """Posiziona e mostra il popover a destra dell'icona, centrato verticalmente."""
        self._popover.adjustSize()
        gap_point = QPoint(
            self.width() + POPOVER_GAP,
            self.height() // 2 - self._popover.height() // 2,
        )
        self._popover.move(self.mapToGlobal(gap_point))
        self._popover.show()

    def hide_popover(self) -> None:
        self._popover.hide()

    def enterEvent(self, event: QEvent) -> None:
        self.show_popover()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.hide_popover()
        super().leaveEvent(event)
