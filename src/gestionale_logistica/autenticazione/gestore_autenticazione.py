import secrets
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
from gestionale_logistica.database.models import CodiceConferma, Sessione, Utente

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


class GestoreAutenticazione:
    def __init__(self, session: Session, email_service: EmailService) -> None:
        self.session = session
        self.email_service = email_service

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
    ) -> Utente:
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

        utente = Utente(
            nome=nome,
            cognome=cognome,
            telefono=telefono,
            email=email,
            password_hash=password_hash,
            ruolo=RuoloUtente.ADMIN,
            flg_confermata=False,
            data_registrazione=datetime.now(),
        )
        self.session.add(utente)
        self.session.flush()

        self._genera_e_invia_codice(utente)
        self.session.commit()
        return utente

    def _genera_e_invia_codice(self, utente: Utente) -> None:
        codice = _genera_codice_otp()
        self.session.add(
            CodiceConferma(
                utente_id=utente.id,
                codice=codice,
                data_scadenza=datetime.now() + DURATA_CODICE_CONFERMA,
                tentativi_falliti=0,
            )
        )
        self.email_service.invia_codice_conferma(utente.email, codice)

    def _ultimo_codice(self, utente_id: int) -> CodiceConferma | None:
        return self.session.scalar(
            select(CodiceConferma)
            .where(CodiceConferma.utente_id == utente_id)
            .order_by(CodiceConferma.id.desc())
        )

    def verifica_codice(self, utente_id: int, codice: str) -> bool:
        codice_conferma = self._ultimo_codice(utente_id)
        if codice_conferma is None:
            return False

        if codice_conferma.tentativi_falliti >= MAX_TENTATIVI_FALLITI:
            return False

        if codice_conferma.data_scadenza < datetime.now():
            return False

        if codice_conferma.codice != codice:
            codice_conferma.tentativi_falliti += 1
            self.session.commit()
            return False

        utente = self.session.get(Utente, utente_id)
        utente.flg_confermata = True
        self.session.delete(codice_conferma)
        self.session.commit()
        return True

    def rigenera_codice(self, utente_id: int) -> None:
        codice_conferma = self._ultimo_codice(utente_id)
        if codice_conferma is not None:
            data_creazione = codice_conferma.data_scadenza - DURATA_CODICE_CONFERMA
            if datetime.now() - data_creazione < COOLDOWN_RIGENERAZIONE_CODICE:
                raise CooldownAttivoError("Attendere prima di richiedere un nuovo codice")
            self.session.delete(codice_conferma)
            self.session.flush()

        utente = self.session.get(Utente, utente_id)
        self._genera_e_invia_codice(utente)
        self.session.commit()

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

    def logout(self, token: str) -> None:
        sessione = self.session.scalar(select(Sessione).where(Sessione.token == token))
        if sessione is not None:
            self.session.delete(sessione)
            self.session.commit()
