import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

CONFIG_PATH = Path("config.ini")
SESSION_TOKEN_PATH = Path(".session_token")


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
    load_dotenv()
    return EmailConfig(
        smtp_host=os.environ["SMTP_HOST"],
        smtp_port=int(os.environ["SMTP_PORT"]),
        smtp_user=os.environ["SMTP_USER"],
        smtp_app_password=os.environ["SMTP_APP_PASSWORD"],
        smtp_mittente_nome=os.environ["SMTP_MITTENTE_NOME"],
    )


def get_db_encryption_key() -> str:
    load_dotenv()
    return os.environ["DB_ENCRYPTION_KEY"]
