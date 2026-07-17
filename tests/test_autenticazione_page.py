"""Test di integrazione GUI per AutenticazionePage: instrada tra le 3 view (Login,
Registrazione, Conferma OTP) e orchestra GestoreAutenticazione. Nessun pytest-qt: singola
QApplication offscreen a livello di modulo, stesso pattern degli altri test GUI."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from gestionale_logistica.autenticazione.gestore_autenticazione import GestoreAutenticazione
from gestionale_logistica.gui.autenticazione.autenticazione_page import (
    _CONFERMA_OTP,
    _LOGIN,
    _REGISTRAZIONE,
    AutenticazionePage,
)

# Ordine delle chiavi allineato sia a GestoreAutenticazione.registra_utente(**DATI_VALIDI)
# (per nome, keyword) sia all'ordine dei parametri di RegistrazioneView.submitted
# (per posizione, *DATI_VALIDI.values()) - i due usi sotto dipendono entrambi da quest'ordine.
DATI_VALIDI = {
    "nome": "Mario",
    "cognome": "Rossi",
    "telefono": "3331234567",
    "email": "mario.rossi@example.com",
    "password": "Password1!",
    "conferma_password": "Password1!",
}


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


class EmailServiceFinto:
    def __init__(self) -> None:
        self.ultimo_codice = None

    def invia_codice_conferma(self, destinatario: str, codice: str) -> None:
        self.ultimo_codice = codice


def _pagina(session):
    email_service = EmailServiceFinto()
    gestore = GestoreAutenticazione(session, email_service)
    return AutenticazionePage(gestore), gestore, email_service


def test_routing_iniziale_su_registrazione_se_nessun_utente(app, session_factory):
    with session_factory() as session:
        pagina, _, _ = _pagina(session)
        assert pagina._stack.currentIndex() == _REGISTRAZIONE


def test_routing_iniziale_su_login_se_utente_esiste(app, session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        gestore.registra_utente(**DATI_VALIDI)
        gestore.verifica_codice(email_service.ultimo_codice)

        pagina = AutenticazionePage(gestore)

        assert pagina._stack.currentIndex() == _LOGIN


def test_registrazione_valida_passa_a_conferma_otp(app, session_factory):
    with session_factory() as session:
        pagina, _, email_service = _pagina(session)

        pagina._registrazione.submitted.emit(*DATI_VALIDI.values())

        assert pagina._stack.currentIndex() == _CONFERMA_OTP
        assert email_service.ultimo_codice is not None


def test_registrazione_non_valida_mostra_errore_e_resta_su_registrazione(app, session_factory):
    with session_factory() as session:
        pagina, _, _ = _pagina(session)
        dati = dict(DATI_VALIDI, conferma_password="Altra1!")

        pagina._registrazione.submitted.emit(*dati.values())

        assert pagina._stack.currentIndex() == _REGISTRAZIONE
        assert not pagina._registrazione._error.isHidden()


def test_conferma_otp_corretta_autentica(app, session_factory):
    with session_factory() as session:
        pagina, _, email_service = _pagina(session)
        pagina._registrazione.submitted.emit(*DATI_VALIDI.values())
        token_ricevuto = []
        pagina.authenticated.connect(token_ricevuto.append)

        pagina._otp.submitted.emit(email_service.ultimo_codice)

        assert len(token_ricevuto) == 1
        assert token_ricevuto[0]


def test_conferma_otp_errata_mostra_errore(app, session_factory):
    with session_factory() as session:
        pagina, _, _ = _pagina(session)
        pagina._registrazione.submitted.emit(*DATI_VALIDI.values())

        pagina._otp.submitted.emit("000000")

        assert pagina._stack.currentIndex() == _CONFERMA_OTP
        assert not pagina._otp._error.isHidden()


def test_login_corretto_autentica(app, session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        gestore.registra_utente(**DATI_VALIDI)
        gestore.verifica_codice(email_service.ultimo_codice)
        pagina = AutenticazionePage(gestore)
        token_ricevuto = []
        pagina.authenticated.connect(token_ricevuto.append)

        pagina._login.submitted.emit(DATI_VALIDI["email"], DATI_VALIDI["password"])

        assert len(token_ricevuto) == 1


def test_login_errato_mostra_errore(app, session_factory):
    with session_factory() as session:
        gestore = GestoreAutenticazione(session, EmailServiceFinto())
        gestore.registra_utente(**DATI_VALIDI)
        pagina = AutenticazionePage(gestore)

        pagina._login.submitted.emit(DATI_VALIDI["email"], "password-sbagliata")

        assert not pagina._login._error.isHidden()


def test_reset_to_login_torna_al_login_con_form_vuoto(app, session_factory):
    with session_factory() as session:
        pagina, _, _ = _pagina(session)
        pagina._registrazione.submitted.emit(*DATI_VALIDI.values())
        pagina._login.email.set_value("residuo@esempio.it")

        pagina.reset_to_login()

        assert pagina._stack.currentIndex() == _LOGIN
        assert pagina._login.email.value() == ""


def test_resend_in_cooldown_mostra_errore(app, session_factory):
    with session_factory() as session:
        pagina, _, _ = _pagina(session)
        pagina._registrazione.submitted.emit(*DATI_VALIDI.values())

        pagina._otp.resendRequested.emit()

        assert not pagina._otp._error.isHidden()


def _compila_registrazione(registrazione, dati):
    registrazione.nome.set_value(dati["nome"])
    registrazione.cognome.set_value(dati["cognome"])
    registrazione.telefono.set_value(dati["telefono"])
    registrazione.email.set_value(dati["email"])
    registrazione.password.set_value(dati["password"])
    registrazione.conferma_password.set_value(dati["conferma_password"])


def test_back_da_otp_torna_a_registrazione(app, session_factory):
    with session_factory() as session:
        pagina, gestore, _ = _pagina(session)
        _compila_registrazione(pagina._registrazione, DATI_VALIDI)
        pagina._registrazione._button.click()

        pagina._otp.backRequested.emit()

        assert pagina._stack.currentIndex() == _REGISTRAZIONE
        assert pagina._registrazione._button.isEnabled()
        assert pagina._registrazione.email.value() == DATI_VALIDI["email"]
        assert gestore.esiste_almeno_un_utente() is False


def test_back_da_otp_permette_di_correggere_e_registrare_di_nuovo(app, session_factory):
    with session_factory() as session:
        pagina, _, email_service = _pagina(session)
        _compila_registrazione(pagina._registrazione, DATI_VALIDI)
        pagina._registrazione._button.click()
        pagina._otp.backRequested.emit()

        dati_corretti = dict(DATI_VALIDI, email="corretta@example.com")
        pagina._registrazione.email.set_value(dati_corretti["email"])
        pagina._registrazione._button.click()

        assert pagina._stack.currentIndex() == _CONFERMA_OTP
        assert pagina._registrazione._error.isHidden()

        token_ricevuto = []
        pagina.authenticated.connect(token_ricevuto.append)
        pagina._otp.submitted.emit(email_service.ultimo_codice)

        assert len(token_ricevuto) == 1


def test_freccetta_back_riceve_davvero_il_click_del_mouse(app, session_factory):
    """Regressione: il titolo "Conferma la tua email" e la freccetta condividono la stessa
    cella di QGridLayout; senza WA_TransparentForMouseEvents sul titolo, la QLabel (aggiunta
    per ultima, quindi sopra nello z-order) intercetta il click reale prima che raggiunga il
    bottone sottostante (bug riportato: "clicco sulla freccetta e non succede nulla").
    `childAt()` replica esattamente l'hit-testing che Qt usa per instradare un click reale a
    schermo — `.click()` programmatico da solo non lo avrebbe rilevato, perche' aggira quella
    risoluzione per posizione."""
    with session_factory() as session:
        pagina, _, _ = _pagina(session)
        _compila_registrazione(pagina._registrazione, DATI_VALIDI)
        pagina._registrazione._button.click()
        pagina.show()
        app.processEvents()

        back = pagina._otp._back
        punto_click = back.geometry().center()

        assert back.parentWidget().childAt(punto_click) is back
