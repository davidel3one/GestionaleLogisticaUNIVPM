import smtplib
from email.message import EmailMessage

from gestionale_logistica.config import get_email_config


class EmailService:
    def invia_codice_conferma(self, destinatario: str, codice: str) -> None:
        config = get_email_config()

        messaggio = EmailMessage()
        messaggio["Subject"] = "Codice di conferma - Gestionale Logistica"
        messaggio["From"] = f"{config.smtp_mittente_nome} <{config.smtp_user}>"
        messaggio["To"] = destinatario
        messaggio.set_content(
            f"Il tuo codice di conferma e': {codice}\n\nIl codice scade tra 10 minuti."
        )

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(config.smtp_user, config.smtp_app_password)
            smtp.send_message(messaggio)
