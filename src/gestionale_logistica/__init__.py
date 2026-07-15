from gestionale_logistica.config import load_config
import configparser
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gestionale_logistica.autenticazione.email_service import EmailService
from gestionale_logistica.autenticazione.gestore_autenticazione import GestoreAutenticazione
from gestionale_logistica.concorrenza import arresta_esecutore
from gestionale_logistica.gui.autenticazione import AutenticazionePage
from gestionale_logistica.gui.components import EmptyState, SidebarItem
from gestionale_logistica.gui.main_window import AppShell
from gestionale_logistica.scheduler import avvia_scheduler

from gestionale_logistica.database.base import Base, SessionLocal, engine
from gestionale_logistica.database import models


def setup_logging(config: configparser.ConfigParser) -> None:
    logging.basicConfig(
        level=config.get("logging", "level", fallback="INFO"),
        filename=config.get("logging", "file", fallback="app.log"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    Base.metadata.create_all(engine)
    config = load_config()
    setup_logging(config)
    logging.getLogger(__name__).info("Avvio Gestionale Logistica")

    scheduler = avvia_scheduler(config)

    app = QApplication(sys.argv)
    app.aboutToQuit.connect(scheduler.shutdown)
    app.aboutToQuit.connect(arresta_esecutore)

    session = SessionLocal()
    gestore_autenticazione = GestoreAutenticazione(session, EmailService())

    auth_page = AutenticazionePage(gestore_autenticazione)
    auth_page.setWindowTitle("Gestionale Logistica")
    auth_page.resize(1280, 800)

    # Voci di navigazione, ordine e icone verificati nel mockup Sketch (Sidebar, artboard
    # Dashboard). Le pagine applicative non sono ancora integrate su questo branch:
    # ogni voce mostra per ora un EmptyState placeholder, da sostituire quando verranno
    # collegate le pagine vere.
    sidebar_items = [
        SidebarItem("dashboard", "Dashboard", "layout-dashboard"),
        SidebarItem("ordini", "Ordini", "package"),
        SidebarItem("pianificazione", "Pianificazione", "calendar-clock"),
        SidebarItem("dipendenti", "Dipendenti", "user"),
        SidebarItem("camion", "Camion", "truck"),
        SidebarItem("squadre", "Squadre", "users"),
        SidebarItem("viaggi", "Viaggi", "route"),
    ]

    shell_holder: list[AppShell] = []
    token_corrente: list[str] = []

    def _on_authenticated(token: str) -> None:
        token_corrente[:] = [token]

        shell = AppShell(sidebar_items)
        for item in sidebar_items:
            shell.add_page(
                item.id,
                EmptyState(
                    f"{item.label} in arrivo",
                    "Questa pagina non e' ancora stata integrata su questo branch",
                ),
            )
        shell.logoutRequested.connect(_on_logout)

        shell_holder[:] = [shell]
        auth_page.close()
        shell.show()

    def _on_logout() -> None:
        if token_corrente:
            gestore_autenticazione.logout(token_corrente.pop())
        if shell_holder:
            shell_holder.pop().close()
        auth_page.reset_to_login()
        auth_page.show()

    auth_page.authenticated.connect(_on_authenticated)
    auth_page.show()
    sys.exit(app.exec())
