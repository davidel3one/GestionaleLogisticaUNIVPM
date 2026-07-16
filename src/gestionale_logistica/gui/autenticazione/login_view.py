"""View Login (fonte: mockup Sketch, artboard "Login"). Nessuna sidebar: sostituisce l'intera
finestra finche' l'utente non e' autenticato."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from gestionale_logistica.gui.autenticazione._shared import (
    CONTENT_WIDTH,
    ERROR_COLOR,
    build_centered_layout,
    hint_label,
    title_label,
)
from gestionale_logistica.gui.components import AuthLogo, Button, ButtonVariant, TextField


class LoginView(QWidget):
    """Email + password + bottone Accedi + messaggio di errore (nascosto finche' non serve)."""

    submitted = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("LoginView { background-color: #FFFFFF; }")

        self.email = TextField("Email", placeholder="nome@azienda.it")
        self.password = TextField("Password", placeholder="········", password=True)
        self._button = Button(ButtonVariant.PRIMARY_LARGE, "Accedi")
        self._error = hint_label("", color=ERROR_COLOR)
        self._error.hide()

        column = QWidget()
        column.setFixedWidth(CONTENT_WIDTH)
        content = QVBoxLayout(column)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        content.addWidget(AuthLogo(), 0)
        content.addSpacing(28)
        content.addWidget(title_label("Accedi al tuo account"))
        content.addSpacing(12)
        content.addWidget(hint_label("Inserisci le tue credenziali per accedere a LogiPlan"))
        content.addSpacing(32)
        content.addWidget(self.email)
        content.addSpacing(20)
        content.addWidget(self.password)
        content.addSpacing(24)
        content.addWidget(self._button)
        content.addSpacing(12)
        content.addWidget(self._error)

        self.setLayout(build_centered_layout(column))

        self._button.clicked.connect(self._on_submit)

    def _on_submit(self) -> None:
        self.submitted.emit(self.email.value(), self.password.value())

    def show_error(self, message: str) -> None:
        self._error.setText(f"⚠ {message}")
        self._error.show()

    def clear_error(self) -> None:
        self._error.hide()

    def clear(self) -> None:
        self.email.set_value("")
        self.password.set_value("")
        self.clear_error()
