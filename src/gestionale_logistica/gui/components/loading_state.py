"""Stato di caricamento: spinner + titolo (+ sottotitolo) centrati.

Stessa struttura/token di `EmptyState` (icona + titolo centrati H/V) con lo spinner animato al
posto dell'icona statica - placeholder da mostrare al posto di una tabella/lista mentre i dati
sono in caricamento (non presente nel mockup Sketch, che non modella stati di caricamento
asincrono: si riutilizzano gli stessi colori/dimensioni di `EmptyState` per restare coerenti
con lo stile esistente)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from gestionale_logistica.gui.components.empty_state import (
    ICON_SIZE,
    ICON_TITLE_GAP,
    SUBTITLE_COLOR,
    SUBTITLE_SIZE,
    SUBTITLE_WEIGHT,
    TITLE_COLOR,
    TITLE_SIZE,
    TITLE_SUBTITLE_GAP,
    TITLE_WEIGHT,
    build_centered_label,
)
from gestionale_logistica.gui.components.spinner import Spinner


class LoadingState(QWidget):
    """Spinner + titolo (+ sottotitolo opzionale), centrati H e V."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        layout.addWidget(Spinner(size=ICON_SIZE), alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(ICON_TITLE_GAP)
        layout.addWidget(
            build_centered_label(title, TITLE_COLOR, TITLE_SIZE, TITLE_WEIGHT, self),
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        if subtitle:
            layout.addSpacing(TITLE_SUBTITLE_GAP)
            layout.addWidget(
                build_centered_label(subtitle, SUBTITLE_COLOR, SUBTITLE_SIZE, SUBTITLE_WEIGHT, self),
                alignment=Qt.AlignmentFlag.AlignHCenter,
            )

        layout.addStretch(1)
