from gestionale_logistica.config import (
    clear_session_token,
    load_config,
    load_session_token,
    save_session_token,
)
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
from gestionale_logistica.gui.dashboard import DashboardPage
from gestionale_logistica.gui.main_window import AppShell
from gestionale_logistica.gui.pages import (
    CamionPage,
    DipendentiPage,
    OrdiniPage,
    SquadrePage,
    ViaggiPage,
)
from gestionale_logistica.gui.pianificazione import PianificazionePage
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione
from gestionale_logistica.risorse.gestore_camion import GestoreCamion
from gestionale_logistica.risorse.gestore_dipendenti import GestoreDipendenti
from gestionale_logistica.risorse.gestore_squadre import GestoreSquadre
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
    # Dashboard). Tutte e 7 le pagine sono integrate.
    sidebar_items = [
        SidebarItem("dashboard", "Dashboard", "layout-dashboard"),
        SidebarItem("ordini", "Ordini", "package"),
        SidebarItem("pianificazione", "Pianificazione", "calendar-clock"),
        SidebarItem("dipendenti", "Dipendenti", "user"),
        SidebarItem("camion", "Camion", "truck"),
        SidebarItem("squadre", "Squadre", "users"),
        SidebarItem("viaggi", "Viaggi", "route"),
    ]

    _crea_pagina = {
        "ordini": lambda: OrdiniPage(GestoreLogistica(), GestoreRendicontazione()),
        "dipendenti": lambda: DipendentiPage(GestoreDipendenti()),
        "camion": lambda: CamionPage(GestoreCamion()),
        "squadre": lambda: SquadrePage(GestoreSquadre()),
        "viaggi": lambda: ViaggiPage(GestoreLogistica()),
    }

    shell_holder: list[AppShell] = []
    token_corrente: list[str] = []

    def _on_authenticated(token: str) -> None:
        token_corrente[:] = [token]
        save_session_token(token)

        shell = AppShell(sidebar_items)
        dashboard_page = DashboardPage()
        pianificazione_page = PianificazionePage()
        for item in sidebar_items:
            if item.id == "dashboard":
                shell.add_page(item.id, dashboard_page)
                continue
            if item.id == "pianificazione":
                shell.add_page(item.id, pianificazione_page)
                continue
            if item.id in _crea_pagina:
                shell.add_page(item.id, _crea_pagina[item.id]())
                continue
            shell.add_page(
                item.id,
                EmptyState(
                    f"{item.label} in arrivo",
                    "Questa pagina non e' ancora stata integrata su questo branch",
                ),
            )
        shell.logoutRequested.connect(_on_logout)

        # "Nuova pianificazione" della Dashboard: apre la Pianificazione sulla tab Automatica.
        dashboard_page.nuovaPianificazioneRequested.connect(pianificazione_page.mostra_tab_automatica)
        dashboard_page.nuovaPianificazioneRequested.connect(lambda: shell.navigate_to("pianificazione"))

        shell_holder[:] = [shell]
        auth_page.close()
        shell.show()

    def _on_logout() -> None:
        if token_corrente:
            gestore_autenticazione.logout(token_corrente.pop())
        clear_session_token()
        if shell_holder:
            shell_holder.pop().close()
        auth_page.reset_to_login()
        auth_page.show()

    auth_page.authenticated.connect(_on_authenticated)

    token_salvato = load_session_token()
    if token_salvato is not None and gestore_autenticazione.sessione_valida(token_salvato):
        _on_authenticated(token_salvato)
    else:
        if token_salvato is not None:
            clear_session_token()
        auth_page.show()

    sys.exit(app.exec())
