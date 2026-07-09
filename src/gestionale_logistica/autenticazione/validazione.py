import re

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TELEFONO_REGEX = re.compile(r"^(\+39)?\d{9,10}$")


class ValidazioneError(Exception):
    pass


def valida_email(email: str) -> None:
    if not EMAIL_REGEX.match(email):
        raise ValidazioneError(f"Email non valida: '{email}'")


def valida_telefono(telefono: str) -> None:
    if not TELEFONO_REGEX.match(telefono.replace(" ", "")):
        raise ValidazioneError(f"Numero di telefono non valido: '{telefono}'")


def valida_password(password: str) -> None:
    if len(password) < 8:
        raise ValidazioneError("La password deve contenere almeno 8 caratteri")
    if not re.search(r"[A-Z]", password):
        raise ValidazioneError("La password deve contenere almeno una lettera maiuscola")
    if not re.search(r"[a-z]", password):
        raise ValidazioneError("La password deve contenere almeno una lettera minuscola")
    if not re.search(r"\d", password):
        raise ValidazioneError("La password deve contenere almeno una cifra")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValidazioneError("La password deve contenere almeno un carattere speciale")
