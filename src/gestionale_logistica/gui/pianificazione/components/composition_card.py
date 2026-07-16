"""CompositionCard: card "Viaggio in composizione", condivisa da Pianificazione — Manuale
(RF10/RF11) e Assistita (RF12) — stesso layout misurato su entrambi i mockup Sketch: intestazione
(squadra/camion/partenza), barre Peso/Volume, elenco ordini nel viaggio (con badge categoria),
sezione "Aggiungi ordine" (tabella paginata di candidati, non la select del mockup — vedi nota
su `_CANDIDATI_TABLE_COLUMNS`), messaggio di rifiuto opzionale (RF11), footer Annulla/Chiudi
viaggio.

`add_extra_section(widget)` inserisce un blocco aggiuntivo prima della sezione "Aggiungi ordine"
(usato da Assistita per il blocco "Suggerimento automatico" — non ancora costruito)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    Card,
    ColumnDef,
    ColumnType,
    ProgressBar,
    RowAction,
    Table,
    Tooltip,
    load_lucide_icon,
)
from gestionale_logistica.gui.components.table import FOOTER_HEIGHT, HEADER_HEIGHT, ROW_HEIGHT

TITLE_COLOR = "#2E2E2E"
HINT_COLOR = "#9AA1AA"
LABEL_COLOR = "#8A93A0"
DIVIDER_COLOR = "#EDEFF3"
ALERT_COLOR = "#C0392B"
BAR_WIDTH = 350
BAR_HEIGHT = 7
BAR_COLUMN_GAP = 46

# Icona "annulla inserimento" (undo-2) per le righe di "Ordini nel viaggio": non nel mockup
# (nessun frame la disegna), stessa dimensione/stile dei bottoni icona di Table (28px, sfondo
# trasparente, icona 14px) per coerenza con il resto dell'app - colore HINT_COLOR (gia' usato
# per peso/volume nella stessa riga) invece di un colore nuovo.
RIMUOVI_ICON_SIZE = 14
RIMUOVI_BUTTON_SIZE = 28

# Pagina della tabella "Aggiungi ordine": stessa dimensione di SuggestionSection.PAGE_SIZE per
# coerenza fra le tabelle di Pianificazione (Manuale/Assistita).
PAGE_SIZE = 20

# Altezza minima della tabella "Aggiungi ordine": ~4 righe visibili prima di dover scorrere
# (nel suo QScrollArea interno) invece di affidarsi solo allo spazio residuo della Card, che il
# suo stesso addStretch(1) finale assorbe per intero prima che arrivi qui sotto.
_CANDIDATI_TABLE_MIN_VISIBLE_ROWS = 4
CANDIDATI_TABLE_MIN_HEIGHT = (
    HEADER_HEIGHT + _CANDIDATI_TABLE_MIN_VISIBLE_ROWS * ROW_HEIGHT + FOOTER_HEIGHT
)

# "Standard" raggruppa le categorie senza vincoli particolari (BordoStrada/InstallazioneSemplice
# AlPiano/Incasso): il mockup mostra solo badge "Standard"/"Big" — nessuna istanza con
# "CertificazioneGas", ma la stessa logica va applicata per coerenza (uniche 2 categorie con un
# vincolo di idoneità in RF11, verifica_idoneita_risorsa).
CATEGORIA_BADGE_LABELS = {
    "BordoStrada": "Standard",
    "InstallazioneSempliceAlPiano": "Standard",
    "Incasso": "Standard",
    "Big": "Big",
    "CertificazioneGas": "Certificazione Gas",
}
CATEGORIA_BADGE_COLORS = {
    "Standard": ("#EAEAEA", "#2E2E2E"),
    "Big": ("#FEF3C7", "#B45309"),
    "Certificazione Gas": ("#FEF3C7", "#B45309"),
}

# Colonne fisse della tabella "Aggiungi ordine" (deviazione dal mockup, che mostra una select a
# singola riga di testo: concordata con l'utente 2026-07-16 per lo stesso motivo già affrontato in
# SuggestionSection — una select con centinaia di candidati senza peso/volume/categoria è difficile
# da scandagliare). Stesse colonne di SuggestionSection.TABLE_COLUMNS, duplicate qui invece che
# condivise (stesso principio di CATEGORIA_BADGE_COLORS, vedi componenti-gui.md).
_CANDIDATI_TABLE_COLUMNS = [
    ColumnDef(key="ordine_id", label="Ordine", width=90),
    ColumnDef(key="cliente", label="Cliente", stretch=2),
    ColumnDef(key="peso", label="Peso", width=90),
    ColumnDef(key="volume", label="Volume", width=90),
    ColumnDef(
        key="categoria_label",
        label="Categoria",
        column_type=ColumnType.STATUS_BADGE,
        status_colors=CATEGORIA_BADGE_COLORS,
        width=140,
    ),
]
_CANDIDATI_ACTION_COLUMN_WIDTH = 40


def _heading(text: str = "") -> QLabel:
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(15)
    label.setFont(font)
    label.setStyleSheet(f"color: {TITLE_COLOR}; background: transparent;")
    return label


def _hint(text: str = "") -> QLabel:
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(500))
    font.setPixelSize(12)
    label.setFont(font)
    label.setStyleSheet(f"color: {HINT_COLOR}; background: transparent;")
    return label


def _bar_label(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(11)
    label.setFont(font)
    label.setStyleSheet(f"color: {LABEL_COLOR}; background: transparent;")
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {DIVIDER_COLOR}; border: none;")
    return line


def _badge(categoria_label: str) -> QLabel:
    bg, color = CATEGORIA_BADGE_COLORS.get(categoria_label, CATEGORIA_BADGE_COLORS["Standard"])
    label = QLabel(categoria_label)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(12)
    label.setFont(font)
    label.setFixedWidth(90)
    label.setStyleSheet(
        f"background-color: {bg}; color: {color}; border-radius: 7px; padding: 4px 12px;"
    )
    return label


def _build_rimuovi_ordine_button(parent: QWidget) -> QPushButton:
    button = QPushButton(parent)
    button.setFixedSize(RIMUOVI_BUTTON_SIZE, RIMUOVI_BUTTON_SIZE)
    button.setIcon(load_lucide_icon("undo-2", HINT_COLOR, RIMUOVI_ICON_SIZE))
    button.setIconSize(QSize(RIMUOVI_ICON_SIZE, RIMUOVI_ICON_SIZE))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip("Annulla inserimento")
    button.setStyleSheet(
        """
        QPushButton {
            background-color: transparent;
            border: none;
        }
        """
    )
    return button


@dataclass
class RigaOrdineComposizione:
    ordine_id: str
    cliente: str
    peso: float
    volume: float
    categoria_label: str  # vedi CATEGORIA_BADGE_LABELS


class CompositionCard(Card):
    aggiungiOrdineRequested = Signal(str)  # ordine_id scelto nella tabella "Aggiungi ordine"
    rimuoviOrdineRequested = Signal(str)  # ordine_id da rimuovere da "Ordini nel viaggio"
    annullaRequested = Signal()
    chiudiViaggioRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(padding_horizontal=24, padding_vertical=20, spacing=16, parent=parent)
        self._mostra_rimuovi_ordine = False

        self._title = _heading()
        self.content_layout.addWidget(self._title)

        self._info_hint = _hint()
        self.content_layout.addWidget(self._info_hint)

        bars_row = QHBoxLayout()
        bars_row.setContentsMargins(0, 0, 0, 0)
        bars_row.setSpacing(BAR_COLUMN_GAP)
        self._peso_label, self._peso_bar, peso_column = self._build_bar_column()
        self._volume_label, self._volume_bar, volume_column = self._build_bar_column()
        bars_row.addWidget(peso_column)
        bars_row.addWidget(volume_column)
        bars_row.addStretch(1)
        self.content_layout.addLayout(bars_row)

        self._ordini_heading = _heading()
        self.content_layout.addWidget(self._ordini_heading)

        self._ordini_layout = QVBoxLayout()
        self._ordini_layout.setContentsMargins(0, 0, 0, 0)
        self._ordini_layout.setSpacing(0)
        self.content_layout.addLayout(self._ordini_layout)

        self.content_layout.addWidget(_divider())

        self._extra_sections_layout = QVBoxLayout()
        self._extra_sections_layout.setContentsMargins(0, 0, 0, 0)
        self._extra_sections_layout.setSpacing(16)
        self.content_layout.addLayout(self._extra_sections_layout)

        self._manual_add_section = QWidget()
        manual_add_layout = QVBoxLayout(self._manual_add_section)
        manual_add_layout.setContentsMargins(0, 0, 0, 0)
        manual_add_layout.setSpacing(16)

        aggiungi_heading_row = QHBoxLayout()
        aggiungi_heading_row.setContentsMargins(0, 0, 0, 0)
        aggiungi_heading_row.setSpacing(8)
        aggiungi_heading_row.addWidget(_heading("Aggiungi ordine"))
        aggiungi_heading_row.addWidget(
            Tooltip("Nessun algoritmo qui: scegli tu ogni ordine da aggiungere.")
        )
        aggiungi_heading_row.addStretch(1)
        manual_add_layout.addLayout(aggiungi_heading_row)

        self._ordini_disponibili: list[RigaOrdineComposizione] = []
        self._pagina_disponibili = 1

        colonne_disponibili = [
            *_CANDIDATI_TABLE_COLUMNS,
            ColumnDef(
                key="azioni",
                label="",
                column_type=ColumnType.ACTIONS,
                width=_CANDIDATI_ACTION_COLUMN_WIDTH,
                actions=[RowAction("circle-plus", self._on_aggiungi_clicked, tooltip="Aggiungi al viaggio")],
            ),
        ]
        self._tabella_disponibili = Table(colonne_disponibili)
        self._tabella_disponibili.pageChanged.connect(self._on_pagina_disponibili_cambiata)
        self._tabella_disponibili.hide()
        # Table ora scorre al suo interno con una QScrollArea (per le pagine Ordini/Viaggi/
        # Dipendenti, dove riceve tutta l'altezza residua della pagina). Qui invece e' annidata
        # dentro la Card, il cui content_layout termina con un addStretch(1) che assorbe lui
        # stesso tutto lo spazio verticale in eccesso (apposta, per tenere compatte le sezioni
        # sopra) - senza un minimo esplicito la QScrollArea interna collassava a un'altezza
        # minima anche con una sola riga candidata: il bottone "Aggiungi" restava tecnicamente
        # cliccabile ma la tabella appariva come una striscia quasi invisibile (causa reale del
        # bottone "che non funziona più" - non lo stretch mancante, provato e verificato che da
        # solo non basta). Altezza minima per ~4 righe visibili prima di dover scorrere.
        self._tabella_disponibili.setMinimumHeight(CANDIDATI_TABLE_MIN_HEIGHT)
        manual_add_layout.addWidget(self._tabella_disponibili, 1)

        self._disponibili_hint = _hint("Nessun ordine disponibile da aggiungere")
        self._disponibili_hint.hide()
        manual_add_layout.addWidget(self._disponibili_hint)

        self.content_layout.addWidget(self._manual_add_section)

        self._alert_label = QLabel()
        alert_font = QFont("Inter")
        alert_font.setWeight(QFont.Weight(500))
        alert_font.setPixelSize(12)
        self._alert_label.setFont(alert_font)
        self._alert_label.setStyleSheet(f"color: {ALERT_COLOR}; background: transparent;")
        self._alert_label.hide()
        self.content_layout.addWidget(self._alert_label)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(8)
        footer_row.addStretch(1)
        self._annulla_button = Button(ButtonVariant.SECONDARY, "Annulla")
        self._annulla_button.clicked.connect(self.annullaRequested)
        footer_row.addWidget(self._annulla_button)
        self._chiudi_button = Button(ButtonVariant.PRIMARY, "Chiudi viaggio")
        self._chiudi_button.clicked.connect(self.chiudiViaggioRequested)
        footer_row.addWidget(self._chiudi_button)
        self.content_layout.addLayout(footer_row)

        # Senza uno stretch finale, se la card riceve più altezza di quella richiesta dal
        # contenuto (es. finestra grande), QVBoxLayout la distribuisce tra le label (size policy
        # Preferred, non Fixed) invece di lasciarle compatte in cima - stesso principio già
        # documentato per il pannello "Attività recente" della Dashboard.
        self.content_layout.addStretch(1)

    def _build_bar_column(self) -> tuple[QLabel, ProgressBar, QWidget]:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = _bar_label("")
        layout.addWidget(label)
        bar = ProgressBar(0.0, width=BAR_WIDTH, height=BAR_HEIGHT)
        layout.addWidget(bar)
        return label, bar, column

    def _on_aggiungi_clicked(self, row: dict) -> None:
        self.aggiungiOrdineRequested.emit(row["ordine_id"])

    def _on_pagina_disponibili_cambiata(self, page: int) -> None:
        self._pagina_disponibili = page
        self._render_pagina_disponibili()

    def _render_pagina_disponibili(self) -> None:
        self._tabella_disponibili.setVisible(bool(self._ordini_disponibili))
        self._disponibili_hint.setVisible(not self._ordini_disponibili)
        inizio = (self._pagina_disponibili - 1) * PAGE_SIZE
        pagina = self._ordini_disponibili[inizio : inizio + PAGE_SIZE]
        self._tabella_disponibili.set_rows(
            [
                {
                    "ordine_id": riga.ordine_id,
                    "cliente": riga.cliente,
                    "peso": f"{riga.peso:g} kg",
                    "volume": f"{riga.volume:g} m³",
                    "categoria_label": riga.categoria_label,
                }
                for riga in pagina
            ]
        )
        self._tabella_disponibili.set_pagination(
            self._pagina_disponibili, len(self._ordini_disponibili), PAGE_SIZE
        )

    # -- API pubblica --------------------------------------------------------------------

    def set_intestazione(
        self,
        squadra_label: str,
        camion_label: str,
        partenza_label: str,
        peso_occupato: float,
        peso_massimo: float,
        volume_occupato: float,
        volume_massimo: float,
    ) -> None:
        self._title.setText(f"Viaggio in composizione — Squadra {squadra_label}")
        self._info_hint.setText(f"{camion_label} · Partenza {partenza_label}")

        self._peso_label.setText(f"Peso: {peso_occupato:g} / {peso_massimo:g} kg")
        self._volume_label.setText(f"Volume: {volume_occupato:g} / {volume_massimo:g} m³")
        peso_pct = (peso_occupato / peso_massimo * 100) if peso_massimo else 0.0
        volume_pct = (volume_occupato / volume_massimo * 100) if volume_massimo else 0.0
        self._peso_bar.set_percent(peso_pct)
        self._volume_bar.set_percent(volume_pct)

    def set_ordini(self, righe: list[RigaOrdineComposizione]) -> None:
        self._ordini_heading.setText(f"Ordini nel viaggio ({len(righe)})")
        while self._ordini_layout.count():
            item = self._ordini_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for indice, riga in enumerate(righe):
            if indice > 0:
                self._ordini_layout.addWidget(_divider())
            self._ordini_layout.addWidget(self._build_ordine_row(riga))

    def _build_ordine_row(self, riga: RigaOrdineComposizione) -> QWidget:
        row = QWidget()
        row.setFixedHeight(40)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        id_cliente = QLabel(f"{riga.ordine_id}  ·  {riga.cliente}")
        id_font = QFont("Inter")
        id_font.setWeight(QFont.Weight(500))
        id_font.setPixelSize(12)
        id_cliente.setFont(id_font)
        id_cliente.setStyleSheet(f"color: {TITLE_COLOR}; background: transparent;")
        layout.addWidget(id_cliente, 1)

        peso_volume = _hint(f"{riga.peso:g} kg · {riga.volume:g} m³")
        peso_volume.setFixedWidth(140)
        layout.addWidget(peso_volume)

        layout.addWidget(_badge(riga.categoria_label))

        if self._mostra_rimuovi_ordine:
            rimuovi_button = _build_rimuovi_ordine_button(row)
            rimuovi_button.clicked.connect(
                lambda checked=False, ordine_id=riga.ordine_id: self.rimuoviOrdineRequested.emit(ordine_id)
            )
            layout.addWidget(rimuovi_button)

        return row

    def set_rimozione_ordine_abilitata(self, abilitata: bool) -> None:
        """Mostra un'icona "annulla inserimento" (freccia indietro `undo-2`) per ogni riga di
        "Ordini nel viaggio", che rimuove l'ordine dal viaggio in composizione — non nel mockup
        (nessun frame la disegna): richiesta esplicita dell'utente, solo per Manuale (Assistita
        non la abilita, resta con la sola vista di sola lettura gia' esistente)."""
        self._mostra_rimuovi_ordine = abilitata

    def set_ordini_disponibili(self, ordini: list[RigaOrdineComposizione]) -> None:
        """`ordini`: righe candidate per la tabella "Aggiungi ordine"."""
        self._ordini_disponibili = ordini
        self._pagina_disponibili = 1
        self._render_pagina_disponibili()

    def show_alert(self, messaggio: str) -> None:
        self._alert_label.setText(f"⚠  {messaggio}")
        self._alert_label.show()

    def hide_alert(self) -> None:
        self._alert_label.hide()

    def add_extra_section(self, widget: QWidget) -> None:
        self._extra_sections_layout.addWidget(widget)

    def set_manual_add_visible(self, visible: bool) -> None:
        """Assistita (RF12) nasconde del tutto la sezione "Aggiungi ordine" manuale: il mockup
        la sostituisce con `SuggestionSection` (via `add_extra_section`), non la affianca."""
        self._manual_add_section.setVisible(visible)
