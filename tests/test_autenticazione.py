from datetime import datetime, timedelta

import pytest

from gestionale_logistica.autenticazione.gestore_autenticazione import (
    CooldownAttivoError,
    CredenzialiNonValideError,
    GestoreAutenticazione,
)
from gestionale_logistica.autenticazione.validazione import ValidazioneError
from gestionale_logistica.database.models import Sessione, Utente

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

        gestore.registra_utente(**DATI_VALIDI)

        assert email_service.ultimo_destinatario == DATI_VALIDI["email"]
        assert email_service.ultimo_codice is not None
        # Nessuna riga Utente va creata finche' il codice non e' verificato.
        assert session.query(Utente).all() == []


def test_registrazione_rifiutata_se_esiste_gia_un_utente(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        gestore.registra_utente(**DATI_VALIDI)
        gestore.verifica_codice(email_service.ultimo_codice)

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
        gestore.registra_utente(**DATI_VALIDI)

        risultato = gestore.verifica_codice(email_service.ultimo_codice)

        assert risultato is True
        utente = session.query(Utente).one()
        assert utente.email == DATI_VALIDI["email"]
        assert utente.flg_confermata is True


def test_verifica_codice_errato_non_conferma(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        gestore.registra_utente(**DATI_VALIDI)

        risultato = gestore.verifica_codice("000000")

        assert risultato is False
        assert session.query(Utente).all() == []


def test_verifica_codice_scaduto_non_conferma(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        gestore.registra_utente(**DATI_VALIDI)

        gestore._pending.data_scadenza = datetime.now() - timedelta(minutes=1)

        risultato = gestore.verifica_codice(email_service.ultimo_codice)

        assert risultato is False
        assert session.query(Utente).all() == []


def test_cinque_tentativi_falliti_invalidano_il_codice(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        gestore.registra_utente(**DATI_VALIDI)

        for _ in range(5):
            assert gestore.verifica_codice("000000") is False

        risultato = gestore.verifica_codice(email_service.ultimo_codice)

        assert risultato is False
        assert session.query(Utente).all() == []


def test_rigenera_codice_prima_del_cooldown_solleva_errore(session_factory):
    with session_factory() as session:
        gestore = _gestore(session)
        gestore.registra_utente(**DATI_VALIDI)

        with pytest.raises(CooldownAttivoError):
            gestore.rigenera_codice()


def test_rigenera_codice_dopo_il_cooldown_invia_nuovo_codice(session_factory):
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        gestore.registra_utente(**DATI_VALIDI)
        vecchio_codice = email_service.ultimo_codice

        # Simula il trascorrere del cooldown spostando indietro la data di creazione
        # del codice pending (tenuta solo in memoria, non c'e' piu' una riga a DB).
        gestore._pending.data_creazione = datetime.now() - timedelta(minutes=2)

        gestore.rigenera_codice()

        assert email_service.ultimo_codice != vecchio_codice


def _registra_e_conferma(gestore, email_service):
    gestore.registra_utente(**DATI_VALIDI)
    gestore.verifica_codice(email_service.ultimo_codice)


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


def test_chiusura_app_prima_della_conferma_non_lascia_utente_appeso(session_factory):
    """Regressione: prima del fix, registra_utente() committava subito una riga Utente
    con flg_confermata=False. Se l'app si chiudeva prima di verifica_codice(), quella
    riga restava a DB per sempre: esiste_almeno_un_utente() tornava True e bloccava ogni
    nuova registrazione, mentre login() rifiutava perche' l'utente non era confermato -
    account irrecuperabile. Ora i dati della registrazione vivono solo in memoria finche'
    il codice non e' verificato, quindi la chiusura dell'app non lascia nulla a DB."""
    with session_factory() as session:
        email_service = EmailServiceFinto()
        gestore = GestoreAutenticazione(session, email_service)
        gestore.registra_utente(**DATI_VALIDI)

        assert gestore.esiste_almeno_un_utente() is False

        # Simula il riavvio dell'app dopo una chiusura a meta' flusso: nuova istanza di
        # GestoreAutenticazione (stato pending in memoria perso) sulla stessa sessione/DB.
        nuovo_gestore = GestoreAutenticazione(session, email_service)

        nuovo_gestore.registra_utente(**DATI_VALIDI)
