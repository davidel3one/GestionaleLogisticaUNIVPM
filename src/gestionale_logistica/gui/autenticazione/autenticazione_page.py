"""AutenticazionePage: controller delle 3 view di autenticazione (Login, Registrazione,
Conferma OTP). Sostituisce l'intera finestra (nessuna sidebar, fonte: mockup Sketch, nessuno
dei 3 artboard ha una Sidebar) finche' l'utente non e' autenticato; emette `authenticated(token)`
al successo.

Routing iniziale: Registrazione se non esiste ancora nessun utente (account amministratore
unico), altrimenti Login. Dopo la conferma del codice OTP, l'utente viene loggato
automaticamente con le credenziali appena inserite nel form di registrazione, cosi' da non
fargliele ridigitare subito dopo (decisione presa in implementazione, non richiesta esplicita)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from gestionale_logistica.autenticazione.gestore_autenticazione import (
    CooldownAttivoError,
    CredenzialiNonValideError,
    GestoreAutenticazione,
)
from gestionale_logistica.autenticazione.validazione import ValidazioneError
from gestionale_logistica.gui.autenticazione.conferma_otp_view import ConfermaOtpView
from gestionale_logistica.gui.autenticazione.login_view import LoginView
from gestionale_logistica.gui.autenticazione.registrazione_view import RegistrazioneView

_LOGIN, _REGISTRAZIONE, _CONFERMA_OTP = range(3)


class AutenticazionePage(QWidget):
    authenticated = Signal(str)

    def __init__(self, gestore: GestoreAutenticazione, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gestore = gestore
        self._pending_utente_id: int | None = None
        self._pending_credenziali: tuple[str, str] | None = None

        self._login = LoginView()
        self._registrazione = RegistrazioneView()
        self._otp = ConfermaOtpView()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._login)
        self._stack.addWidget(self._registrazione)
        self._stack.addWidget(self._otp)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._login.submitted.connect(self._on_login)
        self._registrazione.submitted.connect(self._on_registrazione)
        self._otp.submitted.connect(self._on_conferma)
        self._otp.resendRequested.connect(self._on_resend)

        self._stack.setCurrentIndex(
            _LOGIN if gestore.esiste_almeno_un_utente() else _REGISTRAZIONE
        )

    def _on_login(self, email: str, password: str) -> None:
        self._login.clear_error()
        try:
            sessione = self._gestore.login(email, password)
        except CredenzialiNonValideError as errore:
            self._login.show_error(str(errore))
            return
        self.authenticated.emit(sessione.token)

    def _on_registrazione(
        self,
        nome: str,
        cognome: str,
        telefono: str,
        email: str,
        password: str,
        conferma_password: str,
    ) -> None:
        self._registrazione.clear_error()
        try:
            utente = self._gestore.registra_utente(
                nome, cognome, telefono, email, password, conferma_password
            )
        except ValidazioneError as errore:
            self._registrazione.show_error(str(errore))
            return
        self._pending_utente_id = utente.id
        self._pending_credenziali = (email, password)
        self._otp.set_email(utente.email)
        self._otp.clear_code()
        self._otp.clear_error()
        self._stack.setCurrentIndex(_CONFERMA_OTP)

    def _on_conferma(self, codice: str) -> None:
        self._otp.clear_error()
        if self._pending_utente_id is None or self._pending_credenziali is None:
            return
        if not self._gestore.verifica_codice(self._pending_utente_id, codice):
            self._otp.show_error("Codice non valido o scaduto")
            return
        email, password = self._pending_credenziali
        sessione = self._gestore.login(email, password)
        self.authenticated.emit(sessione.token)

    def reset_to_login(self) -> None:
        """Torna alla schermata Login a form vuoto (usato dopo il logout)."""
        self._login.clear()
        self._stack.setCurrentIndex(_LOGIN)

    def _on_resend(self) -> None:
        if self._pending_utente_id is None:
            return
        try:
            self._gestore.rigenera_codice(self._pending_utente_id)
        except CooldownAttivoError as errore:
            self._otp.show_error(str(errore))
