from datetime import datetime, timedelta

import pytest

from gestionale_logistica.autenticazione.gestore_autenticazione import (
    CooldownAttivoError,
    CredenzialiNonValideError,
    GestoreAutenticazione,
)
from gestionale_logistica.autenticazione.validazione import ValidazioneError
from gestionale_logistica.database.models import CodiceConferma, Sessione, Utente

DATI_VALIDI = {
    "nome": "Mario",
    "cognome": "Rossi",
    "telefono": "3331234567",
    "email": "mario.rossi@example.com",
    "password": "Password1!",
    "conferma_password": "Password1!",
}


class EmailServiceFinto:
    def __init__(self) -> None:
        self.ultimo_destinatario = None
        self.ultimo_codice = None

    def invia_codice_conferma(self, destinatario: str, codice: str) -> None:
        self.ultimo_destinatario = destinatario
        self.ultimo_codice = codice


def _gestore(session):
    return GestoreAutenticazione(session, EmailServiceFinto())


def test_registrazione_con_dati_validi(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)

        utente = gestore.registra_utente(**DATI_VALIDI)

        assert utente.id is not None
        assert utente.email_confermata is False
        assert email_service.ultimo_destinatario == DATI_VALIDI["email"]
        assert email_service.ultimo_codice is not None
        assert len(session.query(CodiceConferma).all()) == 1


def test_registrazione_rifiutata_se_esiste_gia_un_utente(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        gestore.registra_utente(**DATI_VALIDI)

        with pytest.raises(ValidazioneError):
            gestore.registra_utente(
                nome="Luca",
                cognome="Bianchi",
                telefono="3339876543",
                email="luca.bianchi@example.com",
                password="Password1!",
                conferma_password="Password1!",
            )


def test_email_malformata_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        dati = {**DATI_VALIDI, "email": "non-una-email"}

        with pytest.raises(ValidazioneError):
            gestore.registra_utente(**dati)


def test_telefono_malformato_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        dati = {**DATI_VALIDI, "telefono": "abc123"}

        with pytest.raises(ValidazioneError):
            gestore.registra_utente(**dati)


def test_password_debole_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        dati = {**DATI_VALIDI, "password": "debole", "conferma_password": "debole"}

        with pytest.raises(ValidazioneError):
            gestore.registra_utente(**dati)


def test_password_e_conferma_non_coincidenti_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        dati = {**DATI_VALIDI, "conferma_password": "Altra1!Password"}

        with pytest.raises(ValidazioneError):
            gestore.registra_utente(**dati)


def test_verifica_codice_corretto_conferma_email(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        utente = gestore.registra_utente(**DATI_VALIDI)

        risultato = gestore.verifica_codice(utente.id, email_service.ultimo_codice)

        assert risultato is True
        assert session.get(Utente, utente.id).email_confermata is True
        assert session.query(CodiceConferma).all() == []


def test_verifica_codice_errato_non_conferma(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        utente = gestore.registra_utente(**DATI_VALIDI)

        risultato = gestore.verifica_codice(utente.id, "000000")

        assert risultato is False
        assert session.get(Utente, utente.id).email_confermata is False


def test_verifica_codice_scaduto_non_conferma(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        utente = gestore.registra_utente(**DATI_VALIDI)

        codice_conferma = session.query(CodiceConferma).one()
        codice_conferma.data_scadenza = datetime.now() - timedelta(minutes=1)
        session.commit()

        risultato = gestore.verifica_codice(utente.id, email_service.ultimo_codice)

        assert risultato is False
        assert session.get(Utente, utente.id).email_confermata is False


def test_cinque_tentativi_falliti_invalidano_il_codice(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        utente = gestore.registra_utente(**DATI_VALIDI)

        for _ in range(5):
            assert gestore.verifica_codice(utente.id, "000000") is False

        risultato = gestore.verifica_codice(utente.id, email_service.ultimo_codice)

        assert risultato is False
        assert session.get(Utente, utente.id).email_confermata is False


def test_rigenera_codice_prima_del_cooldown_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        utente = gestore.registra_utente(**DATI_VALIDI)

        with pytest.raises(CooldownAttivoError):
            gestore.rigenera_codice(utente.id)


def test_rigenera_codice_dopo_il_cooldown_invia_nuovo_codice(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        utente = gestore.registra_utente(**DATI_VALIDI)

        codice_conferma = session.query(CodiceConferma).one()
        codice_conferma.data_scadenza = datetime.now() + timedelta(minutes=8)
        session.commit()
        vecchio_codice = email_service.ultimo_codice

        gestore.rigenera_codice(utente.id)

        assert len(session.query(CodiceConferma).all()) == 1
        assert email_service.ultimo_codice != vecchio_codice


def _registra_e_conferma(gestore, email_service):
    utente = gestore.registra_utente(**DATI_VALIDI)
    gestore.verifica_codice(utente.id, email_service.ultimo_codice)
    return utente


def test_login_con_credenziali_corrette_crea_sessione(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        _registra_e_conferma(gestore, email_service)

        sessione = gestore.login(DATI_VALIDI["email"], DATI_VALIDI["password"])

        assert sessione.token is not None
        assert sessione.data_scadenza > datetime.now()
        assert gestore.sessione_valida(sessione.token) is True


def test_login_con_email_non_confermata_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        gestore.registra_utente(**DATI_VALIDI)

        with pytest.raises(CredenzialiNonValideError):
            gestore.login(DATI_VALIDI["email"], DATI_VALIDI["password"])


def test_login_con_password_errata_solleva_errore(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        _registra_e_conferma(gestore, email_service)

        with pytest.raises(CredenzialiNonValideError):
            gestore.login(DATI_VALIDI["email"], "PasswordErrata1!")


def test_login_con_utente_inesistente_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)

        with pytest.raises(CredenzialiNonValideError):
            gestore.login("inesistente@example.com", "Password1!")


def test_sessione_valida_entro_le_tre_ore(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        _registra_e_conferma(gestore, email_service)
        sessione = gestore.login(DATI_VALIDI["email"], DATI_VALIDI["password"])

        assert gestore.sessione_valida(sessione.token) is True


def test_sessione_non_valida_dopo_scadenza(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        _registra_e_conferma(gestore, email_service)
        sessione = gestore.login(DATI_VALIDI["email"], DATI_VALIDI["password"])

        sessione.data_scadenza = datetime.now() - timedelta(seconds=1)
        session.commit()

        assert gestore.sessione_valida(sessione.token) is False


def test_logout_elimina_la_sessione(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        _registra_e_conferma(gestore, email_service)
        sessione = gestore.login(DATI_VALIDI["email"], DATI_VALIDI["password"])

        gestore.logout(sessione.token)

        assert session.query(Sessione).all() == []
