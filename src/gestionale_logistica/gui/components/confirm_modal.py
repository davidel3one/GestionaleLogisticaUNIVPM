"""ConfirmModal: modale di conferma generico (Annulla / azione), per operazioni che meritano un
passaggio esplicito prima di eseguirle (es. eliminare un camion/dipendente) - non nel mockup
Sketch (nessuna RF/artboard lo definisce), introdotto su richiesta esplicita dell'utente.

Riusa la stessa chrome di `Modal`, nessun token nuovo: bottone di conferma in `ButtonVariant.PRIMARY`
(blu), lo stesso usato da ogni altro modale di conferma del sito (Aggiungi/Modifica/Salva) - non un
rosso "distruttivo", che non esiste come variante nella libreria: introdurne uno solo qui sarebbe
una deviazione dallo stile già stabilito, non una scelta più coerente (regola "resta sullo stile
già costruito" per ciò che il mockup non modella)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from gestionale_logistica.gui.components.button import Button, ButtonVariant
from gestionale_logistica.gui.components.modal import Modal

FONT_FAMILY = "Inter"
MESSAGE_COLOR = "#5B6472"


class ConfirmModal(Modal):
    """`confirmed` si emette solo se l'utente clicca il bottone di conferma - il chiamante esegue
    l'azione vera e propria nello slot connesso a quel segnale, il modale si chiude da solo in
    entrambi i casi (Annulla o conferma)."""

    confirmed = Signal()

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str = "Elimina",
        cancel_label: str = "Annulla",
        parent: QWidget | None = None,
    ) -> None:
        bottone_annulla = Button(ButtonVariant.SECONDARY, cancel_label)
        bottone_conferma = Button(ButtonVariant.PRIMARY, confirm_label)
        super().__init__(
            title, width=440, footer_buttons=[bottone_annulla, bottone_conferma], parent=parent
        )

        etichetta = QLabel(message)
        etichetta.setWordWrap(True)
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(13)
        etichetta.setFont(font)
        etichetta.setStyleSheet(f"color: {MESSAGE_COLOR};")
        self.add_widget(etichetta)

        bottone_annulla.clicked.connect(self.close)
        bottone_conferma.clicked.connect(self._conferma_e_chiudi)

    def _conferma_e_chiudi(self) -> None:
        self.close()
        self.confirmed.emit()
