import configparser
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _app_data_dir() -> Path:
    """Cartella dati utente standard del SO per l'eseguibile compilato (PyInstaller): un
    .app/.exe non ha una working directory garantita (es. lanciato da Finder/Explorer), quindi
    config/DB/log/token non possono restare relativi alla CWD come in modalita' sviluppo.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "GestionaleLogistica"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "GestionaleLogistica"
    else:
        base = Path.home() / ".gestionale-logistica"
    base.mkdir(parents=True, exist_ok=True)
    return base


CONFIG_PATH = _app_data_dir() / "config.ini" if _is_frozen() else Path("config.ini")
SESSION_TOKEN_PATH = _app_data_dir() / ".session_token" if _is_frozen() else Path(".session_token")
_ENV_PATH = _app_data_dir() / ".env" if _is_frozen() else Path(".env")


def default_database_path() -> str:
    return str(_app_data_dir() / "gestionale.db") if _is_frozen() else "gestionale.db"


def default_log_path() -> str:
    return str(_app_data_dir() / "app.log") if _is_frozen() else "app.log"


def _seed_env_file() -> None:
    """Al primo avvio dell'eseguibile compilato, copia il .env impacchettato (SMTP + chiave di
    cifratura) nella cartella dati utente: senza questo passo os.environ[...] solleva KeyError,
    perche' load_dotenv non troverebbe alcun file fuori dalla cartella `dev/`.
    """
    if _ENV_PATH.exists():
        return
    bundled_dir = getattr(sys, "_MEIPASS", None)
    if bundled_dir is None:
        return
    sorgente = Path(bundled_dir) / ".env"
    if sorgente.exists():
        shutil.copy(sorgente, _ENV_PATH)


def _load_env() -> None:
    if _is_frozen():
        _seed_env_file()
        load_dotenv(dotenv_path=_ENV_PATH)
    else:
        load_dotenv()


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config


def save_session_token(token: str) -> None:
    SESSION_TOKEN_PATH.write_text(token)


def load_session_token() -> str | None:
    if not SESSION_TOKEN_PATH.is_file():
        return None
    return SESSION_TOKEN_PATH.read_text().strip() or None


def clear_session_token() -> None:
    SESSION_TOKEN_PATH.unlink(missing_ok=True)


@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_app_password: str
    smtp_mittente_nome: str


def get_email_config() -> EmailConfig:
    _load_env()
    return EmailConfig(
        smtp_host=os.environ["SMTP_HOST"],
        smtp_port=int(os.environ["SMTP_PORT"]),
        smtp_user=os.environ["SMTP_USER"],
        smtp_app_password=os.environ["SMTP_APP_PASSWORD"],
        smtp_mittente_nome=os.environ["SMTP_MITTENTE_NOME"],
    )


def get_db_encryption_key() -> str:
    _load_env()
    return os.environ["DB_ENCRYPTION_KEY"]
