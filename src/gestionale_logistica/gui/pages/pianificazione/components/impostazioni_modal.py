"""ImpostazioniPianificazioneModal: vincoli di RF10-13 configurabili dall'admin (tempi di
installazione per categoria, ore di lavoro per viaggio, ora di partenza default) — non
disegnato nel mockup Sketch (nessun frame lo modella), costruito riusando `Modal`/`TextField`
con lo stesso stile/layout a 2 colonne osservato in "Camion — Aggiungi (modale)".

Orchestratore `QObject` come `ImportCsvModal`: costruisce un singolo `Modal`, non e' esso
stesso un widget.
"""

from __future__ import annotations

from datetime import time

from PySide6.QtCore import QObject, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QHBoxLayout, QWidget

from gestionale_logistica.database.enums import CategoriaConsegna
from gestionale_logistica.gui.components.button import Button, ButtonVariant
from gestionale_logistica.gui.components.form_field import TextField
from gestionale_logistica.gui.components.modal import CONTENT_PADDING_TOP, Modal
from gestionale_logistica.ottimizzazione.gestore_configurazione import GestoreConfigurazione

_LABEL_CATEGORIA = {
    CategoriaConsegna.BORDO_STRADA: "Bordo strada (min)",
    CategoriaConsegna.INSTALLAZIONE_SEMPLICE_AL_PIANO: "Installazione al piano (min)",
    CategoriaConsegna.INCASSO: "Incasso (min)",
    CategoriaConsegna.BIG: "Big (min)",
    CategoriaConsegna.CERTIFICAZIONE_GAS: "Certificazione gas (min)",
}

_ROW_GAP = 16
# Modal impone 0px di padding inferiore sul content per design (componenti-gui.md): il
# chiamante deve aggiungerlo. Simmetrico a CONTENT_PADDING_TOP per bilanciare il gap
# titolo->primo campo osservato in alto.
_SPAZIO_FINALE_CONTENUTO = CONTENT_PADDING_TOP

_REGEX_ORA = QRegularExpression(r"^([01]\d|2[0-3]):[0-5]\d$")
_REGEX_ORE_LAVORO = QRegularExpression(r"^([1-9]|1\d|2[0-4])(\.\d)?$")
_REGEX_MINUTI = QRegularExpression(r"^[1-9]\d{0,2}$")


def _validator_ora() -> QRegularExpressionValidator:
    return QRegularExpressionValidator(_REGEX_ORA)


def _validator_ore_lavoro() -> QRegularExpressionValidator:
    return QRegularExpressionValidator(_REGEX_ORE_LAVORO)


def _validator_minuti() -> QRegularExpressionValidator:
    return QRegularExpressionValidator(_REGEX_MINUTI)


def _riga(*campi: TextField) -> QWidget:
    riga = QWidget()
    layout = QHBoxLayout(riga)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(_ROW_GAP)
    for campo in campi:
        layout.addWidget(campo, 1)
    return riga


class ImpostazioniPianificazioneModal(QObject):
    """Mostra il modale precompilato con la configurazione corrente; Salva valida e persiste
    tramite `GestoreConfigurazione`, chiude il modale."""

    def __init__(
        self,
        parent_widget: QWidget,
        gestore: GestoreConfigurazione | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._parent_widget = parent_widget
        self._gestore = gestore or GestoreConfigurazione()
        self._modal: Modal | None = None

    def show(self) -> None:
        configurazione = self._gestore.leggi()

        annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        salva = Button(ButtonVariant.PRIMARY, "Salva")

        modal = Modal(
            "Impostazioni pianificazione",
            subtitle="Vincoli usati dall'ottimizzatore per calcolare orari e durata dei viaggi",
            width=560,
            footer_buttons=[annulla, salva],
        )

        campo_ora = TextField(
            "Ora di partenza default", placeholder="es. 08:00", validator=_validator_ora()
        )
        campo_ora.set_value(configurazione.ora_partenza_default.strftime("%H:%M"))

        campo_ore_lavoro = TextField(
            "Ore di lavoro per viaggio", placeholder="es. 8", validator=_validator_ore_lavoro()
        )
        campo_ore_lavoro.set_value(_formatta_ore(configurazione.ore_lavoro))

        modal.add_widget(_riga(campo_ora, campo_ore_lavoro))

        campi_categoria: dict[CategoriaConsegna, TextField] = {}
        categorie = list(CategoriaConsegna)
        for indice in range(0, len(categorie), 2):
            coppia = categorie[indice : indice + 2]
            campi_riga = []
            for categoria in coppia:
                campo = TextField(
                    _LABEL_CATEGORIA[categoria], placeholder="es. 30", validator=_validator_minuti()
                )
                campo.set_value(str(configurazione.tempi_installazione_minuti[categoria]))
                campi_categoria[categoria] = campo
                campi_riga.append(campo)
            modal.add_widget(_riga(*campi_riga))

        # Padding inferiore del content di Modal e' 0px per design (componenti-gui.md): senza
        # questo l'ultima riga toccherebbe il divider sopra Annulla/Salva.
        modal.content_layout.addSpacing(_SPAZIO_FINALE_CONTENUTO)

        def _aggiorna_salva_abilitato() -> None:
            valido = bool(_REGEX_ORA.match(campo_ora.value()).hasMatch())
            valido = valido and bool(_REGEX_ORE_LAVORO.match(campo_ore_lavoro.value()).hasMatch())
            for campo in campi_categoria.values():
                valido = valido and bool(_REGEX_MINUTI.match(campo.value()).hasMatch())
            salva.setEnabled(valido)

        campo_ora.valueChanged.connect(lambda _: _aggiorna_salva_abilitato())
        campo_ore_lavoro.valueChanged.connect(lambda _: _aggiorna_salva_abilitato())
        for campo in campi_categoria.values():
            campo.valueChanged.connect(lambda _: _aggiorna_salva_abilitato())
        _aggiorna_salva_abilitato()

        annulla.clicked.connect(self._chiudi)
        salva.clicked.connect(lambda: self._salva(campo_ora, campo_ore_lavoro, campi_categoria))

        self._modal = modal
        modal.closed.connect(self._on_modal_closed)
        modal.show_over(self._parent_widget)

    def _salva(
        self,
        campo_ora: TextField,
        campo_ore_lavoro: TextField,
        campi_categoria: dict[CategoriaConsegna, TextField],
    ) -> None:
        ore, minuti = campo_ora.value().split(":")
        self._gestore.aggiorna(
            ora_partenza_default=time(int(ore), int(minuti)),
            ore_lavoro=float(campo_ore_lavoro.value()),
            tempi_installazione_minuti={
                categoria: int(campo.value()) for categoria, campo in campi_categoria.items()
            },
        )
        self._chiudi()

    def _chiudi(self) -> None:
        if self._modal is not None:
            self._modal.close()
            self._modal = None

    def _on_modal_closed(self) -> None:
        self._modal = None


def _formatta_ore(ore: float) -> str:
    return str(int(ore)) if ore == int(ore) else str(ore)
