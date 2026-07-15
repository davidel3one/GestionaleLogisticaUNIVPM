"""Helper condiviso tra le pagine per i modali a griglia 2 colonne (fonte: mockup Sketch - ogni
modale "Aggiungi"/"Modifica" ispezionato finora usa questa stessa griglia)."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget

RIGA_SPACING = 16


def riga_2_colonne(sinistra: QWidget, destra: QWidget | None) -> QHBoxLayout:
    """Una riga del modale con 2 campi affiancati, stessa larghezza. `destra=None` per l'ultima
    riga quando il mockup lascia la seconda colonna vuota."""
    riga = QHBoxLayout()
    riga.setSpacing(RIGA_SPACING)
    riga.addWidget(sinistra, 1)
    if destra is not None:
        riga.addWidget(destra, 1)
    else:
        riga.addStretch(1)
    return riga
