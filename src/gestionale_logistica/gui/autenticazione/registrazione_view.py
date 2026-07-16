"""View Registrazione (fonte: mockup Sketch, artboard "Registrazione"). Mostrata al primo
avvio, quando non esiste ancora nessun utente (account amministratore unico, RF-Autenticazione:
`GestoreAutenticazione.registra_utente` rifiuta una seconda registrazione)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from gestionale_logistica.gui.autenticazione._shared import (
    CAPTION_COLOR,
    CONTENT_WIDTH,
    ERROR_COLOR,
    build_centered_layout,
    hint_label,
    title_label,
)
from gestionale_logistica.gui.components import AuthLogo, Button, ButtonVariant, TextField


class RegistrazioneView(QWidget):
    """Nome/Cognome, Telefono, Email, Password, Conferma password + bottone Crea account."""

    submitted = Signal(str, str, str, str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("RegistrazioneView { background-color: #FFFFFF; }")

        self.nome = TextField("Nome", placeholder="Mario")
        self.cognome = TextField("Cognome", placeholder="Rossi")
        self.telefono = TextField("Telefono", placeholder="333 1234567")
        self.email = TextField("Email", placeholder="nome@azienda.it")
        self.password = TextField("Password", placeholder="········", password=True)
        self.conferma_password = TextField(
            "Conferma password", placeholder="········", password=True
        )
        self._button = Button(ButtonVariant.PRIMARY_LARGE, "Crea account")
        self._error = hint_label("", color=ERROR_COLOR)
        self._error.hide()

        nome_cognome_row = QHBoxLayout()
        nome_cognome_row.setSpacing(20)
        nome_cognome_row.addWidget(self.nome, 1)
        nome_cognome_row.addWidget(self.cognome, 1)

        column = QWidget()
        column.setFixedWidth(CONTENT_WIDTH)
        content = QVBoxLayout(column)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        content.addWidget(AuthLogo(), 0)
        content.addSpacing(24)
        content.addWidget(title_label("Crea il tuo account amministratore"))
        content.addSpacing(12)
        content.addWidget(hint_label("Sarai l'unico amministratore di LogiPlan"))
        content.addSpacing(32)
        content.addLayout(nome_cognome_row)
        content.addSpacing(20)
        content.addWidget(self.telefono)
        content.addSpacing(20)
        content.addWidget(self.email)
        content.addSpacing(20)
        content.addWidget(self.password)
        content.addSpacing(20)
        content.addWidget(self.conferma_password)
        content.addSpacing(16)
        content.addWidget(
            hint_label(
                "Almeno 8 caratteri, con maiuscola, minuscola, cifra e carattere speciale",
                alignment=Qt.AlignmentFlag.AlignLeft,
            )
        )
        content.addSpacing(8)
        content.addWidget(self._error)
        content.addSpacing(16)
        content.addWidget(self._button)
        content.addSpacing(12)
        content.addWidget(hint_label("Riceverai un codice di conferma via email", color=CAPTION_COLOR))

        self.setLayout(build_centered_layout(column))

        self._button.clicked.connect(self._on_submit)

    def _on_submit(self) -> None:
        self._button.setEnabled(False)
        self.submitted.emit(
            self.nome.value(),
            self.cognome.value(),
            self.telefono.value(),
            self.email.value(),
            self.password.value(),
            self.conferma_password.value(),
        )

    def show_error(self, message: str) -> None:
        self._error.setText(f"⚠ {message}")
        self._error.show()
        self._button.setEnabled(True)

    def clear_error(self) -> None:
        self._error.hide()
