"""Componente AuthLogo: logo LogiPlan riusabile nelle schermate di autenticazione (Login,
Registrazione, Conferma OTP) — stessi token del tassello logo della Sidebar, verificati
identici via Sketch (tassello 28x28 radius8 bg #2563C9 + icona 'route' bianca 16px, testo
'LogiPlan' Inter 17px/Medium #163A6B). Riusa l'helper e i token della Sidebar invece di
ridefinirli, qui disposti in una riga centrata sopra il form invece che nella logo row laterale.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gestionale_logistica.gui.components.sidebar import (
    APP_NAME_COLOR,
    _build_logo_badge,
    _make_font,
)

GAP = 8


class AuthLogo(QWidget):
    """Tassello logo + 'LogiPlan', centrato orizzontalmente."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(_build_logo_badge())

        name = QLabel("LogiPlan")
        name.setFont(_make_font(17, 500))
        name.setStyleSheet(f"color: {APP_NAME_COLOR}; background: transparent;")
        layout.addWidget(name)
