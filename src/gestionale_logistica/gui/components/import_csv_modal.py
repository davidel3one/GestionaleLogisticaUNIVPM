"""ImportCsvModal: flusso a 2 passi "Importa CSV" (RF9) — seleziona file poi anteprima/conferma
(fonte: mockup Sketch, artboard "Ordini — Importa CSV — Seleziona file/Risultato (modale)").

Condiviso tra Dashboard e pagina Ordini (stesso identico modale, non ritagliato su una pagina
sola) — vive in `gui/components/`, non in `gui/dashboard/components/`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gestionale_logistica.gui.components.button import Button, ButtonVariant
from gestionale_logistica.gui.components.dropzone import Dropzone
from gestionale_logistica.gui.components.form_field import EditableSelect
from gestionale_logistica.gui.components.modal import Modal
from gestionale_logistica.gui.components.scroll_style import MINIMAL_SCROLLBAR_QSS
from gestionale_logistica.gui.components.table import ColumnDef, ColumnType, Table
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica

_HINT_COLOR = "#9AA1AA"
_HINT_TEXT = 'Formato richiesto: ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia (separatore ";")'

# (sfondo, testo) — stessi valori di IconChipVariant.RED / IconChipVariant.GREEN in icon_chip.py,
# dichiarati qui invece di importarli per non legare Table (che usa la tupla in ordine bg,testo)
# alla tupla (icona,sfondo) di IconChipVariant.
_BADGE_VALIDE = ("#DFF5E5", "#1E8E3E")
_BADGE_SCARTATE = ("#FBE4E1", "#C0392B")
_MOTIVO_ROSSO = ("#FBE4E1", "#C0392B")
# Le uniche 6 stringhe che _prepara_ordini_da_file puo' produrre come ErroreImport.messaggio:
# tutte in rosso uniforme nel mockup (nessuna differenziazione per motivo).
_MOTIVI_CONOSCIUTI = [
    "ID duplicato",
    "Peso non valido",
    "Volume non valido",
    "Categoria non valida",
    "Indirizzo non valido",
    "Provincia mancante",
]

DISCARDED_TABLE_MAX_HEIGHT = 220


def _modal_title() -> str:
    return "Importa CSV"


def _summary_badge(text: str, colors: tuple[str, str]) -> QLabel:
    bg, fg = colors
    label = QLabel(text)
    font = QFont("Inter")
    font.setWeight(QFont.Weight(600))
    font.setPixelSize(12)
    label.setFont(font)
    label.setStyleSheet(
        f"background-color: {bg}; color: {fg}; border-radius: 7px; padding: 4px 12px;"
    )
    return label


class ImportCsvModal(QObject):
    """Orchestratore del flusso a 2 passi. Non e' un widget: costruisce Modal distinti per
    ciascun passo (il footer di `Modal` e' fisso alla costruzione, nessuna API per sostituirlo
    a runtime — comporre due Modal in sequenza e' piu' semplice che combattere quel vincolo)."""

    importCompleted = Signal(int)

    def __init__(
        self,
        parent_widget: QWidget,
        gestore: GestoreLogistica | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._parent_widget = parent_widget
        self._gestore = gestore or GestoreLogistica()
        self._modal: Modal | None = None

    def show(self) -> None:
        self._mostra_step_seleziona_file()

    def _chiudi(self) -> None:
        if self._modal is not None:
            self._modal.close()
            self._modal = None

    def _mostra_step_seleziona_file(self) -> None:
        annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        carica = Button(ButtonVariant.PRIMARY, "Carica")
        carica.setEnabled(False)

        modal = Modal(_modal_title(), width=900, footer_buttons=[annulla, carica])

        dropzone = Dropzone(
            heading="Trascina qui il file CSV o clicca per selezionarlo",
            file_filter="File ordini (*.csv *.xlsx)",
            dialog_title="Seleziona file ordini",
        )
        modal.add_widget(dropzone)

        negozio_field = EditableSelect(
            "Negozio partner",
            self._gestore.elenco_negozi_partner(),
            placeholder="Scegli o scrivi un nuovo negozio",
        )
        modal.add_widget(negozio_field)

        hint = QLabel(_HINT_TEXT)
        hint_font = QFont("Inter")
        hint_font.setWeight(QFont.Weight(500))
        hint_font.setPixelSize(12)
        hint.setFont(hint_font)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {_HINT_COLOR}; background: transparent;")
        modal.add_widget(hint)

        stato = {"percorso": None}

        def _aggiorna_carica_abilitato() -> None:
            carica.setEnabled(stato["percorso"] is not None and bool(negozio_field.value()))

        def _on_file_selezionato(percorso: Path) -> None:
            stato["percorso"] = percorso
            _aggiorna_carica_abilitato()

        dropzone.fileSelected.connect(_on_file_selezionato)
        negozio_field.valueChanged.connect(lambda _: _aggiorna_carica_abilitato())
        annulla.clicked.connect(self._chiudi)
        carica.clicked.connect(lambda: self._on_carica(stato["percorso"], negozio_field.value()))

        self._modal = modal
        modal.closed.connect(self._on_modal_closed)
        modal.show_over(self._parent_widget)

    def _on_modal_closed(self) -> None:
        self._modal = None

    def _on_carica(self, percorso: Path | None, negozio_partner: str) -> None:
        if percorso is None or not negozio_partner:
            return
        anteprima = self._gestore.anteprima_import_ordini(percorso, negozio_partner)
        self._chiudi()
        self._mostra_step_risultato(percorso, negozio_partner, anteprima)

    def _mostra_step_risultato(self, percorso: Path, negozio_partner: str, anteprima) -> None:
        annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        n_valide = anteprima.righe_valide
        importa = Button(ButtonVariant.PRIMARY, f"Importa {n_valide} ordini")
        importa.setEnabled(n_valide > 0)

        modal = Modal(_modal_title(), width=900, footer_buttons=[annulla, importa])

        righe_rilevate = anteprima.righe_valide + len(anteprima.errori)
        riepilogo = QLabel(f"{percorso.name}  ·  {righe_rilevate} righe rilevate")
        riepilogo_font = QFont("Inter")
        riepilogo_font.setWeight(QFont.Weight(500))
        riepilogo_font.setPixelSize(13)
        riepilogo.setFont(riepilogo_font)
        riepilogo.setStyleSheet("color: #5B6472; background: transparent;")
        modal.add_widget(riepilogo)

        badges_row = QHBoxLayout()
        badges_row.setSpacing(10)
        badges_row.addWidget(_summary_badge(f"{n_valide} righe valide", _BADGE_VALIDE))
        badges_row.addWidget(_summary_badge(f"{len(anteprima.errori)} righe scartate", _BADGE_SCARTATE))
        badges_row.addStretch(1)
        modal.content_layout.addLayout(badges_row)

        if anteprima.errori:
            tabella = Table(
                [
                    ColumnDef(key="id_ordine", label="Righe scartate", column_type=ColumnType.LINK, stretch=2),
                    ColumnDef(key="cliente", label="Cliente", stretch=2),
                    ColumnDef(
                        key="motivo",
                        label="Motivo",
                        column_type=ColumnType.STATUS_BADGE,
                        status_colors={motivo: _MOTIVO_ROSSO for motivo in _MOTIVI_CONOSCIUTI},
                        stretch=2,
                    ),
                ],
                show_footer=False,
            )
            tabella.set_rows(
                [
                    {
                        "id_ordine": errore.id_ordine or "—",
                        "cliente": errore.cliente or "—",
                        "motivo": errore.messaggio,
                    }
                    for errore in anteprima.errori
                ]
            )

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(DISCARDED_TABLE_MAX_HEIGHT)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setStyleSheet(
                f"QScrollArea {{ background: transparent; border: none; }} {MINIMAL_SCROLLBAR_QSS}"
            )
            scroll.setWidget(tabella)
            modal.add_widget(scroll)

        annulla.clicked.connect(self._chiudi)
        importa.clicked.connect(lambda: self._on_importa(percorso, negozio_partner))

        self._modal = modal
        modal.closed.connect(self._on_modal_closed)
        modal.show_over(self._parent_widget)

    def _on_importa(self, percorso: Path, negozio_partner: str) -> None:
        risultato = self._gestore.importa_ordini(percorso, negozio_partner)
        self._chiudi()
        self.importCompleted.emit(risultato.ordini_creati)
