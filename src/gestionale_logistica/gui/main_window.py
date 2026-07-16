"""Finestra applicativa base: Sidebar a sinistra + area contenuti (QStackedWidget) a destra."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from gestionale_logistica.gui.components.sidebar import Sidebar, SidebarItem

CONTENT_BG = "#EAEAEA"


class AppShell(QMainWindow):
    """Shell dell'applicazione: naviga tra pagine impilate tramite la Sidebar.

    Le pagine sono registrate con `add_page(item_id, widget)` e associate 1:1 alle voci
    della Sidebar tramite il loro `id`. Il click su una voce cambia la pagina mostrata e
    tiene sincronizzato l'highlight; `logoutRequested` viene inoltrato dalla Sidebar.
    """

    logoutRequested = Signal()

    def __init__(
        self,
        items: list[SidebarItem],
        app_name: str = "LogiPlan",
        user_name: str = "Davide",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gestionale Logistica")
        self.resize(1280, 800)

        self.sidebar = Sidebar(items, app_name=app_name, user_name=user_name)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"QStackedWidget {{ background-color: {CONTENT_BG}; }}")
        self._pages: dict[str, int] = {}
        self._current_id: str | None = None

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self.sidebar.navigated.connect(self._on_navigated)
        self.sidebar.logoutRequested.connect(self.logoutRequested)

    def add_page(self, item_id: str, widget: QWidget) -> None:
        """Registra la pagina `widget` per la voce `item_id`. La prima pagina aggiunta
        diventa quella mostrata all'avvio (con la relativa voce evidenziata)."""
        index = self._stack.addWidget(widget)
        self._pages[item_id] = index
        if len(self._pages) == 1:
            self._current_id = item_id
            self.sidebar.set_active(item_id)
            self._stack.setCurrentIndex(index)

    def navigate_to(self, item_id: str) -> None:
        """Cambia pagina programmaticamente (es. da un'azione di un'altra pagina), stessa
        logica del click su una voce della Sidebar."""
        self._on_navigated(item_id)

    def _on_navigated(self, item_id: str) -> None:
        if item_id in self._pages:
            self._stack.setCurrentIndex(self._pages[item_id])
            self._current_id = item_id
            self.sidebar.set_active(item_id)
        elif self._current_id is not None:
            # Voce senza pagina registrata: la Sidebar si e' gia' auto-evidenziata al
            # click, ma il contenuto non cambia — riporto l'highlight sulla pagina corrente
            # per non lasciare evidenziata una voce che non mostra nulla.
            self.sidebar.set_active(self._current_id)


# Alias di compatibilita' con lo stub precedente.
MainWindow = AppShell
