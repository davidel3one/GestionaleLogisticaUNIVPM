"""View Conferma OTP (fonte: mockup Sketch, artboard "Conferma OTP"). Mostrata subito dopo la
registrazione, per confermare il codice a 6 cifre inviato via email."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from gestionale_logistica.gui.pages.autenticazione._shared import (
    CONTENT_WIDTH,
    ERROR_COLOR,
    build_centered_layout,
    hint_label,
    title_label,
)
from gestionale_logistica.gui.components import (
    AuthLogo,
    Button,
    ButtonVariant,
    LinkButton,
    OtpInput,
    load_lucide_icon,
)


class ConfermaOtpView(QWidget):
    """6 caselle codice + bottone Conferma + link "Invia di nuovo"."""

    submitted = Signal(str)
    resendRequested = Signal()
    backRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("ConfermaOtpView { background-color: #FFFFFF; }")

        self._subtitle = hint_label("")
        self._otp = OtpInput(length=6)
        self._button = Button(ButtonVariant.PRIMARY_LARGE, "Conferma")
        self._resend = LinkButton("Non hai ricevuto il codice? Invia di nuovo")
        self._back = LinkButton("", icon=load_lucide_icon("chevron-left", "#2563C9", 16), icon_size=16)
        self._error = hint_label("", color=ERROR_COLOR)
        self._error.hide()

        titolo = title_label("Conferma la tua email")
        titolo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        header_row = QGridLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.addWidget(
            self._back, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        header_row.addWidget(titolo, 0, 0)

        column = QWidget()
        column.setFixedWidth(CONTENT_WIDTH)
        content = QVBoxLayout(column)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        content.addWidget(AuthLogo(), 0)
        content.addSpacing(28)
        content.addLayout(header_row)
        content.addSpacing(12)
        content.addWidget(self._subtitle)
        content.addSpacing(48)
        content.addWidget(self._otp, 0)
        content.addSpacing(16)
        content.addWidget(hint_label("Il codice scade tra 10 minuti"))
        content.addSpacing(8)
        content.addWidget(self._error)
        content.addSpacing(16)
        content.addWidget(self._button)
        content.addSpacing(16)
        content.addWidget(self._resend, 0, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setLayout(build_centered_layout(column))

        self._button.clicked.connect(self._on_submit)
        self._resend.clicked.connect(self.resendRequested)
        self._back.clicked.connect(self.backRequested)

    def set_email(self, email: str) -> None:
        self._subtitle.setText(f"Abbiamo inviato un codice a {email}")

    def _on_submit(self) -> None:
        self.submitted.emit(self._otp.value())

    def show_error(self, message: str) -> None:
        self._error.setText(f"⚠ {message}")
        self._error.show()

    def clear_error(self) -> None:
        self._error.hide()

    def clear_code(self) -> None:
        self._otp.clear()
