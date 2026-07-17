import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from gestionale_logistica.autenticazione.email_service import EmailService
from gestionale_logistica.autenticazione.validazione import (
    ValidazioneError,
    valida_email,
    valida_password,
    valida_telefono,
)
from gestionale_logistica.database.enums import RuoloUtente
from gestionale_logistica.database.models import Sessione, Utente



DURATA_CODICE_CONFERMA = timedelta(minutes=10)
DURATA_SESSIONE = timedelta(hours=3)
COOLDOWN_RIGENERAZIONE_CODICE = timedelta(seconds=60)
MAX_TENTATIVI_FALLITI = 5


class CooldownAttivoError(Exception):
    pass


class CredenzialiNonValideError(Exception):
    pass


def _genera_codice_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


_HASH = bcrypt.hashpw(secrets.token_bytes(64), bcrypt.gensalt()).decode()


@dataclass
class _RegistrazionePendente:
    """Dati di una registrazione in attesa di conferma OTP, tenuti solo in memoria:
    nessuna riga Utente viene creata finche' il codice non e' verificato con successo
    (in precedenza un Utente non confermato restava "appeso" a DB se l'app si chiudeva
    prima della conferma, bloccando per sempre esiste_almeno_un_utente() e il login)."""

    nome: str
    cognome: str
    telefono: str
    email: str
    password_hash: str
    codice: str
    data_scadenza: datetime
    data_creazione: datetime
    tentativi_falliti: int = 0


class GestoreAutenticazione:
    def __init__(self, session: Session, email_service: EmailService) -> None:
        self.session = session
        self.email_service = email_service
        self._pending: _RegistrazionePendente | None = None

    def esiste_almeno_un_utente(self) -> bool:
        return self.session.scalar(select(Utente.id).limit(1)) is not None

    def registra_utente(
        self,
        nome: str,
        cognome: str,
        telefono: str,
        email: str,
        password: str,
        conferma_password: str,
    ) -> None:
        email = email.strip().lower()

        if self.esiste_almeno_un_utente():
            raise ValidazioneError("Esiste gia' un account registrato")

        valida_email(email)
        valida_telefono(telefono)
        valida_password(password)
        if password != conferma_password:
            raise ValidazioneError("Le password non coincidono")

        if self.session.scalar(select(Utente).where(Utente.email == email)) is not None:
            raise ValidazioneError(f"Email gia' registrata: '{email}'")

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        self._pending = _RegistrazionePendente(
            nome=nome,
            cognome=cognome,
            telefono=telefono,
            email=email,
            password_hash=password_hash,
            codice="",
            data_scadenza=datetime.now(),
            data_creazione=datetime.now(),
        )
        self._genera_e_invia_codice()

    def _genera_e_invia_codice(self) -> None:
        assert self._pending is not None
        codice = _genera_codice_otp()
        ora = datetime.now()
        self._pending.codice = codice
        self._pending.data_scadenza = ora + DURATA_CODICE_CONFERMA
        self._pending.data_creazione = ora
        self._pending.tentativi_falliti = 0
        self.email_service.invia_codice_conferma(self._pending.email, codice)

    def verifica_codice(self, codice: str) -> bool:
        pending = self._pending
        if pending is None:
            return False

        if pending.tentativi_falliti >= MAX_TENTATIVI_FALLITI:
            return False

        if pending.data_scadenza < datetime.now():
            return False

        if pending.codice != codice:
            pending.tentativi_falliti += 1
            return False

        utente = Utente(
            nome=pending.nome,
            cognome=pending.cognome,
            telefono=pending.telefono,
            email=pending.email,
            password_hash=pending.password_hash,
            ruolo=RuoloUtente.ADMIN,
            flg_confermata=True,
            data_registrazione=datetime.now(),
        )
        self.session.add(utente)
        self.session.commit()
        self._pending = None
        return True

    def rigenera_codice(self) -> None:
        if self._pending is None:
            raise ValidazioneError("Nessuna registrazione in corso")

        if datetime.now() - self._pending.data_creazione < COOLDOWN_RIGENERAZIONE_CODICE:
            raise CooldownAttivoError("Attendere prima di richiedere un nuovo codice")

        self._genera_e_invia_codice()

    def login(self, email: str, password: str) -> Sessione:
        email = email.strip().lower()
        utente = self.session.scalar(select(Utente).where(Utente.email == email))

        hash_da_verificare = utente.password_hash if utente is not None else _HASH
        password_corretta = bcrypt.checkpw(password.encode(), hash_da_verificare.encode())

        if utente is None or not utente.flg_confermata or not password_corretta:
            raise CredenzialiNonValideError("Email o password non validi")

        sessione = Sessione(
            utente_id=utente.id,
            token=secrets.token_urlsafe(32),
            data_creazione=datetime.now(),
            data_scadenza=datetime.now() + DURATA_SESSIONE,
        )
        self.session.add(sessione)
        self.session.commit()
        return sessione

    def sessione_valida(self, token: str) -> bool:
        sessione = self.session.scalar(select(Sessione).where(Sessione.token == token))
        return sessione is not None and sessione.data_scadenza > datetime.now()

    def utente_da_token(self, token: str) -> Utente | None:
        sessione = self.session.scalar(select(Sessione).where(Sessione.token == token))
        if sessione is None:
            return None
        return self.session.get(Utente, sessione.utente_id)

    def logout(self, token: str) -> None:
        sessione = self.session.scalar(select(Sessione).where(Sessione.token == token))
        if sessione is not None:
            self.session.delete(sessione)
            self.session.commit()
